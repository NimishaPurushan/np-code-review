import json
import logging
import time
from typing import Any

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Constants for retry logic
MAX_RETRIES = 3
RETRY_DELAY_BASE = 2  # seconds
RETRY_DELAY_MAX = 10  # seconds


class BedrockClient:
    def __init__(
        self,
        model_id: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        aws_region: str = "us-east-1",
    ):
        self.model_id = model_id
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.aws_region = aws_region
        self._runtime_client = None

    @property
    def runtime(self):
        if self._runtime_client is None:
            boto_config = BotoConfig(
                region_name=self.aws_region,
                retries={"max_attempts": 3, "mode": "adaptive"},
            )
            self._runtime_client = boto3.client(
                "bedrock-runtime",
                config=boto_config,
            )
        return self._runtime_client

    def _normalize_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize message format based on model family."""
        normalized = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            # If content is a string, convert to appropriate format
            if isinstance(content, str):
                if self.model_id.startswith("amazon.nova"):
                    # Nova models: array of objects with just "text" key
                    normalized.append({"role": role, "content": [{"text": content}]})
                else:
                    # Anthropic models: array of objects with "type" and "text"
                    normalized.append(
                        {"role": role, "content": [{"type": "text", "text": content}]}
                    )
            # If content is already an array
            elif isinstance(content, list):
                if self.model_id.startswith("amazon.nova"):
                    # Nova: ensure no "type" field
                    nova_content = []
                    for item in content:
                        if isinstance(item, dict):
                            if "type" in item and item["type"] == "text":
                                # Remove type field for Nova
                                nova_content.append({"text": item["text"]})
                            else:
                                nova_content.append(item)
                        else:
                            nova_content.append({"text": str(item)})
                    normalized.append({"role": role, "content": nova_content})
                else:
                    # Anthropic: ensure proper format with type
                    anthropic_content = []
                    for item in content:
                        if isinstance(item, dict):
                            if "type" not in item and "text" in item:
                                # Add type field for Anthropic
                                anthropic_content.append({"type": "text", "text": item["text"]})
                            else:
                                anthropic_content.append(item)
                        else:
                            anthropic_content.append({"type": "text", "text": str(item)})
                    normalized.append({"role": role, "content": anthropic_content})
            else:
                # Keep as-is if neither string nor list
                normalized.append(msg)

        return normalized

    def invoke_model(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Invoke Bedrock model with automatic retry logic.

        Implements exponential backoff for transient failures:
        - Rate limit errors
        - Throttling exceptions
        - Network timeouts
        """
        last_exception = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Normalize messages format based on model family
                normalized_messages = self._normalize_messages(messages)

                # Build request body based on model family
                if self.model_id.startswith("anthropic."):
                    # Anthropic Claude models
                    body = {
                        "anthropic_version": "bedrock-2023-05-31",
                        "messages": normalized_messages,
                        "max_tokens": self.max_tokens,
                        "temperature": self.temperature,
                    }
                    if system:
                        body["system"] = system
                elif self.model_id.startswith("amazon.nova"):
                    # Amazon Nova models use a different format
                    body = {
                        "messages": normalized_messages,
                        "inferenceConfig": {
                            "maxTokens": self.max_tokens,
                            "temperature": self.temperature,
                        },
                    }
                    if system:
                        body["system"] = [{"text": system}]
                else:
                    # Default to Anthropic format for unknown models
                    body = {
                        "anthropic_version": "bedrock-2023-05-31",
                        "messages": normalized_messages,
                        "max_tokens": self.max_tokens,
                        "temperature": self.temperature,
                    }
                    if system:
                        body["system"] = system

                # Filter out parameters that shouldn't be in the body
                filtered_kwargs = {
                    k: v
                    for k, v in kwargs.items()
                    if k not in ["max_tokens", "temperature", "model_id"]
                }
                body.update(filtered_kwargs)

                logger.info(
                    f"Invoking model {self.model_id} (attempt {attempt}/{MAX_RETRIES}) "
                    f"with {len(messages)} messages"
                )

                response = self.runtime.invoke_model(
                    modelId=self.model_id,
                    contentType="application/json",
                    accept="application/json",
                    body=json.dumps(body),
                )

                response_body = json.loads(response["body"].read())
                logger.info(
                    f"Model invocation successful. Stop reason: {response_body.get('stop_reason')}"
                )

                return response_body

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                error_message = e.response.get("Error", {}).get("Message", str(e))

                logger.warning(
                    f"Bedrock error on attempt {attempt}/{MAX_RETRIES}: "
                    f"{error_code} - {error_message}"
                )

                # Check if error is retryable
                retryable_errors = [
                    "ThrottlingException",
                    "TooManyRequestsException",
                    "ServiceUnavailableException",
                    "InternalServerError",
                ]

                if error_code in retryable_errors and attempt < MAX_RETRIES:
                    # Calculate exponential backoff
                    delay = min(RETRY_DELAY_BASE * (2 ** (attempt - 1)), RETRY_DELAY_MAX)
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                    last_exception = e
                    continue
                else:
                    # Non-retryable error or max retries exceeded
                    logger.error(f"Bedrock invocation failed: {error_code} - {error_message}")
                    raise

            except Exception as e:
                logger.error(f"Unexpected error during model invocation: {str(e)}")
                if attempt < MAX_RETRIES:
                    delay = min(RETRY_DELAY_BASE * (2 ** (attempt - 1)), RETRY_DELAY_MAX)
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                    last_exception = e
                    continue
                else:
                    raise

        # If we get here, all retries failed
        if last_exception:
            raise last_exception
        raise Exception("Model invocation failed after all retries")

    def analyze_code(
        self,
        code: str,
        language: str,
        analysis_type: str = "review",
    ) -> str:
        system_prompt = f"""You are an expert code reviewer specializing in {language}.
Provide detailed, actionable feedback on code quality, best practices, potential bugs,
security issues, and performance optimizations."""

        user_prompt = f"""Please perform a {analysis_type} of the following {language} code:

```{language}
{code}
```

Provide specific recommendations with examples where applicable."""

        # Pass content as string - _normalize_messages will format it correctly for the model
        messages = [{"role": "user", "content": user_prompt}]

        response = self.invoke_model(
            messages=messages,
            system=system_prompt,
        )
        if self.model_id.startswith("amazon.nova"):
            # Extract text from Nova response
            content = response["output"]["message"]["content"]
            if content and isinstance(content, list):
                return content[0].get("text", "")
        else:
            # Extract text from response
            content = response.get("content", [])
            if content and isinstance(content, list):
                return content[0].get("text", "")

        return ""

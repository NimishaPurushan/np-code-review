import logging
import time
from typing import Any

from azure.identity import ClientSecretCredential, get_bearer_token_provider
from openai import APIConnectionError, APIStatusError, AzureOpenAI, RateLimitError

from .utils import messages_to_openai_chat_messages

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY_BASE = 2
RETRY_DELAY_MAX = 10

# Default scope for Azure AI / Cognitive Services (client credentials flow)
DEFAULT_COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"


class AIClient:
    """Azure OpenAI chat client using Microsoft Entra ID (client id + secret)."""

    def __init__(
        self,
        azure_endpoint: str,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        deployment_name: str,
        api_version: str = "2024-08-01-preview",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        token_scope: str = DEFAULT_COGNITIVE_SERVICES_SCOPE,
    ):
        self.azure_endpoint = azure_endpoint.rstrip("/")
        self.deployment_name = deployment_name
        self.api_version = api_version
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client: AzureOpenAI | None = None

        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
        self._token_provider = get_bearer_token_provider(credential, token_scope)

    @property
    def client(self) -> AzureOpenAI:
        if self._client is None:
            self._client = AzureOpenAI(
                api_version=self.api_version,
                azure_endpoint=self.azure_endpoint,
                azure_ad_token_provider=self._token_provider,
            )
        return self._client

    def invoke_model(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Call chat completions; returns ``content`` list format expected by ``AICodeReviewer``."""
        openai_messages = messages_to_openai_chat_messages(messages, system)
        max_tokens = int(kwargs.pop("max_tokens", self.max_tokens))
        temperature = float(kwargs.pop("temperature", self.temperature))

        last_exception: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(
                    "Invoking Azure OpenAI deployment %s (attempt %s/%s) with %s messages",
                    self.deployment_name,
                    attempt,
                    MAX_RETRIES,
                    len(openai_messages),
                )

                completion = self.client.chat.completions.create(
                    model=self.deployment_name,
                    messages=openai_messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                )

                choice = completion.choices[0]
                text = (choice.message.content or "").strip()
                logger.info(
                    "Azure OpenAI completion ok (finish_reason=%s)",
                    getattr(choice, "finish_reason", None),
                )
                return {"content": [{"text": text}]}

            except RateLimitError as e:
                logger.warning(
                    "Azure OpenAI rate limit on attempt %s/%s: %s",
                    attempt,
                    MAX_RETRIES,
                    e,
                )
                last_exception = e
            except APIConnectionError as e:
                logger.warning(
                    "Azure OpenAI connection error on attempt %s/%s: %s",
                    attempt,
                    MAX_RETRIES,
                    e,
                )
                last_exception = e
            except APIStatusError as e:
                status = getattr(e, "status_code", None)
                logger.warning(
                    "Azure OpenAI API error on attempt %s/%s: status=%s %s",
                    attempt,
                    MAX_RETRIES,
                    status,
                    e,
                )
                retryable = status in (408, 429, 500, 502, 503, 504)
                if not retryable:
                    raise
                last_exception = e
            except Exception as e:
                logger.error("Unexpected error during Azure OpenAI call: %s", e)
                last_exception = e

            if attempt < MAX_RETRIES:
                delay = min(RETRY_DELAY_BASE * (2 ** (attempt - 1)), RETRY_DELAY_MAX)
                logger.info("Retrying in %s seconds...", delay)
                time.sleep(delay)

        if last_exception:
            raise last_exception
        raise RuntimeError("Azure OpenAI invocation failed after all retries")

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

        messages = [{"role": "user", "content": user_prompt}]
        response = self.invoke_model(messages=messages, system=system_prompt)
        content = response.get("content", [])
        if content and isinstance(content, list):
            return str(content[0].get("text", ""))
        return ""

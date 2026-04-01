from typing import Any


def normalize_messages(messages: list[dict[str, Any]], model_id: str) -> list[dict[str, Any]]:
    """
    Normalize message format based on model family.

    Args:
        messages: List of message dictionaries with 'role' and 'content' keys
        model_id: The Bedrock model ID

    Returns:
        Normalized messages formatted for the specific model family
    """
    normalized = []

    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        # If content is a string, convert to appropriate format
        if isinstance(content, str):
            if model_id.startswith("amazon.nova"):
                # Nova models: array of objects with just "text" key
                normalized.append({"role": role, "content": [{"text": content}]})
            else:
                # Anthropic models: array of objects with "type" and "text"
                normalized.append({"role": role, "content": [{"type": "text", "text": content}]})
        # If content is already an array
        elif isinstance(content, list):
            if model_id.startswith("amazon.nova"):
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


def build_request_body(
    model_id: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    temperature: float,
    system: str | None = None,
    **kwargs,
) -> dict[str, Any]:
    """
    Build request body based on model family.

    Args:
        model_id: The Bedrock model ID
        messages: List of normalized messages
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        system: Optional system prompt
        **kwargs: Additional model-specific parameters

    Returns:
        Request body formatted for the specific model family
    """
    if model_id.startswith("anthropic."):
        # Anthropic Claude models
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            body["system"] = system
    elif model_id.startswith("amazon.nova"):
        # Amazon Nova models use a different format
        body = {
            "messages": messages,
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system:
            body["system"] = [{"text": system}]
    else:
        # Default to Anthropic format for unknown models
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            body["system"] = system

    # Filter out parameters that shouldn't be in the body
    filtered_kwargs = {
        k: v for k, v in kwargs.items() if k not in ["max_tokens", "temperature", "model_id"]
    }
    body.update(filtered_kwargs)

    return body


def extract_text_from_response(model_id: str, response: dict[str, Any]) -> str:
    if model_id.startswith("amazon.nova"):
        # Nova response format
        content = response.get("output", {}).get("message", {}).get("content", [])
        if content and isinstance(content, list):
            return content[0].get("text", "")
    else:
        # Anthropic response format
        content = response.get("content", [])
        if content and isinstance(content, list):
            return content[0].get("text", "")

    raise Exception("Unable to extract text from response - unrecognized format")

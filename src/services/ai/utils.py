from typing import Any


def _content_blocks_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if "text" in block or block.get("type") == "text" and "text" in block:
                    parts.append(str(block["text"]))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return str(content) if content is not None else ""


def messages_to_openai_chat_messages(
    messages: list[dict[str, Any]],
    system: str | None = None,
) -> list[dict[str, str]]:
    """Build OpenAI/Azure chat `messages` from app message dicts (string or content blocks)."""
    out: list[dict[str, str]] = []
    if system:
        out.append({"role": "system", "content": system})
    for msg in messages:
        role = msg.get("role", "user")
        text = _content_blocks_to_text(msg.get("content"))
        out.append({"role": role, "content": text})
    return out

"""Tests for Azure OpenAI message shaping helpers."""

from src.services.ai.utils import messages_to_openai_chat_messages


class TestMessagesToOpenAIChatMessages:
    def test_string_user_content(self):
        messages = [{"role": "user", "content": "hello world"}]
        result = messages_to_openai_chat_messages(messages, system="You are helpful")
        assert result == [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "hello world"},
        ]

    def test_content_blocks_with_type_text(self):
        messages = [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]
        result = messages_to_openai_chat_messages(messages)
        assert result == [{"role": "user", "content": "hello"}]

    def test_content_blocks_with_text_key_only(self):
        messages = [{"role": "user", "content": [{"text": "hello"}]}]
        result = messages_to_openai_chat_messages(messages)
        assert result == [{"role": "user", "content": "hello"}]

    def test_multiple_messages_no_system(self):
        messages = [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "second"},
        ]
        result = messages_to_openai_chat_messages(messages)
        assert len(result) == 3
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"

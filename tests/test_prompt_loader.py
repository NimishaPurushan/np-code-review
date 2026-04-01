import pytest

from src.utils.prompts import (
    get_pr_summary_template,
    get_system_prompt,
    get_user_prompt,
)


class TestGetSystemPrompt:
    def test_valid_language(self):
        result = get_system_prompt("Python")
        assert "Python" in result
        assert "code reviewer" in result

    def test_empty_string_language(self):
        result = get_system_prompt("")
        assert "code reviewer" in result

    def test_special_characters_in_language(self):
        result = get_system_prompt("C++")
        assert "C++" in result

    def test_none_language_converts_to_string(self):
        result = get_system_prompt(None)
        assert "None" in result
        assert "code reviewer" in result

    def test_int_language_works(self):
        result = get_system_prompt(123)
        assert "123" in result


class TestGetUserPrompt:
    def test_valid_all_parameters(self):
        result = get_user_prompt(
            file_path="src/main.py",
            language="Python",
            code="def hello(): pass",
            context="PR #123: Add greeting function",
        )
        assert "src/main.py" in result
        assert "Python" in result
        assert "def hello(): pass" in result
        assert "PR #123" in result
        assert "Context:" in result

    def test_valid_without_context(self):
        result = get_user_prompt(
            file_path="src/main.py",
            language="Python",
            code="def hello(): pass",
            context=None,
        )
        assert "src/main.py" in result
        assert "Python" in result
        assert "def hello(): pass" in result
        assert "Context:" not in result

    def test_empty_context(self):
        result = get_user_prompt(
            file_path="src/main.py",
            language="Python",
            code="def hello(): pass",
            context="",
        )
        assert "src/main.py" in result
        assert "Context:" not in result

    def test_empty_strings(self):
        result = get_user_prompt(
            file_path="", language="", code="", context=None
        )
        assert "File Path" in result
        assert len(result) > 0

    def test_none_file_path_converts_to_string(self):
        result = get_user_prompt(
            file_path=None,
            language="Python",
            code="def hello(): pass",
            context=None,
        )
        assert "None" in result
        assert "Python" in result

    def test_none_language_in_user_prompt_converts_to_string(self):
        result = get_user_prompt(
            file_path="src/main.py",
            language=None,
            code="def hello(): pass",
            context=None,
        )
        assert "None" in result
        assert "src/main.py" in result

    def test_none_code_converts_to_string(self):
        result = get_user_prompt(
            file_path="src/main.py",
            language="Python",
            code=None,
            context=None,
        )
        assert "None" in result
        assert "Python" in result

    def test_multiline_code(self):
        code = """def hello():
    print("Hello, World!")
    return True"""
        result = get_user_prompt(
            file_path="src/main.py",
            language="Python",
            code=code,
            context=None,
        )
        assert "def hello():" in result
        assert 'print("Hello, World!")' in result

    def test_special_characters_in_context(self):
        result = get_user_prompt(
            file_path="src/main.py",
            language="Python",
            code="pass",
            context="PR #123: Fix bug with $ and {} characters",
        )
        assert "$" in result
        assert "{}" in result


class TestGetPRSummaryTemplate:
    def test_returns_string(self):
        result = get_pr_summary_template()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_idempotent(self):
        result1 = get_pr_summary_template()
        result2 = get_pr_summary_template()
        assert result1 == result2


class TestEdgeCases:
    def test_unicode_in_code(self):
        result = get_user_prompt(
            file_path="src/test.py",
            language="Python",
            code="# Comment with émojis 🚀 and unicode: 你好",
            context=None,
        )
        assert "🚀" in result
        assert "你好" in result

    def test_very_long_code(self):
        long_code = "x = 1\n" * 10000
        result = get_user_prompt(
            file_path="src/test.py",
            language="Python",
            code=long_code,
            context=None,
        )
        assert "x = 1" in result
        assert len(result) > 10000

    def test_code_with_braces(self):
        code = "def test(): return {key: value}"
        result = get_user_prompt(
            file_path="src/test.py",
            language="Python",
            code=code,
            context=None,
        )
        assert "{key: value}" in result

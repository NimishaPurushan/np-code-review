"""
Test script to verify previous feedback functionality.
This tests the new methods added to support tracking previous bot comments.
"""

import sys
from unittest.mock import MagicMock, Mock

sys.path.insert(0, "src")

from services.github.client import GithubClient


def test_format_previous_feedback():
    """Test that previous comments are formatted correctly."""
    client = GithubClient("test_app_id", "test_key")
    
    previous_comments = [
        {
            "type": "general",
            "author": "bot-user",
            "created_at": "2026-03-15T10:00:00",
            "body": "Please fix the security issue in authentication.",
        },
        {
            "type": "inline",
            "author": "bot-user",
            "created_at": "2026-03-15T10:05:00",
            "file": "src/auth.py",
            "line": 42,
            "body": "This password comparison is vulnerable to timing attacks.",
        },
    ]
    
    formatted = client.format_previous_feedback(previous_comments)
    
    assert "Previous Bot Feedback" in formatted
    assert "Comment 1" in formatted
    assert "Comment 2" in formatted
    assert "General PR Comment" in formatted
    assert "Inline on `src/auth.py` line 42" in formatted
    assert "Please fix the security issue" in formatted
    assert "timing attacks" in formatted
    
    print("✓ format_previous_feedback test passed")


def test_format_no_previous_feedback():
    """Test formatting when there are no previous comments."""
    client = GithubClient("test_app_id", "test_key")
    
    formatted = client.format_previous_feedback([])
    
    assert "No previous feedback" in formatted
    
    print("✓ format_no_previous_feedback test passed")


def test_get_bot_previous_comments_structure():
    """Test the structure of returned bot comments."""
    client = GithubClient("test_app_id", "test_key")
    
    mock_user = Mock()
    mock_user.login = "test-bot[bot]"
    
    mock_issue_comment = Mock()
    mock_issue_comment.user = mock_user
    mock_issue_comment.created_at = Mock()
    mock_issue_comment.created_at.isoformat = Mock(return_value="2026-03-15T10:00:00")
    mock_issue_comment.body = "Test comment"
    
    mock_review_comment = Mock(spec=['user', 'created_at', 'body', 'path', 'original_line'])
    mock_review_comment.user = mock_user
    mock_review_comment.created_at = Mock()
    mock_review_comment.created_at.isoformat = Mock(return_value="2026-03-15T10:05:00")
    mock_review_comment.body = "Test review comment"
    mock_review_comment.path = "test.py"
    mock_review_comment.original_line = 10
    
    client.get_bot_username = Mock(return_value="test-bot[bot]")
    client.get_pr_comments = Mock(return_value=[mock_issue_comment])
    client.get_pr_review_comments = Mock(return_value=[mock_review_comment])
    
    comments = client.get_bot_previous_comments(123, "org/repo", 1)
    
    assert len(comments) == 2
    assert comments[0]["type"] == "general"
    assert comments[0]["body"] == "Test comment"
    assert comments[1]["type"] == "inline"
    assert comments[1]["file"] == "test.py"
    assert comments[1]["line"] == 10
    
    print("✓ get_bot_previous_comments_structure test passed")


def test_prompt_includes_previous_feedback():
    """Test that the prompt template includes previous feedback."""
    from utils.prompts import get_user_prompt
    
    prompt = get_user_prompt(
        file_path="test.py",
        language="python",
        code="def test(): pass",
        context="Test PR",
        previous_feedback="## Previous Bot Feedback\n\nTest feedback content"
    )
    
    assert "Previous Bot Feedback" in prompt
    assert "Test feedback content" in prompt
    assert "addresses_previous_issue" in prompt
    
    print("✓ prompt_includes_previous_feedback test passed")


def test_prompt_without_previous_feedback():
    """Test that the prompt works without previous feedback."""
    from utils.prompts import get_user_prompt
    
    prompt = get_user_prompt(
        file_path="test.py",
        language="python",
        code="def test(): pass",
        context="Test PR",
        previous_feedback=None
    )
    
    assert "test.py" in prompt
    assert "python" in prompt
    assert "Previous Bot Feedback" not in prompt
    
    print("✓ prompt_without_previous_feedback test passed")


if __name__ == "__main__":
    print("\n🧪 Running Previous Feedback Feature Tests\n")
    print("=" * 60)
    
    try:
        test_format_previous_feedback()
        test_format_no_previous_feedback()
        test_get_bot_previous_comments_structure()
        test_prompt_includes_previous_feedback()
        test_prompt_without_previous_feedback()
        
        print("=" * 60)
        print("\n✅ All tests passed! The previous feedback feature is working.\n")
        print("Summary:")
        print("  • Bot can retrieve its own previous comments")
        print("  • Comments are properly formatted for AI context")
        print("  • Prompt templates include previous feedback")
        print("  • AI is instructed to check if issues were addressed")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error running tests: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

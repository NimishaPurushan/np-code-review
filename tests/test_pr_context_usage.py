import pytest
from unittest.mock import Mock
from src.services.code_review.code_review_service import CodeReviewService
from src.config.config import Config


class TestPRContextFormatting:
    """Test PR context formatting functionality."""

    def test_format_pr_context_with_full_details(self):
        """Test context formatting with complete PR information."""
        config = Mock(spec=Config)
        service = CodeReviewService(config)

        pr_title = "Add user authentication feature"
        pr_body = """## Description
This PR adds JWT-based authentication to the API.

## Known Limitations
- Session management is not yet implemented (will be in next PR)
- Token refresh logic is intentionally simplified for MVP

## Testing
- Added unit tests for auth middleware
- Manual testing completed"""
        file_path = "src/auth/middleware.py"

        context = service._format_pr_context(pr_title, pr_body, file_path)

        # Verify all components are included
        assert "Add user authentication feature" in context
        assert "JWT-based authentication" in context
        assert "Known Limitations" in context
        assert "src/auth/middleware.py" in context
        assert "Review Context Instructions" in context
        assert "ALIGN" in context
        assert "intentional decisions" in context

    def test_format_pr_context_with_no_description(self):
        config = Mock(spec=Config)
        service = CodeReviewService(config)

        pr_title = "Fix bug in login"
        pr_body = None
        file_path = "auth.py"

        context = service._format_pr_context(pr_title, pr_body, file_path)

        assert "Fix bug in login" in context
        assert "No description provided" in context
        assert "auth.py" in context
        assert "Review Context Instructions" in context

    def test_format_pr_context_with_empty_description(self):
        config = Mock(spec=Config)
        service = CodeReviewService(config)

        pr_title = "Refactor database module"
        pr_body = ""
        file_path = "db/connection.py"

        context = service._format_pr_context(pr_title, pr_body, file_path)

        assert "Refactor database module" in context
        assert "No description provided" in context
        assert "db/connection.py" in context

    def test_format_pr_context_preserves_markdown(self):
        """Test that markdown formatting in PR description is preserved."""
        config = Mock(spec=Config)
        service = CodeReviewService(config)

        pr_title = "Update docs"
        pr_body = """## Changes
- Updated README
- Added **important** note
- Fixed `code examples`

### TODO
- [ ] Add more examples"""
        file_path = "README.md"

        context = service._format_pr_context(pr_title, pr_body, file_path)

        # Verify markdown is preserved
        assert "## Changes" in context
        assert "**important**" in context
        assert "`code examples`" in context
        assert "- [ ] Add more examples" in context

    def test_format_pr_context_includes_all_instructions(self):
        """Test that all critical instructions are included in context."""
        config = Mock(spec=Config)
        service = CodeReviewService(config)

        context = service._format_pr_context("Test", "Body", "file.py")

        # Verify key instruction keywords are present
        required_keywords = [
            "INTENT",
            "SCOPE",
            "known limitations",
            "trade-offs",
            "intentional decisions",
            "ALIGN",
            "matches the scope",
            "partial implementations",
            "work-in-progress",
            "previous feedback",
        ]

        for keyword in required_keywords:
            assert keyword in context, f"Missing keyword: {keyword}"

    def test_format_pr_context_includes_all_files(self):
        """Test that context includes the list of all changed files."""
        config = Mock(spec=Config)
        service = CodeReviewService(config)

        all_files = ["src/auth/login.py", "src/auth/register.py", "tests/test_auth.py"]
        context = service._format_pr_context(
            "Add authentication", "Implements JWT auth", "src/auth/login.py", all_files
        )

        # Verify all files are listed
        assert "All Files Changed in This PR" in context
        assert "src/auth/login.py" in context
        assert "src/auth/register.py" in context
        assert "tests/test_auth.py" in context
        
        # Verify the current file being reviewed is shown
        assert "File Being Reviewed" in context
        assert "src/auth/login.py" in context

    def test_format_pr_context_detects_scope_mismatch(self):
        """Test that context includes instructions to detect scope mismatches."""
        config = Mock(spec=Config)
        service = CodeReviewService(config)

        # Scenario: PR says adding auth but only config file changed
        all_files = ["pyproject.toml"]
        context = service._format_pr_context(
            "Add user authentication system",
            "Implements JWT-based authentication with login/logout",
            "pyproject.toml",
            all_files,
        )

        # Verify mismatch detection instructions are present
        assert "CRITICAL" in context
        assert "claims changes that are NOT present" in context
        assert "Scope Mismatch" in context
        assert 'Description says "Added authentication"' in context
        assert "flag it as a WARNING" in context


class TestPromptContextUsage:
    """Test that prompts use context appropriately."""

    def test_prompt_includes_pr_context_section(self):
        """Test that user prompt has a dedicated PR context section."""
        from src.utils.prompts import get_user_prompt

        prompt = get_user_prompt(
            file_path="test.py",
            language="python",
            code="def foo(): pass",
            context="## Pull Request Context\n**Title**: Test",
            previous_feedback=None,
        )

        assert "## Pull Request Context" in prompt
        assert "**Title**: Test" in prompt

    def test_prompt_without_context_gracefully_handled(self):
        """Test that prompt works when context is None."""
        from src.utils.prompts import get_user_prompt

        prompt = get_user_prompt(
            file_path="test.py",
            language="python",
            code="def foo(): pass",
            context=None,
            previous_feedback=None,
        )

        # Should still generate valid prompt without errors
        assert "test.py" in prompt
        assert "python" in prompt
        assert "def foo(): pass" in prompt

    def test_prompt_instructions_mention_pr_intent(self):
        from src.utils.prompts.templates import CODE_REVIEW_USER

        # Check that instructions include PR context usage guidance
        assert ("Understand PR Intent" in CODE_REVIEW_USER or 
                "PR Intent" in CODE_REVIEW_USER or 
                "PR intent" in CODE_REVIEW_USER)
        assert ("INTENT" in CODE_REVIEW_USER or 
                "intent" in CODE_REVIEW_USER or 
                "Intent" in CODE_REVIEW_USER)
        assert ("SCOPE" in CODE_REVIEW_USER or "scope" in CODE_REVIEW_USER)
        assert ("ALIGN" in CODE_REVIEW_USER or "align" in CODE_REVIEW_USER or "Align" in CODE_REVIEW_USER)

    def test_prompt_instructions_mention_avoiding_known_issues(self):
        """Test that instructions tell AI not to flag acknowledged issues."""
        from src.utils.prompts.templates import CODE_REVIEW_USER

        assert "DO NOT flag" in CODE_REVIEW_USER or "Do not flag" in CODE_REVIEW_USER
        assert "explicitly explained" in CODE_REVIEW_USER or "acknowledged" in CODE_REVIEW_USER
        assert "intentional" in CODE_REVIEW_USER.lower()

    def test_prompt_instructions_include_alignment_check(self):
        """Test that instructions include checking alignment with PR description."""
        from src.utils.prompts.templates import CODE_REVIEW_USER

        assert "alignment" in CODE_REVIEW_USER.lower() or "align" in CODE_REVIEW_USER.lower()
        assert "matches" in CODE_REVIEW_USER.lower() or "match" in CODE_REVIEW_USER.lower()


class TestContextInReviewWorkflow:
    """Test context usage in the full review workflow."""

    def test_format_pr_context_method_exists(self):
        """Test that _format_pr_context method exists and is callable."""
        config = Mock(spec=Config)
        service = CodeReviewService(config)
        
        # Verify the method exists
        assert hasattr(service, '_format_pr_context')
        assert callable(service._format_pr_context)
        
        # Test it can be called
        result = service._format_pr_context("Test Title", "Test Body", "file.py")
        assert isinstance(result, str)
        assert "Test Title" in result
        assert "Test Body" in result
        assert "file.py" in result


class TestContextImpactOnReview:
    """Test scenarios where context should affect review decisions."""

    def test_context_format_helps_identify_partial_implementation(self):
        """Test that formatted context highlights partial implementations."""
        config = Mock(spec=Config)
        service = CodeReviewService(config)

        pr_body = """## Implementation Status
This is Phase 1 of 3:
- [x] Basic structure
- [ ] Advanced features (Phase 2)
- [ ] Performance optimization (Phase 3)"""
        
        context = service._format_pr_context("Phase 1: Basic structure", pr_body, "module.py")

        assert "partial implementations" in context.lower()
        assert "work-in-progress" in context.lower()
        # The actual PR body should be included
        assert "Phase 1 of 3" in context

    def test_context_format_highlights_known_limitations(self):
        """Test that context helps AI understand acknowledged limitations."""
        config = Mock(spec=Config)
        service = CodeReviewService(config)

        pr_body = """## Known Limitations
- Error handling is basic (will improve in v2)
- No retry logic yet (out of scope for MVP)
- Synchronous calls only (async in next PR)"""
        
        context = service._format_pr_context("MVP implementation", pr_body, "api.py")

        assert "known limitations" in context.lower()
        assert "trade-offs" in context.lower()
        assert "intentional decisions" in context.lower()
        # The limitations should be visible
        assert "Error handling is basic" in context

    def test_context_format_emphasizes_alignment_check(self):
        """Test that context instructs AI to verify alignment."""
        config = Mock(spec=Config)
        service = CodeReviewService(config)

        pr_body = "Add JWT authentication with refresh tokens"
        
        context = service._format_pr_context("Add auth system", pr_body, "auth.py")

        # Should instruct AI to check alignment
        assert "ALIGN" in context
        assert "stated purpose" in context or "stated" in context
        assert "implementation matches" in context or "matches" in context

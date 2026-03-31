"""Prompt loader for managing AI prompts."""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PromptLoader:
    """Manages loading and formatting of AI prompts."""

    def __init__(self, prompts_dir: Path | None = None):
        """Initialize the prompt loader.

        Args:
            prompts_dir: Directory containing prompt templates
        """
        if prompts_dir is None:
            self.prompts_dir = Path(__file__).parent / "templates"
        else:
            self.prompts_dir = Path(prompts_dir)

        if not self.prompts_dir.exists():
            logger.warning(f"Prompts directory not found: {self.prompts_dir}")

    def load_template(self, template_name: str) -> str:
        """Load a prompt template from file.

        Args:
            template_name: Name of the template file (without .txt extension)

        Returns:
            Template content as string

        Raises:
            FileNotFoundError: If template file doesn't exist
        """
        template_path = self.prompts_dir / f"{template_name}.txt"

        if not template_path.exists():
            logger.error(f"Template not found: {template_path}")
            raise FileNotFoundError(f"Template not found: {template_name}")

        return template_path.read_text(encoding="utf-8")

    def format_template(self, template_name: str, **kwargs: Any) -> str:
        """Load and format a prompt template with variables.

        Args:
            template_name: Name of the template file
            **kwargs: Variables to substitute in the template

        Returns:
            Formatted prompt string
        """
        template = self.load_template(template_name)
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing template variable: {e}")
            raise ValueError(f"Missing required template variable: {e}") from e

    def get_system_prompt(self, language: str) -> str:
        """Get the system prompt for code review.

        Args:
            language: Programming language being reviewed

        Returns:
            System prompt string
        """
        try:
            return self.format_template("code_review_system", language=language)
        except FileNotFoundError:
            # Fallback to default if template not found
            logger.warning("Using fallback system prompt")
            return self._default_system_prompt(language)

    def get_user_prompt(
        self,
        file_path: str,
        language: str,
        code: str,
        context: str | None = None,
    ) -> str:
        """Get the user prompt for code review.

        Args:
            file_path: Path to the file being reviewed
            language: Programming language
            code: Code to review
            context: Optional context information

        Returns:
            User prompt string
        """
        try:
            context_section = f"\nContext:\n{context}\n" if context else ""
            return self.format_template(
                "code_review_user",
                file_path=file_path,
                language=language,
                code=code,
                context=context_section,
            )
        except FileNotFoundError:
            logger.warning("Using fallback user prompt")
            return self._default_user_prompt(file_path, language, code, context)

    def get_pr_summary_template(self) -> str:
        """Get the PR summary template.

        Returns:
            PR summary template string
        """
        try:
            return self.load_template("pr_summary")
        except FileNotFoundError:
            logger.warning("Using fallback PR summary template")
            return self._default_pr_summary_template()

    def _default_system_prompt(self, language: str) -> str:
        """Default system prompt fallback."""
        return f"""You are an expert code reviewer specializing in {language}.

Your task is to review code changes and provide constructive, actionable feedback.

Focus on:
1. **Code Quality**: Readability, maintainability, and best practices
2. **Bugs & Logic**: Potential bugs, edge cases, and logic errors
3. **Security**: Security vulnerabilities and data handling issues
4. **Performance**: Performance implications and optimization opportunities
5. **Testing**: Test coverage and testability
6. **Documentation**: Code comments and documentation needs

Provide feedback in this format:
- Use **CRITICAL** for serious issues that must be fixed
- Use **WARNING** for important issues that should be addressed
- Use **SUGGESTION** for improvements and best practices
- Use **PRAISE** for good practices worth highlighting

Be specific, provide examples, and suggest improvements where applicable."""

    def _default_user_prompt(
        self,
        file_path: str,
        language: str,
        code: str,
        context: str | None = None,
    ) -> str:
        """Default user prompt fallback."""
        prompt = f"""Please review the following code changes from file: `{file_path}`

Language: {language}

"""
        if context:
            prompt += f"Context:\n{context}\n\n"

        prompt += f"""Code Changes:
```{language}
{code}
```

Please provide a detailed review with specific line-by-line feedback where applicable."""

        return prompt

    def _default_pr_summary_template(self) -> str:
        """Default PR summary template fallback."""
        return """## AI Code Review Summary

- **Files Reviewed**: {files_reviewed}
- **Total Comments**: {total_comments}
- **Critical Issues**: {critical_count}
- **Warnings**: {warning_count}

{action_message}"""


# Singleton instance
_prompt_loader: PromptLoader | None = None


def get_prompt_loader() -> PromptLoader:
    """Get or create the singleton PromptLoader instance.

    Returns:
        PromptLoader instance
    """
    global _prompt_loader
    if _prompt_loader is None:
        _prompt_loader = PromptLoader()
    return _prompt_loader

from typing import Any

from .templates import TEMPLATES
from .types import PromptTemplate


class PromptLoader:
    """Handles loading and formatting of prompt templates.

    All templates are stored in-memory as constants.
    """

    def load_template(self, template_name: str) -> str:
        return TEMPLATES[template_name]

    def format_template(self, template_name: str, **kwargs: Any) -> str:
        template = self.load_template(template_name)
        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing required template variable: {e}") from e

    def get_system_prompt(self, language: str) -> str:
        return self.format_template(PromptTemplate.CODE_REVIEW_SYSTEM, language=language)

    def get_user_prompt(
        self,
        file_path: str,
        language: str,
        code: str,
        context: str | None = None,
    ) -> str:
        context_section = f"\nContext:\n{context}\n" if context else ""
        return self.format_template(
            PromptTemplate.CODE_REVIEW_USER,
            file_path=file_path,
            language=language,
            code=code,
            context=context_section,
        )

    def get_pr_summary_template(self) -> str:
        return self.load_template(PromptTemplate.PR_SUMMARY)


def get_prompt_loader() -> PromptLoader:
    return PromptLoader()

from .templates import CODE_REVIEW_SYSTEM, CODE_REVIEW_USER, PR_SUMMARY


def get_system_prompt(language: str) -> str:
    return CODE_REVIEW_SYSTEM.format(language=language)


def get_user_prompt(
    file_path: str,
    language: str,
    code: str,
    context: str | None = None,
) -> str:
    context_section = f"\nContext:\n{context}\n" if context else ""
    return CODE_REVIEW_USER.format(
        file_path=file_path,
        language=language,
        code=code,
        context=context_section,
    )


def get_pr_summary_template() -> str:
    return PR_SUMMARY

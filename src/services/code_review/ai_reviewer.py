import json
import logging
from datetime import UTC, datetime

from src.utils.prompts import get_pr_summary_template, get_system_prompt, get_user_prompt
from src.utils.prompts.types import ReviewSeverity

from ..ai import AIClient

logger = logging.getLogger(__name__)

# Prompts require lowercase severities in JSON; the rest of the app uses ReviewSeverity (uppercase).
_SEVERITY_ALIASES: dict[str, ReviewSeverity] = {
    "critical": ReviewSeverity.CRITICAL,
    "warning": ReviewSeverity.WARNING,
    "suggestion": ReviewSeverity.SUGGESTION,
    "praise": ReviewSeverity.PRAISE,
    "info": ReviewSeverity.SUGGESTION,
}

# Lower sorts first: critical → warning → suggestion → praise
_SEVERITY_SORT_ORDER: dict[ReviewSeverity, int] = {
    ReviewSeverity.CRITICAL: 0,
    ReviewSeverity.WARNING: 1,
    ReviewSeverity.SUGGESTION: 2,
    ReviewSeverity.PRAISE: 3,
}


def _sort_comments_by_severity(comments: list[dict]) -> list[dict]:
    return sorted(
        comments,
        key=lambda c: _SEVERITY_SORT_ORDER.get(c.get("severity"), 99),
    )


def _normalize_severity(raw: str | None) -> ReviewSeverity:
    if raw is None:
        return ReviewSeverity.SUGGESTION
    key = str(raw).strip().lower()
    return _SEVERITY_ALIASES.get(key, ReviewSeverity.SUGGESTION)


def _log_ai_response(file_path: str, review_text: str) -> None:
    max_len = 8000
    preview = (
        review_text if len(review_text) <= max_len else review_text[:max_len] + "\n... [truncated]"
    )
    logger.info(
        "AI agent response for %s (%d chars):\n%s",
        file_path,
        len(review_text),
        preview,
    )


class AICodeReviewer:
    def __init__(self, ai_client: AIClient):
        self.ai = ai_client

    def review_code(
        self,
        code: str,
        file_path: str,
        language: str,
        context: str | None = None,
        previous_feedback: str | None = None,
    ) -> dict:
        system_prompt = get_system_prompt(language)
        user_prompt = get_user_prompt(
            file_path=file_path,
            language=language,
            code=code,
            context=context,
            previous_feedback=previous_feedback,
        )

        messages = [{"role": "user", "content": [{"type": "text", "text": user_prompt}]}]

        try:
            logger.info(f"Reviewing {file_path} ({language}) with AI")

            response = self.ai.invoke_model(
                messages=messages,
                system=system_prompt,
            )

            content = response.get("content", [])
            if content and isinstance(content, list):
                review_text = (content[0].get("text") or "").strip()
                _log_ai_response(file_path, review_text)
                if not review_text:
                    logger.warning("AI returned empty text for %s", file_path)
                    return {"file": file_path, "comments": [], "summary": "No review generated"}
                return self._parse_review_response(review_text, file_path)

            logger.warning(
                "Unexpected AI response shape for %s: content=%r",
                file_path,
                type(content).__name__,
            )
            return {"file": file_path, "comments": [], "summary": "No review generated"}

        except Exception as e:
            logger.error(f"Error reviewing {file_path}: {e}")
            return {
                "file": file_path,
                "comments": [],
                "summary": f"Error during review: {str(e)}",
            }

    def review_pull_request(
        self,
        files: list[dict],
        pr_title: str,
        pr_description: str,
    ) -> dict:
        reviews = []
        context = f"PR Title: {pr_title}\nPR Description: {pr_description}"

        for file_info in files:
            file_path = file_info.get("filename", "")
            patch = file_info.get("patch", "")
            language = file_info.get("language", "unknown")

            if not patch:
                continue

            review = self.review_code(
                code=patch,
                file_path=file_path,
                language=language,
                context=context,
            )
            reviews.append(review)

        return {
            "pr_title": pr_title,
            "files_reviewed": len(reviews),
            "reviews": reviews,
            "overall_summary": self._generate_overall_summary(reviews),
        }

    def _parse_json_comments_array(self, data: object, file_path: str) -> list[dict] | None:
        comments_raw: list | None = None
        if isinstance(data, list):
            comments_raw = data
        elif isinstance(data, dict):
            for key in ("comments", "findings", "review", "items"):
                val = data.get(key)
                if isinstance(val, list):
                    comments_raw = val
                    break

        if comments_raw is None:
            return None

        validated_comments: list[dict] = []
        for comment in comments_raw:
            if not isinstance(comment, dict):
                continue
            validated_comments.append(
                {
                    "severity": _normalize_severity(comment.get("severity")),
                    "category": comment.get("category", "general"),
                    "title": comment.get("title", ""),
                    "text": comment.get("text", comment.get("description", "")),
                    "line_number": comment.get("line_number"),
                    "recommendation": comment.get("recommendation", ""),
                    "addresses_previous_issue": comment.get("addresses_previous_issue", False),
                }
            )

        validated_comments = _sort_comments_by_severity(validated_comments)
        logger.info(
            "Successfully parsed %s JSON comment(s) for %s", len(validated_comments), file_path
        )
        return validated_comments

    def _parse_review_response(self, review_text: str, file_path: str) -> dict:
        try:
            cleaned_text = review_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text.split("```json", 1)[1]
            if cleaned_text.startswith("```"):
                cleaned_text = cleaned_text.split("```", 1)[1]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text.rsplit("```", 1)[0]

            cleaned_text = cleaned_text.strip()

            # Prefer parsing the whole payload (object or array); some models wrap the array in an object.
            try:
                parsed = json.loads(cleaned_text)
                validated = self._parse_json_comments_array(parsed, file_path)
                if validated is not None:
                    return {
                        "file": file_path,
                        "comments": validated,
                        "summary": f"Reviewed with {len(validated)} comments",
                    }
            except json.JSONDecodeError:
                pass

            if "[" in cleaned_text and "]" in cleaned_text:
                start = cleaned_text.find("[")
                end = cleaned_text.rfind("]") + 1
                json_str = cleaned_text[start:end]
                comments = json.loads(json_str)
                validated = self._parse_json_comments_array(comments, file_path)
                if validated is not None:
                    return {
                        "file": file_path,
                        "comments": validated,
                        "summary": f"Reviewed with {len(validated)} comments",
                    }

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}. Falling back to text parsing.")
        except Exception as e:
            logger.error(f"Unexpected error parsing JSON: {e}. Falling back to text parsing.")

        # Fallback to text parsing
        logger.info("Using text parsing fallback")
        return self._parse_review_response_text(review_text, file_path)

    def _parse_review_response_text(self, review_text: str, file_path: str) -> dict:
        comments = []
        lines = review_text.split("\n")

        current_comment = None
        for line in lines:
            line = line.strip()
            if not line:
                continue

            if any(
                marker in line.upper() for marker in ["CRITICAL", "WARNING", "SUGGESTION", "PRAISE"]
            ):
                if current_comment:
                    comments.append(current_comment)

                severity = ReviewSeverity.SUGGESTION
                u = line.upper()
                if "CRITICAL" in u:
                    severity = ReviewSeverity.CRITICAL
                elif "WARNING" in u:
                    severity = ReviewSeverity.WARNING
                elif "SUGGESTION" in u:
                    severity = ReviewSeverity.SUGGESTION
                elif "PRAISE" in u:
                    severity = ReviewSeverity.PRAISE

                current_comment = {
                    "severity": severity,
                    "text": line,
                    "category": "general",
                }
            elif current_comment:
                current_comment["text"] += "\n" + line

        if current_comment:
            comments.append(current_comment)

        return {
            "file": file_path,
            "comments": _sort_comments_by_severity(comments),
            "summary": review_text[:500] if len(review_text) > 500 else review_text,
        }

    def _generate_overall_summary(self, reviews: list[dict]) -> str:
        total_comments = sum(len(r.get("comments", [])) for r in reviews)
        critical_count = sum(
            1
            for r in reviews
            for c in r.get("comments", [])
            if c.get("severity") == ReviewSeverity.CRITICAL
        )
        warning_count = sum(
            1
            for r in reviews
            for c in r.get("comments", [])
            if c.get("severity") == ReviewSeverity.WARNING
        )
        suggestion_count = sum(
            1
            for r in reviews
            for c in r.get("comments", [])
            if c.get("severity") == ReviewSeverity.SUGGESTION
        )
        praise_count = sum(
            1
            for r in reviews
            for c in r.get("comments", [])
            if c.get("severity") == ReviewSeverity.PRAISE
        )

        # Determine action message
        if critical_count > 0:
            action_message = (
                "\n⚠️ **Action Required**: Please address the critical issues before merging."
            )
        elif warning_count > 0:
            action_message = "\n⚡ **Recommendations**: Consider addressing the warnings for better code quality."
        else:
            action_message = "\n✅ **Looks Good**: No major issues found!"

        try:
            template = get_pr_summary_template()
            return template.format(
                files_reviewed=len(reviews),
                total_comments=total_comments,
                critical_count=critical_count,
                warning_count=warning_count,
                suggestion_count=suggestion_count,
                praise_count=praise_count,
                action_message=action_message,
                merge_recommendation="Review critical issues and security findings before merging.",
                model_label=self.ai.deployment_name,
                timestamp=datetime.now(UTC).isoformat(),
            )
        except Exception as e:
            logger.error(f"Error formatting PR summary: {e}")
            return f"""## AI Code Review Summary
- **Files Reviewed**: {len(reviews)}
- **Total Comments**: {total_comments}
- **Critical Issues**: {critical_count}
- **Warnings**: {warning_count}
{action_message}"""
        

    def _generate_overal(self, reviews: list[dict]) -> str:
        total_comments = sum(len(r.get("comments", [])) for r in reviews)
        critical_count = sum(
            1
            for r in reviews
            for c in r.get("comments", [])
            if c.get("severity") == ReviewSeverity.CRITICAL
        )
        warning_count = sum(
            1
            for r in reviews
            for c in r.get("comments", [])
            if c.get("severity") == ReviewSeverity.WARNING
        )
        suggestion_count = sum(
            1
            for r in reviews
            for c in r.get("comments", [])
            if c.get("severity") == ReviewSeverity.SUGGESTION
        )
        praise_count = sum(
            1
            for r in reviews
            for c in r.get("comments", [])
            if c.get("severity") == ReviewSeverity.PRAISE
        )

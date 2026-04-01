import json
import logging

from ..utils.prompts import get_system_prompt, get_user_prompt
from .aws import BedrockClient

logger = logging.getLogger(__name__)


class AICodeReviewer:
    def __init__(self, bedrock_client: BedrockClient, model_id: str):
        self.bedrock = bedrock_client
        self.model_id = model_id

    def review_code(
        self,
        code: str,
        file_path: str,
        language: str,
        context: str | None = None,
    ) -> dict:
        system_prompt = get_system_prompt(language)
        user_prompt = get_user_prompt(
            file_path=file_path,
            language=language,
            code=code,
            context=context,
        )

        messages = [{"role": "user", "content": [{"type": "text", "text": user_prompt}]}]

        try:
            logger.info(f"Reviewing {file_path} ({language}) with AI")

            response = self.bedrock.invoke_model(
                messages=messages,
                system=system_prompt,
            )

            content = response.get("content", [])
            if content and isinstance(content, list):
                review_text = content[0].get("text", "")
                return self._parse_review_response(review_text, file_path)

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

    def _parse_review_response(self, review_text: str, file_path: str) -> dict:
        """
        Parse AI review response. Expects JSON format.
        Falls back to text parsing if JSON fails.
        """
        try:
            # Try to parse as JSON first
            # Clean up markdown code blocks if present
            cleaned_text = review_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text.split("```json", 1)[1]
            if cleaned_text.startswith("```"):
                cleaned_text = cleaned_text.split("```", 1)[1]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text.rsplit("```", 1)[0]

            cleaned_text = cleaned_text.strip()

            # Try to find JSON array in the response
            if "[" in cleaned_text and "]" in cleaned_text:
                start = cleaned_text.find("[")
                end = cleaned_text.rfind("]") + 1
                json_str = cleaned_text[start:end]
                comments = json.loads(json_str)

                # Validate structure
                if isinstance(comments, list):
                    # Ensure each comment has required fields
                    validated_comments = []
                    for comment in comments:
                        if isinstance(comment, dict):
                            validated_comments.append(
                                {
                                    "severity": comment.get("severity", "info"),
                                    "category": comment.get("category", "general"),
                                    "title": comment.get("title", ""),
                                    "text": comment.get("text", comment.get("description", "")),
                                    "line_number": comment.get("line_number"),
                                    "recommendation": comment.get("recommendation", ""),
                                }
                            )

                    logger.info(f"Successfully parsed {len(validated_comments)} JSON comments")
                    return {
                        "file": file_path,
                        "comments": validated_comments,
                        "summary": f"Reviewed with {len(validated_comments)} comments",
                    }

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}. Falling back to text parsing.")
        except Exception as e:
            logger.error(f"Unexpected error parsing JSON: {e}. Falling back to text parsing.")

        # Fallback to text parsing
        logger.info("Using text parsing fallback")
        return self._parse_review_response_text(review_text, file_path)

    def _parse_review_response_text(self, review_text: str, file_path: str) -> dict:
        """Fallback text-based parsing when JSON parsing fails."""
        comments = []
        lines = review_text.split("\n")

        current_comment = None
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detect severity markers
            if any(
                marker in line.upper() for marker in ["CRITICAL", "WARNING", "SUGGESTION", "PRAISE"]
            ):
                if current_comment:
                    comments.append(current_comment)

                severity = "info"
                if "CRITICAL" in line.upper():
                    severity = "critical"
                elif "WARNING" in line.upper():
                    severity = "warning"
                elif "SUGGESTION" in line.upper():
                    severity = "suggestion"
                elif "PRAISE" in line.upper():
                    severity = "praise"

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
            "comments": comments,
            "summary": review_text[:500] if len(review_text) > 500 else review_text,
        }

    def _generate_overall_summary(self, reviews: list[dict]) -> str:
        total_comments = sum(len(r.get("comments", [])) for r in reviews)
        critical_count = sum(
            1 for r in reviews for c in r.get("comments", []) if c.get("severity") == "critical"
        )
        warning_count = sum(
            1 for r in reviews for c in r.get("comments", []) if c.get("severity") == "warning"
        )
        suggestion_count = sum(
            1 for r in reviews for c in r.get("comments", []) if c.get("severity") == "suggestion"
        )
        praise_count = sum(
            1 for r in reviews for c in r.get("comments", []) if c.get("severity") == "praise"
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

        # Use prompt template for summary
        try:
            template = self.prompt_loader.get_pr_summary_template()
            return template.format(
                files_reviewed=len(reviews),
                total_comments=total_comments,
                critical_count=critical_count,
                warning_count=warning_count,
                suggestion_count=suggestion_count,
                praise_count=praise_count,
                action_message=action_message,
            )
        except Exception as e:
            logger.error(f"Error formatting PR summary: {e}")
            # Fallback to simple summary
            return f"""## AI Code Review Summary
- **Files Reviewed**: {len(reviews)}
- **Total Comments**: {total_comments}
- **Critical Issues**: {critical_count}
- **Warnings**: {warning_count}
{action_message}"""

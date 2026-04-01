import logging
from datetime import datetime
from pathlib import Path

from ..aws import get_bedrock_client
from ..config import Config
from ..config.constants import EXTENSION_MAP, REVIEW_SEVERITY_EMOJI
from ..database import ReviewRepository, get_db
from ..dependencies import GitHubDependency
from ..utils import has_secrets, scan_for_secrets
from .ai_reviewer import AICodeReviewer

logger = logging.getLogger(__name__)

# File filtering constants
SKIP_FILE_PATTERNS = [
    r".*\.lock$",  # All lock files
    r"package-lock\.json$",
    r"yarn\.lock$",
    r"poetry\.lock$",
    r".*\.min\.js$",  # Minified JS
    r".*\.bundle\.js$",  # Bundled JS
    r"dist/.*",  # Distribution folders
    r"build/.*",  # Build folders
    r"__pycache__/.*",  # Python cache
    r".*\.pyc$",  # Compiled Python
    r"node_modules/.*",  # Node modules
    r"\.git/.*",  # Git internals
]

# Chunking constants
MAX_FILES_PER_BATCH = 10
MAX_TOKENS_PER_FILE = 10_000  # Rough estimate: 40KB of code
MAX_TOKENS_PER_BATCH = 50_000  # Conservative limit to stay within AI context window


class CodeReviewService:
    """Service for orchestrating code reviews on pull requests."""

    def __init__(self, config: Config):
        self.config = config

    async def review_pull_request(
        self,
        repo_full_name: str,
        pr_number: int,
        github: GitHubDependency,
        installation_id: int,
    ) -> None:
        """
        Main entry point for reviewing a pull request.

        Implements:
        - Idempotency (commit SHA checking)
        - Database persistence
        - Error boundaries
        - File chunking
        - Secret scanning
        """
        logger.info(f"Starting code review for {repo_full_name}#{pr_number}")

        pr = github.get_pull_request(installation_id, repo_full_name, pr_number)
        commit_sha = pr.head.sha

        # Use database context
        async with get_db() as db:
            repo = ReviewRepository(db)

            # Check idempotency - already reviewed this commit?
            existing_review = await repo.get_review_by_commit(
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                commit_sha=commit_sha,
            )

            if existing_review:
                logger.info(
                    f"Review already exists for commit {commit_sha[:7]} "
                    f"(session {existing_review.id}), skipping"
                )
                # Post a comment noting we already reviewed
                pr.create_issue_comment(
                    f"🤖 **Already Reviewed**\n\n"
                    f"This commit (`{commit_sha[:7]}`) was already reviewed. "
                    f"See previous review session."
                )
                return

            # Get or create PR record
            db_pr = await repo.get_or_create_pull_request(
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                title=pr.title,
                description=pr.body or "",
                author=pr.user.login if pr.user else None,
            )

            review_session = await repo.create_review_session(
                pr_id=db_pr.id,
                commit_sha=commit_sha,
                trigger_event="pull_request",
            )

            try:
                review_comment = await self._perform_review_with_db(
                    pr=pr,
                    repo_full_name=repo_full_name,
                    pr_number=pr_number,
                    review_session=review_session,
                    repo=repo,
                )

                # Post to GitHub
                pr.create_issue_comment(review_comment)

                # Mark as completed
                await repo.update_review_session(
                    session_id=review_session.id,
                    status="completed",
                    completed_at=datetime.utcnow(),
                )

                logger.info(f"Code review completed for {repo_full_name}#{pr_number}")

            except Exception as e:
                logger.error(f"Error during code review: {str(e)}", exc_info=True)

                # Mark as failed in database
                await repo.update_review_session(
                    session_id=review_session.id,
                    status="failed",
                    error_message=str(e),
                    completed_at=datetime.utcnow(),
                )

                # Still post a comment to GitHub
                pr.create_issue_comment(
                    f"🤖 **AI Code Review Bot**\n\n"
                    f"⚠️ Review encountered an error: {str(e)}\n\n"
                    f"Please try again or contact support."
                )
                raise

    async def _perform_review_with_db(
        self,
        pr,
        repo_full_name: str,
        pr_number: int,
        review_session,
        repo: ReviewRepository,
    ) -> str:
        """Perform AI review with database persistence and error handling."""
        files = list(pr.get_files())
        total_files = len(files)

        logger.info(f"PR has {total_files} files changed")

        review_comment = "🤖 **AI Code Review Bot**\n\n"
        review_comment += f"Analyzing {total_files} file(s) in this PR...\n\n"

        # Check if AI review is enabled
        if not self.config.use_ai_review or not self.config.aws_access_key_id:
            review_comment += "ℹ️ AI review is disabled or not configured.\n"
            return review_comment

        # Filter files (skip lock files, build artifacts, etc.)
        reviewable_files = self._filter_files(files)
        skipped_count = total_files - len(reviewable_files)

        if skipped_count > 0:
            review_comment += (
                f"ℹ️ Skipped {skipped_count} file(s) (lock files, build artifacts, etc.)\n\n"
            )

        if not reviewable_files:
            review_comment += "✅ No reviewable files found.\n"
            return review_comment

        # Check for large PRs
        if len(reviewable_files) > MAX_FILES_PER_BATCH * 5:  # 50+ files
            review_comment += f"⚠️ **Large PR Detected** ({len(reviewable_files)} files)\n\n"
            review_comment += (
                "This PR is quite large. Consider splitting it into smaller, "
                "focused changes for better review quality.\n\n"
            )

        # Chunk files into batches
        batches = self._create_batches(reviewable_files)
        logger.info(f"Split {len(reviewable_files)} files into {len(batches)} batches")

        # Initialize counters
        files_reviewed = 0
        files_failed = 0
        files_with_secrets = 0
        all_comments = []

        # Process each batch with error boundaries
        bedrock = get_bedrock_client()
        ai_reviewer = AICodeReviewer(bedrock, self.config.bedrock_model_id)

        for batch_idx, batch in enumerate(batches, 1):
            logger.info(f"Processing batch {batch_idx}/{len(batches)} ({len(batch)} files)")

            for file in batch:
                try:
                    # Check for secrets
                    patch_content = file.patch or ""
                    if has_secrets(patch_content):
                        secrets = scan_for_secrets(patch_content)
                        logger.warning(f"Secrets detected in {file.filename}: {secrets}")

                        review_comment += f"### 🚨 {file.filename}\n\n"
                        review_comment += (
                            "**CRITICAL**: Potential secrets detected in this file!\n"
                            "- Do NOT merge this PR\n"
                            "- Remove all secrets and use environment variables\n"
                            f"- Detected: {', '.join(s.secret_type for s in secrets)}\n\n"
                        )

                        files_with_secrets += 1
                        files_reviewed += 1
                        continue

                    # Perform AI review
                    file_ext = Path(file.filename).suffix
                    language = EXTENSION_MAP.get(file_ext, "unknown")

                    context = f"PR Title: {pr.title}\nPR Description: {pr.body or ''}"

                    review = ai_reviewer.review_code(
                        code=patch_content,
                        file_path=file.filename,
                        language=language,
                        context=context,
                    )

                    # Store in database
                    file_review = await repo.create_file_review(
                        session_id=review_session.id,
                        file_path=file.filename,
                        language=language,
                        file_content=patch_content,
                        summary=review.get("summary", ""),
                        status="success",
                        lines_added=file.additions,
                        lines_deleted=file.deletions,
                    )

                    # Store comments
                    for comment in review.get("comments", []):
                        await repo.create_review_comment(
                            file_review_id=file_review.id,
                            severity=comment.get("severity", "info"),
                            description=comment.get("text", ""),
                            title=comment.get("title"),
                        )
                        all_comments.append(comment)

                    files_reviewed += 1

                except Exception as e:
                    logger.error(f"Failed to review {file.filename}: {str(e)}", exc_info=True)
                    files_failed += 1

                    # Store failed file in database
                    await repo.create_file_review(
                        session_id=review_session.id,
                        file_path=file.filename,
                        language="unknown",
                        file_content="",
                        summary=f"Review failed: {str(e)}",
                        status="failed",
                    )

        # Update session statistics
        critical_count = sum(1 for c in all_comments if c.get("severity") == "critical")
        warning_count = sum(1 for c in all_comments if c.get("severity") == "warning")
        suggestion_count = sum(1 for c in all_comments if c.get("severity") == "suggestion")
        praise_count = sum(1 for c in all_comments if c.get("severity") == "praise")

        await repo.update_review_session(
            session_id=review_session.id,
            files_reviewed=files_reviewed,
            files_failed=files_failed,
            total_comments=len(all_comments),
            critical_count=critical_count,
            warning_count=warning_count,
            suggestion_count=suggestion_count,
            praise_count=praise_count,
        )

        # Generate summary
        if files_with_secrets > 0:
            review_comment += "## ⛔ Review Summary\n\n"
            review_comment += (
                f"**CRITICAL**: {files_with_secrets} file(s) contain potential secrets!\n"
            )
            review_comment += "**Action Required**: Remove all secrets before merging.\n\n"
        elif critical_count > 0:
            review_comment += "## ⚠️ Review Summary\n\n"
            review_comment += (
                f"Found {critical_count} critical issue(s) that must be addressed.\n\n"
            )
        elif warning_count > 0:
            review_comment += "## 📝 Review Summary\n\n"
            review_comment += f"Found {warning_count} warning(s) to consider.\n\n"
        elif suggestion_count > 0:
            review_comment += "## 💡 Review Summary\n\n"
            review_comment += f"Found {suggestion_count} suggestion(s) for improvement.\n\n"
        else:
            review_comment += "## ✅ Review Summary\n\n"
            review_comment += "No issues found. Code looks good!\n\n"

        # Add detailed results grouped by file
        review_comment += self._format_review_results(all_comments)

        # Add failure notice if any
        if files_failed > 0:
            review_comment += f"\n\n⚠️ Note: {files_failed} file(s) failed to review.\n"

        logger.info(
            f"Review completed: {files_reviewed} reviewed, {files_failed} failed, "
            f"{len(all_comments)} comments"
        )

        return review_comment

    def _filter_files(self, files) -> list:
        """Filter out files that should not be reviewed."""
        import re

        filtered = []
        for file in files:
            # Skip if matches any skip pattern
            should_skip = any(
                re.match(pattern, file.filename, re.IGNORECASE) for pattern in SKIP_FILE_PATTERNS
            )

            if not should_skip and file.patch:  # Must have a patch
                filtered.append(file)
            else:
                logger.debug(f"Skipping file: {file.filename}")

        return filtered

    def _create_batches(self, files) -> list[list]:
        """Create batches of files for processing."""
        batches = []
        current_batch = []
        current_tokens = 0

        for file in files:
            # Rough token estimate: 4 chars ≈ 1 token
            file_tokens = len(file.patch or "") // 4

            # Start new batch if limits exceeded
            if (
                len(current_batch) >= MAX_FILES_PER_BATCH
                or current_tokens + file_tokens > MAX_TOKENS_PER_BATCH
            ):
                if current_batch:
                    batches.append(current_batch)
                current_batch = [file]
                current_tokens = file_tokens
            else:
                current_batch.append(file)
                current_tokens += file_tokens

        if current_batch:
            batches.append(current_batch)

        return batches

    def _format_review_results(self, all_comments: list[dict]) -> str:
        """Format review comments into markdown."""
        if not all_comments:
            return ""

        # Group comments by severity
        by_severity = {}
        for comment in all_comments:
            severity = comment.get("severity", "info")
            if severity not in by_severity:
                by_severity[severity] = []
            by_severity[severity].append(comment)

        result = "## 📋 Detailed Findings\n\n"

        # Order: critical, warning, suggestion, praise
        for severity in ["critical", "warning", "suggestion", "praise"]:
            if severity in by_severity:
                emoji = REVIEW_SEVERITY_EMOJI.get(severity, "📌")
                comments = by_severity[severity]

                result += f"### {emoji} {severity.title()} ({len(comments)})\n\n"

                for comment in comments:
                    result += f"{comment.get('text', '')}\n\n"

        return result

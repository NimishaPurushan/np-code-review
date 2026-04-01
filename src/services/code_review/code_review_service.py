import logging
from datetime import datetime
from pathlib import Path

from ...config import Config
from ...database import ReviewRepository, get_db
from ...dependencies import get_bedrock_client
from ...services.github import GithubClient
from ...utils import has_secrets, scan_for_secrets
from ...utils.ignore_patterns import IGNORE_PATTERNS
from ...utils.prompts.types import ReviewSeverity
from .ai_reviewer import AICodeReviewer
from .constants import (
    EXTENSION_MAP,
    MAX_FILES_PER_BATCH,
    MAX_TOKENS_PER_BATCH,
    MAX_TOKENS_PER_FILE,
    REVIEW_SEVERITY_EMOJI,
)

logger = logging.getLogger(__name__)


class CodeReviewService:
    """Service for orchestrating code reviews on pull requests."""

    def __init__(self, config: Config):
        self.config = config

    def _format_pr_context(
        self, pr_title: str, pr_body: str | None, file_path: str, all_files: list[str] = None
    ) -> str:
        body = pr_body or "No description provided"
        
        files_section = ""
        if all_files:
            files_list = "\n".join(f"  - {f}" for f in all_files[:20])
            if len(all_files) > 20:
                files_list += f"\n  ... and {len(all_files) - 20} more files"
            files_section = f"""
**All Files Changed in This PR**:
{files_list}
"""
        
        formatted_context = f"""## Pull Request Context

**Title**: {pr_title}

**Description**:
{body}
{files_section}
**File Being Reviewed**: {file_path}

### Review Context Instructions:
- Use the PR title and description to understand the INTENT and SCOPE of these changes
- **CRITICAL**: Check if the PR description claims changes that are NOT present in the file list above
  - Example: Description says "Added authentication" but no auth-related files are changed
  - Example: Description mentions multiple features but only config files changed
- If the PR description mentions known limitations, trade-offs, or intentional decisions, DO NOT flag them as issues
- Check if the code changes ALIGN with the stated purpose in the description
- Consider whether the implementation matches the scope described
- Look for partial implementations or work-in-progress items mentioned in the description
- If previous feedback exists, verify if mentioned issues have been addressed
- **Scope Mismatch**: If you notice the changed files don't match what the description claims, flag it as a WARNING"""
        
        return formatted_context

    async def review_pull_request(
        self,
        repo_full_name: str,
        pr_number: int,
        github: GithubClient,
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
                    github=github,
                    installation_id=installation_id,
                    commit_sha=commit_sha,
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
        github: GithubClient,
        installation_id: int,
        commit_sha: str,
    ) -> str:
        files, previous_file_reviews, unchanged_with_issues = await self._get_incremental_files(
            pr, repo_full_name, pr_number, commit_sha, repo, github, installation_id
        )
        
        total_files = len(files)

        logger.info(f"PR has {total_files} files to review")

        review_comment = "🤖 **AI Code Review Bot**\n\n"
        
        if previous_file_reviews:
            review_comment += "📊 **Incremental Review** - Analyzing changes since last review\n\n"
        
        review_comment += f"Analyzing {total_files} file(s) in this PR...\n\n"

        if not self.config.USE_AI_REVIEW:
            review_comment += "ℹ️ AI review is disabled or not configured.\n"
            return review_comment

        # Filter files (skip lock files, build artifacts, etc.)
        reviewable_files, skipped_patterns, skipped_large = self._filter_files(files)

        if len(skipped_patterns) > 0:
            review_comment += (
                f"ℹ️ Skipped {len(skipped_patterns)} file(s) (lock files, build artifacts, etc.)\n\n"
            )

        if len(skipped_large) > 0:
            review_comment += f"⚠️ Skipped {len(skipped_large)} file(s) due to large size (>{MAX_TOKENS_PER_FILE:,} tokens):\n"
            for file_info in skipped_large:
                review_comment += (
                    f"  - `{file_info['filename']}` (~{file_info['tokens']:,} tokens)\n"
                )
            review_comment += "\n"

        if len(unchanged_with_issues) > 0:
            review_comment += f"📋 **Unchanged Files with Existing Issues** ({len(unchanged_with_issues)} file(s)):\n"
            review_comment += "_These files were not modified in this commit but have unresolved issues from previous reviews._\n\n"
            for file_info in unchanged_with_issues:
                severity_counts = {}
                for comment in file_info["comments"]:
                    severity = comment["severity"]
                    severity_counts[severity] = severity_counts.get(severity, 0) + 1
                
                severity_summary = ", ".join(
                    f"{count} {severity.lower()}" for severity, count in severity_counts.items()
                )
                review_comment += f"  - `{file_info['filename']}` ({severity_summary})\n"
            review_comment += "\n"

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

        # Extract all file names for context
        all_file_names = [f.filename for f in reviewable_files]

        files_reviewed = 0
        files_failed = 0
        files_with_secrets = 0
        all_comments = []

        bedrock = get_bedrock_client()
        ai_reviewer = AICodeReviewer(bedrock)

        previous_comments = github.get_bot_previous_comments(
            installation_id, repo_full_name, pr_number
        )
        previous_feedback = github.format_previous_feedback(previous_comments)
        logger.info(f"Retrieved {len(previous_comments)} previous bot comments for context")

        for batch_idx, batch in enumerate(batches, 1):
            logger.info(f"Processing batch {batch_idx}/{len(batches)} ({len(batch)} files)")

            for file in batch:
                try:
                    # Check for secrets
                    patch_content = file.patch or ""
                    if has_secrets(patch_content):
                        secrets = scan_for_secrets(patch_content)
                        logger.warning(f"Secrets detected in {file.filename}: {secrets}")

                        # Post inline comments on specific lines where secrets were found
                        line_mapping = self._parse_diff_line_numbers(patch_content)
                        for secret in secrets:
                            # Map the line number from patch to file line number
                            file_line = line_mapping.get(secret.line_number)
                            if file_line:
                                try:
                                    comment_body = (
                                        f"🚨 **Potential Secret Detected - Please Review**\n\n"
                                        f"**Type**: {secret.type}\n"
                                        f"**Confidence**: {secret.confidence:.0%}\n\n"
                                        f"⚠️ **Action Required**:\n"
                                        f"- Do NOT merge this code with secrets\n"
                                        f"- Remove the secret and use environment variables\n"
                                        f"- Rotate the secret if it was already committed\n"
                                    )
                                    github.create_review_comment(
                                        installation_id=installation_id,
                                        repo_full_name=repo_full_name,
                                        pr_number=pr_number,
                                        body=comment_body,
                                        commit_id=commit_sha,
                                        path=file.filename,
                                        line=file_line,
                                    )
                                    logger.info(
                                        f"Posted inline secret comment on {file.filename}:{file_line}"
                                    )
                                except Exception as e:
                                    logger.error(
                                        f"Failed to post inline comment for secret: {str(e)}",
                                        exc_info=True,
                                    )

                        review_comment += f"### 🚨 {file.filename}\n\n"
                        review_comment += (
                            "**CRITICAL**: Potential secrets detected in this file!\n"
                            "- Do NOT merge this PR\n"
                            "- Remove all secrets and use environment variables\n"
                            f"- Detected: {', '.join(s.type for s in secrets)}\n"
                            f"- {len(secrets)} secret(s) found with inline comments\n\n"
                        )

                        files_with_secrets += 1
                        files_reviewed += 1
                        continue

                    # Perform AI review
                    file_ext = Path(file.filename).suffix
                    language = EXTENSION_MAP.get(file_ext, "unknown")

                    context = self._format_pr_context(
                        pr.title, pr.body, file.filename, all_file_names
                    )

                    review = ai_reviewer.review_code(
                        code=patch_content,
                        file_path=file.filename,
                        language=language,
                        context=context,
                        previous_feedback=previous_feedback,
                    )

                    # Store in database
                    file_review = await repo.create_file_review(
                        session_id=review_session.id,
                        file_path=file.filename,
                        language=language,
                        file_content=patch_content,
                        summary=review.get("summary", ReviewSeverity.SUGGESTION),
                        status="success",
                        lines_added=file.additions,
                        lines_deleted=file.deletions,
                    )

                    # Store comments
                    for comment in review.get("comments", []):
                        await repo.create_review_comment(
                            file_review_id=file_review.id,
                            severity=comment.get("severity", ReviewSeverity.SUGGESTION),
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
        critical_count = sum(
            1 for c in all_comments if c.get("severity") == ReviewSeverity.CRITICAL
        )
        warning_count = sum(1 for c in all_comments if c.get("severity") == ReviewSeverity.WARNING)
        suggestion_count = sum(
            1 for c in all_comments if c.get("severity") == ReviewSeverity.SUGGESTION
        )
        praise_count = sum(1 for c in all_comments if c.get("severity") == ReviewSeverity.PRAISE)

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

    async def _get_incremental_files(
        self,
        pr,
        repo_full_name: str,
        pr_number: int,
        current_commit: str,
        repo: ReviewRepository,
        github: GithubClient,
        installation_id: int,
    ) -> tuple[list, dict, list]:
        last_review = await repo.get_last_reviewed_commit(
            repo_full_name, pr_number, before_commit=current_commit
        )

        if not last_review:
            logger.info("No previous review found - reviewing all PR files")
            all_files = list(pr.get_files())
            return all_files, {}, []

        last_commit = last_review.commit_sha
        logger.info(
            f"Found previous review at commit {last_commit[:7]}, identifying incremental changes"
        )

        try:
            changed_files = github.compare_commits(
                installation_id, repo_full_name, last_commit, current_commit
            )
            changed_filenames = {f.filename for f in changed_files}
            logger.info(
                f"Identified {len(changed_filenames)} file(s) changed since last review"
            )

            all_pr_files = list(pr.get_files())

            files_to_review = [f for f in all_pr_files if f.filename in changed_filenames]

            unchanged_files = [f for f in all_pr_files if f.filename not in changed_filenames]

            previous_file_reviews = await repo.get_reviewed_files_from_session(last_review.id)

            unchanged_with_issues = []
            for file in unchanged_files:
                if file.filename in previous_file_reviews:
                    file_data = previous_file_reviews[file.filename]
                    if file_data["comment_count"] > 0:
                        unchanged_with_issues.append(
                            {
                                "filename": file.filename,
                                "comment_count": file_data["comment_count"],
                                "comments": file_data["comments"],
                            }
                        )

            logger.info(
                f"Incremental review: {len(files_to_review)} to review, "
                f"{len(unchanged_with_issues)} unchanged with existing issues"
            )

            return files_to_review, previous_file_reviews, unchanged_with_issues

        except Exception as e:
            logger.warning(f"Error comparing commits, falling back to full review: {e}")
            all_files = list(pr.get_files())
            return all_files, {}, []

    def _filter_files(self, files) -> tuple[list, list, list]:
        """Filter files and return (reviewable_files, skipped_by_pattern, skipped_by_size)."""
        filtered = []
        skipped_patterns = []
        skipped_large = []

        for file in files:
            should_skip = any(pattern.match(file.filename) for pattern in IGNORE_PATTERNS)

            if should_skip or not file.patch:
                logger.debug(f"Skipping file by pattern: {file.filename}")
                skipped_patterns.append(file.filename)
                continue

            # Check file size (rough token estimate: 4 chars ≈ 1 token)
            file_tokens = len(file.patch) // 4

            if file_tokens > MAX_TOKENS_PER_FILE:
                logger.warning(
                    f"Skipping large file: {file.filename} "
                    f"(~{file_tokens:,} tokens > {MAX_TOKENS_PER_FILE:,} limit)"
                )
                skipped_large.append({"filename": file.filename, "tokens": file_tokens})
                continue

            filtered.append(file)

        return filtered, skipped_patterns, skipped_large

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

    def _parse_diff_line_numbers(self, patch: str) -> dict[int, int]:
        line_mapping = {}
        current_new_line = 0
        patch_line_num = 0

        for line in patch.splitlines():
            patch_line_num += 1

            # Parse hunk headers like: @@ -10,7 +10,8 @@
            if line.startswith("@@"):
                # Extract the new file starting line number
                parts = line.split("+")[1].split(" ")[0]
                current_new_line = (
                    int(parts.split(",")[0]) - 1
                )  # -1 because we increment before mapping
                continue

            # For added lines (lines starting with +), map patch line to file line
            if line.startswith("+"):
                current_new_line += 1
                line_mapping[patch_line_num] = current_new_line
            # Context lines (no prefix) also count in the new file
            elif not line.startswith("-"):
                current_new_line += 1

        return line_mapping

    def _format_review_results(self, all_comments: list[dict]) -> str:
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

        for severity in {ReviewSeverity.CRITICAL, ReviewSeverity.WARNING, ReviewSeverity.SUGGESTION, ReviewSeverity.PRAISE}:
            if severity in by_severity:
                emoji = REVIEW_SEVERITY_EMOJI.get(severity, "📌")
                comments = by_severity[severity]

                result += f"### {emoji} {severity.title()} ({len(comments)})\n\n"

                for comment in comments:
                    result += f"{comment.get('text', '')}\n\n"

        return result

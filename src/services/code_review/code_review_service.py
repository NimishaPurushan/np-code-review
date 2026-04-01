import logging
from datetime import datetime
from pathlib import Path

from ...config import Config
from ...database import ReviewRepository, get_db
from ...dependencies import get_ai_client
from ...services.github import GithubClient
from ...utils import has_secrets, scan_for_secrets
from ...utils.ignore_patterns import IGNORE_PATTERNS, UNWANTED_FILE_PATTERNS
from ...utils.ignore_patterns.gitignore import parse_gitignore_spec, path_is_ignored_by_spec
from ...utils.prompts.types import ReviewSeverity
from ...utils.secret_scanner import SecretMatch
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

    def _load_root_gitignore_spec(
        self,
        github: GithubClient,
        installation_id: int,
        repo_full_name: str,
        ref: str,
    ):
        raw = github.try_get_file_text(installation_id, repo_full_name, ".gitignore", ref)
        if not raw:
            return None
        spec = parse_gitignore_spec(raw)
        if spec:
            logger.info(
                "Loaded root .gitignore for %s @ %s",
                repo_full_name,
                ref[:7] if ref else "?",
            )
        return spec

    @staticmethod
    def _unique_files_by_filename(files: list) -> list:
        by_name: dict[str, object] = {}
        for f in files:
            by_name.setdefault(f.filename, f)
        return list(by_name.values())

    def _group_secrets_by_mapped_file_line(
        self,
        secrets: list[SecretMatch],
        line_mapping: dict[int, int],
    ) -> tuple[dict[int, list[SecretMatch]], list[SecretMatch]]:
        groups: dict[int, list[SecretMatch]] = {}
        unmapped: list[SecretMatch] = []
        for s in secrets:
            file_line = line_mapping.get(s.line_number)
            if file_line is None:
                unmapped.append(s)
                continue
            groups.setdefault(file_line, []).append(s)
        return groups, unmapped

    def _post_review_inline_warnings(
        self,
        *,
        files: list,
        commit_sha: str,
        installation_id: int,
        repo_full_name: str,
        pr_number: int,
        github: GithubClient,
        comment_body: str,
        log_ok: str,
    ) -> None:
        for file in self._unique_files_by_filename(files):
            filename = file.filename
            try:
                patch_content = file.patch or ""
                line_mapping = self._parse_diff_line_numbers(patch_content)
                first_line = min(line_mapping.values()) if line_mapping else None
                github.create_review_comment(
                    installation_id=installation_id,
                    repo_full_name=repo_full_name,
                    pr_number=pr_number,
                    body=comment_body,
                    commit_id=commit_sha,
                    path=filename,
                    line=first_line,
                )
                logger.info(log_ok, filename)
            except Exception as e:
                logger.error(
                    "Failed to post inline comment for %s: %s",
                    filename,
                    str(e),
                    exc_info=True,
                )

    async def review_pull_request(
        self,
        repo_full_name: str,
        pr_number: int,
        github: GithubClient,
        installation_id: int,
    ) -> None:
        logger.info(f"Starting code review for {repo_full_name}#{pr_number}")

        pr = github.get_pull_request(installation_id, repo_full_name, pr_number)
        commit_sha = pr.head.sha

        async with get_db() as db:
            repo = ReviewRepository(db)

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
                skip_msg = (
                    f"🤖 **Already Reviewed**\n\n"
                    f"This commit (`{commit_sha[:7]}`) was already reviewed. "
                    f"See previous review session."
                )
                pr.create_issue_comment(skip_msg)
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

                pr.create_issue_comment(review_comment)

                await repo.update_review_session(
                    session_id=review_session.id,
                    status="completed",
                    completed_at=datetime.utcnow(),
                )

                logger.info(f"Code review completed for {repo_full_name}#{pr_number}")

            except Exception as e:
                logger.error(f"Error during code review: {str(e)}", exc_info=True)

                await repo.update_review_session(
                    session_id=review_session.id,
                    status="failed",
                    error_message=str(e),
                    completed_at=datetime.utcnow(),
                )

                err_comment = (
                    f"🤖 **AI Code Review Bot**\n\n"
                    f"⚠️ Review encountered an error: {str(e)}\n\n"
                    f"Please try again or contact support."
                )
                pr.create_issue_comment(err_comment)
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

        if unchanged_with_issues:
            logger.info(
                f"Re-scanning {len(unchanged_with_issues)} unchanged file(s) with previous issues"
            )
            verified_issues = []
            for file_info in unchanged_with_issues:
                try:
                    file_content = github.get_file_content(
                        installation_id, repo_full_name, file_info["filename"], ref=commit_sha
                    )

                    # Check if secrets still exist
                    if has_secrets(file_content):
                        secrets = scan_for_secrets(file_content)
                        logger.warning(
                            f"Secrets still present in unchanged file {file_info['filename']}: {secrets}"
                        )
                        file_info["current_secrets"] = secrets
                        verified_issues.append(file_info)
                    else:
                        logger.info(
                            f"Previously flagged file {file_info['filename']} no longer has secrets - issue resolved!"
                        )
                except Exception as e:
                    logger.error(f"Failed to re-scan {file_info['filename']}: {e}", exc_info=True)
                    verified_issues.append(file_info)

            unchanged_with_issues = verified_issues
            logger.info(f"Verified {len(unchanged_with_issues)} file(s) still have issues")

        total_files = len(files)

        logger.info(f"PR has {total_files} files to review")

        review_comment = "🤖 **AI Code Review Bot**\n\n"

        if previous_file_reviews:
            review_comment += "📊 **Incremental Review** - Analyzing changes since last review\n\n"

        review_comment += f"Analyzing {total_files} file(s) in this PR...\n\n"

        gitignore_spec = self._load_root_gitignore_spec(
            github, installation_id, repo_full_name, commit_sha
        )
        reviewable_files, skipped_patterns, skipped_large, unwanted_files, gitignored_files = (
            self._filter_files(files, gitignore_spec)
        )

        if len(unwanted_files) > 0:
            review_comment += (
                f"## ⚠️ **Unwanted Files Detected** ({len(unwanted_files)} file(s)):\n\n"
            )
            for file in unwanted_files:
                review_comment += f"  - `{file.filename}` (compiled/binary or generated)\n"
            review_comment += (
                "\n_Why and how to fix: **pull request review comments** on each file above "
                "(on a changed line when the diff has one; otherwise a whole-file comment for binaries)._"
                "\n\n"
            )

            unwanted_comment_body = (
                "⚠️ **Unwanted File - Please Remove**\n\n"
                "This file should **NOT** be committed to the repository.\n\n"
                "**Action Required**:\n"
                "- Remove this file from the commit\n"
                "- Ensure `.gitignore` excludes it if appropriate\n"
            )
            self._post_review_inline_warnings(
                files=unwanted_files,
                commit_sha=commit_sha,
                installation_id=installation_id,
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                github=github,
                comment_body=unwanted_comment_body,
                log_ok="Posted inline warning comment for unwanted file: %s",
            )

        if len(gitignored_files) > 0:
            review_comment += f"## 📎 **Tracked Files Matching Root `.gitignore`** ({len(gitignored_files)} file(s)):\n\n"
            for file in gitignored_files:
                review_comment += f"  - `{file.filename}`\n"
            review_comment += (
                "\n_Context and next steps: **pull request review comments** on each path "
                "(line or whole-file if there is no mappable diff line)._ "
                "_Nested `.gitignore` files are not loaded — only the repo root file is used._\n\n"
            )

            gitignore_comment_body = (
                "⚠️ **Matches repository `.gitignore`**\n\n"
                "This path matches a pattern in the **root** `.gitignore` for this branch. "
                "Normally Git would not add it unless forced.\n\n"
                "**Action**: Remove from version control if accidental, or adjust `.gitignore` "
                "if the rule is wrong.\n\n"
                "_Nested `.gitignore` files are not loaded yet — only the repo root file is used._"
            )
            self._post_review_inline_warnings(
                files=gitignored_files,
                commit_sha=commit_sha,
                installation_id=installation_id,
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                github=github,
                comment_body=gitignore_comment_body,
                log_ok="Posted inline .gitignore match warning for: %s",
            )

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
            secrets_count = sum(1 for f in unchanged_with_issues if "current_secrets" in f)
            if secrets_count > 0:
                review_comment += f"## 🚨 **CRITICAL: Unchanged Files with Unresolved Secrets** ({secrets_count} file(s)):\n"
                review_comment += "_These files were **NOT changed** in this commit but **STILL CONTAIN SECRETS** from previous commits._\n\n"
                review_comment += "⛔ **Action Required**:\n"
                review_comment += "- Remove all secrets and use environment variables\n"
                review_comment += "- Do NOT merge this PR\n\n"

                for file_info in unchanged_with_issues:
                    if "current_secrets" in file_info:
                        secrets = file_info["current_secrets"]
                        secret_types = ", ".join(s.type for s in secrets)
                        review_comment += f"  - 🚨 `{file_info['filename']}` - {len(secrets)} secret(s): {secret_types}\n"
                review_comment += "\n"

                other_issues = [f for f in unchanged_with_issues if "current_secrets" not in f]
                if other_issues:
                    review_comment += (
                        f"📋 **Other Unchanged Files with Issues** ({len(other_issues)} file(s)):\n"
                    )
                    for file_info in other_issues:
                        severity_counts = {}
                        for comment in file_info["comments"]:
                            severity = comment["severity"]
                            severity_counts[severity] = severity_counts.get(severity, 0) + 1

                        severity_summary = ", ".join(
                            f"{count} {severity.lower()}"
                            for severity, count in severity_counts.items()
                        )
                        review_comment += f"  - `{file_info['filename']}` ({severity_summary})\n"
                    review_comment += "\n"
            else:
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

        batches = self._create_batches(reviewable_files)
        logger.info(f"Split {len(reviewable_files)} files into {len(batches)} batches")

        # Extract all file names for context
        all_file_names = [f.filename for f in reviewable_files]

        files_reviewed = 0
        files_failed = 0
        files_with_secrets = 0
        all_comments = []

        ai_client = get_ai_client()
        ai_reviewer = AICodeReviewer(ai_client)

        previous_comments = github.get_bot_previous_comments(
            installation_id, repo_full_name, pr_number
        )
        previous_feedback = github.format_previous_feedback(previous_comments)
        logger.info(f"Retrieved {len(previous_comments)} previous bot comments for context")

        for batch_idx, batch in enumerate(batches, 1):
            logger.info(f"Processing batch {batch_idx}/{len(batches)} ({len(batch)} files)")

            for file in batch:
                try:
                    patch_content = file.patch or ""
                    secrets = scan_for_secrets(patch_content)
                    secret_line_groups: dict[int, list[SecretMatch]] = {}

                    if secrets:
                        logger.warning("Secrets detected in %s: %s", file.filename, secrets)
                        line_mapping = self._parse_diff_line_numbers(patch_content)
                        secret_line_groups, unmapped = self._group_secrets_by_mapped_file_line(
                            secrets, line_mapping
                        )
                        if unmapped:
                            logger.debug(
                                "Secret match(es) on unmapped patch lines for %s: %s",
                                file.filename,
                                [m.type for m in unmapped],
                            )

                        for file_line in sorted(secret_line_groups):
                            group = secret_line_groups[file_line]
                            types_str = ", ".join(sorted({m.type for m in group}))
                            conf = max(m.confidence for m in group)
                            comment_body = (
                                f"🚨 **Potential Secret(s) Detected**\n\n"
                                f"**Type(s)**: {types_str}\n"
                                f"**Pattern match(es) on this line**: {len(group)}\n"
                                f"**Confidence**: {conf:.0%}\n\n"
                                f"⚠️ **Action Required**:\n"
                                f"- Do NOT merge this code with secrets\n"
                                f"- Remove the secret and use environment variables\n"
                                f"- Rotate the secret if it was already committed\n"
                            )
                            try:
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
                                    "Posted inline secret comment on %s:%s",
                                    file.filename,
                                    file_line,
                                )
                            except Exception as e:
                                logger.error(
                                    "Failed to post inline comment for secret: %s",
                                    str(e),
                                    exc_info=True,
                                )

                        types = ", ".join(sorted({s.type for s in secrets}))
                        n_inlines = len(secret_line_groups)
                        inline_part = f", {n_inlines} inline comment(s)" if n_inlines else ""
                        review_comment += f"### 🚨 `{file.filename}`\n\n"
                        review_comment += (
                            f"Potential secrets: **{types}** ({len(secrets)} pattern match(es)"
                            f"{inline_part}). "
                            f"**Inline review comments** on this file have confidence and remediation steps — "
                            f"do not merge until addressed.\n\n"
                        )

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

                    summary_parts: list[str] = []
                    if secrets:
                        summary_parts.append(
                            "CRITICAL: "
                            f"{len(secrets)} secret(s) — {', '.join(sorted({s.type for s in secrets}))}"
                        )
                    ai_summary = review.get("summary")
                    if ai_summary:
                        summary_parts.append(str(ai_summary))
                    combined_summary = (
                        " | ".join(summary_parts)
                        if summary_parts
                        else str(ReviewSeverity.SUGGESTION)
                    )

                    file_review = await repo.create_file_review(
                        session_id=review_session.id,
                        file_path=file.filename,
                        language=language,
                        file_content=patch_content[:1000],
                        summary=combined_summary,
                        status="success",
                        lines_added=file.additions,
                        lines_deleted=file.deletions,
                    )

                    if secrets:
                        for secret in secrets:
                            await repo.create_review_comment(
                                file_review_id=file_review.id,
                                severity=ReviewSeverity.CRITICAL,
                                description=f"Potential {secret.type} detected",
                                category="security",
                                line_number=secret.line_number,
                            )
                        files_with_secrets += 1

                    commentable_lines = self._collect_commentable_new_file_lines(patch_content)
                    for comment in review.get("comments", []):
                        raw_ln = comment.get("line_number")
                        resolved_ln = self._resolve_ai_inline_line(raw_ln, commentable_lines)
                        await repo.create_review_comment(
                            file_review_id=file_review.id,
                            severity=comment.get("severity", ReviewSeverity.SUGGESTION),
                            description=comment.get("text", ""),
                            title=comment.get("title"),
                            line_number=resolved_ln if resolved_ln is not None else raw_ln,
                            category=comment.get("category"),
                            recommendation=comment.get("recommendation"),
                        )
                        all_comments.append(comment)

                        body = self._format_ai_inline_body(comment)
                        try:
                            github.create_review_comment(
                                installation_id=installation_id,
                                repo_full_name=repo_full_name,
                                pr_number=pr_number,
                                body=body,
                                commit_id=commit_sha,
                                path=file.filename,
                                line=resolved_ln,
                            )
                            comment["_posted_inline"] = True
                            logger.info(
                                "Posted AI review comment on %s (%s)",
                                file.filename,
                                f"line {resolved_ln}" if resolved_ln is not None else "file",
                            )
                        except Exception as e:
                            logger.error(
                                "Failed to post AI inline review on %s: %s",
                                file.filename,
                                str(e),
                                exc_info=True,
                            )

                    files_reviewed += 1

                except Exception as e:
                    logger.error(f"Failed to review {file.filename}: {str(e)}", exc_info=True)
                    files_failed += 1

                    await repo.create_file_review(
                        session_id=review_session.id,
                        file_path=file.filename,
                        language="unknown",
                        file_content="",
                        summary=f"Review failed: {str(e)}",
                        status="failed",
                    )

        critical_count = sum(
            1 for c in all_comments if c.get("severity") == ReviewSeverity.CRITICAL
        )
        warning_count = sum(1 for c in all_comments if c.get("severity") == ReviewSeverity.WARNING)
        suggestion_count = sum(
            1 for c in all_comments if c.get("severity") == ReviewSeverity.SUGGESTION
        )
        praise_count = sum(1 for c in all_comments if c.get("severity") == ReviewSeverity.PRAISE)

        # Add unchanged files with secrets to the critical count
        unchanged_secrets_count = sum(1 for f in unchanged_with_issues if "current_secrets" in f)
        total_files_with_secrets = files_with_secrets + unchanged_secrets_count

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

        if total_files_with_secrets > 0:
            review_comment += "## ⛔ Review Summary\n\n"
            if files_with_secrets > 0 and unchanged_secrets_count > 0:
                review_comment += (
                    f"**CRITICAL**: **{files_with_secrets}** changed file(s) — see **inline comments** "
                    f"on the diff; **{unchanged_secrets_count}** unchanged file(s) with secrets are "
                    f"listed above. Do not merge until resolved.\n\n"
                )
            elif files_with_secrets > 0:
                review_comment += (
                    f"**CRITICAL**: **{files_with_secrets}** file(s) in this diff may contain secrets. "
                    f"Details are in **inline review comments**. Do not merge until resolved.\n\n"
                )
            else:
                review_comment += (
                    f"**CRITICAL**: **{unchanged_secrets_count}** unchanged file(s) still contain secrets "
                    f"(see the section above). Remove secrets before merging.\n\n"
                )
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

        ai_inline_posted = sum(1 for c in all_comments if c.get("_posted_inline"))
        if ai_inline_posted:
            review_comment += (
                f"💬 **{ai_inline_posted}** AI finding(s) were posted on the **Files changed** "
                "tab as inline review comments. They are omitted below to avoid duplicating "
                "the thread.\n\n"
            )

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
            logger.info(f"Identified {len(changed_filenames)} file(s) changed since last review")

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

    def _filter_files(self, files, gitignore_spec=None) -> tuple[list, list, list, list, list]:
        filtered = []
        skipped_patterns = []
        skipped_large = []
        unwanted = []
        gitignored_tracked = []

        for file in files:
            is_unwanted = any(pattern.search(file.filename) for pattern in UNWANTED_FILE_PATTERNS)

            if is_unwanted:
                logger.debug(f"Unwanted file detected: {file.filename}")
                unwanted.append(file)
                continue

            if gitignore_spec and path_is_ignored_by_spec(gitignore_spec, file.filename):
                logger.debug("File matches root .gitignore: %s", file.filename)
                gitignored_tracked.append(file)
                continue

            should_skip = any(pattern.search(file.filename) for pattern in IGNORE_PATTERNS)

            if should_skip or not file.patch:
                logger.debug(f"Skipping file by pattern: {file.filename}")
                skipped_patterns.append(file.filename)
                continue

            file_tokens = len(file.patch) // 4

            if file_tokens > MAX_TOKENS_PER_FILE:
                logger.warning(
                    f"Skipping large file: {file.filename} "
                    f"(~{file_tokens:,} tokens > {MAX_TOKENS_PER_FILE:,} limit)"
                )
                skipped_large.append({"filename": file.filename, "tokens": file_tokens})
                continue

            filtered.append(file)

        return filtered, skipped_patterns, skipped_large, unwanted, gitignored_tracked

    def _create_batches(self, files) -> list[list]:
        """Create batches of files for processing."""
        batches = []
        current_batch = []
        current_tokens = 0

        for file in files:
            file_tokens = len(file.patch or "") // 4

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

    @staticmethod
    def _collect_commentable_new_file_lines(patch: str) -> set[int]:
        """New-side line numbers present in the unified diff (context + additions).

        GitHub pull-request review comments must anchor to lines that appear in the diff.
        """
        lines: set[int] = set()
        current_new_line = 0
        for line in patch.splitlines():
            if line.startswith("@@"):
                plus_part = line.split("+", 1)[1].split(" ", 1)[0]
                current_new_line = int(plus_part.split(",")[0]) - 1
                continue
            if line.startswith("+") and not line.startswith("+++"):
                current_new_line += 1
                lines.add(current_new_line)
            elif line.startswith("-") or line.startswith("\\"):
                continue
            else:
                current_new_line += 1
                lines.add(current_new_line)
        return lines

    @staticmethod
    def _resolve_ai_inline_line(raw: object, commentable: set[int]) -> int | None:
        """Map model ``line_number`` to a diff line GitHub will accept (exact match only)."""
        if raw is None:
            return None
        try:
            n = int(raw)
        except (TypeError, ValueError):
            return None
        if n in commentable:
            return n
        return None

    def _format_ai_inline_body(self, comment: dict) -> str:
        sev = comment.get("severity", ReviewSeverity.SUGGESTION)
        emoji = REVIEW_SEVERITY_EMOJI.get(sev, "📌")
        title = (comment.get("title") or "").strip()
        text = (comment.get("text") or "").strip()
        rec = (comment.get("recommendation") or "").strip()
        parts = [f"{emoji} **AI code review**"]
        if title:
            parts.append(f"**{title}**")
        if text:
            parts.append(text)
        if rec:
            parts.append(f"**Suggestion**: {rec}")
        return "\n\n".join(parts)


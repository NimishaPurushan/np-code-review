import logging

from cachetools import TTLCache
from github import Github, GithubException, GithubIntegration
from github.Commit import Commit
from github.File import File
from github.IssueComment import IssueComment
from github.PullRequest import PullRequest
from github.Repository import Repository

logger = logging.getLogger(__name__)

TOKEN_TTL = 3300
TOKEN_CACHE_SIZE = 100
_token_cache = TTLCache(maxsize=TOKEN_CACHE_SIZE, ttl=TOKEN_TTL)


class GithubClient:
    def __init__(self, github_app_id: str, github_private_key: str):
        self.github_app_id = github_app_id
        self.github_private_key = github_private_key
        self._integration: GithubIntegration | None = None

    @property
    def integration(self) -> GithubIntegration:
        if self._integration is None:
            logger.debug("Initializing GitHub Integration")
            self._integration = GithubIntegration(
                self.github_app_id,
                self.github_private_key,
            )
        return self._integration

    def get_access_token(self, installation_id: int) -> str:
        if installation_id in _token_cache:
            logger.debug(f"Using cached token for installation {installation_id}")
            return _token_cache[installation_id]

        logger.info(f"Generating new access token for installation {installation_id}")
        token = self.integration.get_access_token(installation_id).token
        _token_cache[installation_id] = token
        return token

    def get_client(self, installation_id: int) -> Github:
        token = self.get_access_token(installation_id)
        return Github(token)

    def get_repo(self, installation_id: int, repo_full_name: str) -> Repository:
        client = self.get_client(installation_id)
        return client.get_repo(repo_full_name)

    def get_pull_request(
        self, installation_id: int, repo_full_name: str, pr_number: int
    ) -> PullRequest:
        repo = self.get_repo(installation_id, repo_full_name)
        return repo.get_pull(pr_number)

    def get_pr_files(self, installation_id: int, repo_full_name: str, pr_number: int) -> list[File]:
        pr = self.get_pull_request(installation_id, repo_full_name, pr_number)
        return list(pr.get_files())

    def get_file_content(
        self,
        installation_id: int,
        repo_full_name: str,
        file_path: str,
        ref: str,
    ) -> str:
        repo = self.get_repo(installation_id, repo_full_name)
        file_content = repo.get_contents(file_path, ref=ref)

        if isinstance(file_content, list):
            raise ValueError(f"Path '{file_path}' is a directory, not a file")

        return file_content.decoded_content.decode("utf-8")

    def try_get_file_text(
        self,
        installation_id: int,
        repo_full_name: str,
        file_path: str,
        ref: str,
    ) -> str | None:
        try:
            return self.get_file_content(installation_id, repo_full_name, file_path, ref)
        except GithubException as e:
            if getattr(e, "status", None) == 404:
                logger.debug("File not found at ref %s: %s", ref, file_path)
                return None
            raise e from None

    def get_pr_diff_since_comment(
        self,
        installation_id: int,
        repo_full_name: str,
        pr_number: int,
        comment_id: int,
    ) -> list[Commit]:
        pr = self.get_pull_request(installation_id, repo_full_name, pr_number)
        repo = self.get_repo(installation_id, repo_full_name)

        comment = repo.get_issue(pr_number).get_comment(comment_id)
        comment_time = comment.created_at
        commits = list(pr.get_commits())
        new_commits = [commit for commit in commits if commit.commit.author.date > comment_time]

        return new_commits

    def post_comment(
        self,
        installation_id: int,
        repo_full_name: str,
        pr_number: int,
        body: str,
    ) -> IssueComment:
        pr = self.get_pull_request(installation_id, repo_full_name, pr_number)
        logger.info(f"Posting comment on PR #{pr_number} in {repo_full_name}")
        return pr.create_issue_comment(body)

    def get_pr_comments(
        self, installation_id: int, repo_full_name: str, pr_number: int
    ) -> list[IssueComment]:
        pr = self.get_pull_request(installation_id, repo_full_name, pr_number)
        return list(pr.as_issue().get_comments())

    def get_pr_review_comments(self, installation_id: int, repo_full_name: str, pr_number: int):
        pr = self.get_pull_request(installation_id, repo_full_name, pr_number)
        return list(pr.get_review_comments())

    def create_pr_comment(
        self,
        installation_id: int,
        repo_full_name: str,
        pr_number: int,
        body: str,
    ) -> IssueComment:
        pr = self.get_pull_request(installation_id, repo_full_name, pr_number)
        return pr.as_issue().create_comment(body)

    def create_review_comment(
        self,
        installation_id: int,
        repo_full_name: str,
        pr_number: int,
        body: str,
        commit_id: str,
        path: str,
        line: int | None = None,
    ):
        """
        Post a pull request review comment on a line, or on the whole file if ``line`` is None.

        Binary / generated files often have no diff hunks with ``+`` lines; GitHub accepts
        ``subject_type=file`` in that case (see REST API create review comment).
        """
        pr = self.get_pull_request(installation_id, repo_full_name, pr_number)
        if line is not None:
            return pr.create_review_comment(
                body=body,
                commit=commit_id,
                path=path,
                line=line,
            )
        return pr.create_review_comment(
            body=body,
            commit=commit_id,
            path=path,
            subject_type="file",
        )

    def get_pr_diff(self, installation_id: int, repo_full_name: str, pr_number: int) -> str:
        pr = self.get_pull_request(installation_id, repo_full_name, pr_number)
        repo = self.get_repo(installation_id, repo_full_name)

        comparison = repo.compare(pr.base.sha, pr.head.sha)

        diff_parts = []
        for file in comparison.files:
            if file.patch:
                diff_parts.append(f"diff --git a/{file.filename} b/{file.filename}")
                diff_parts.append(f"--- a/{file.filename}")
                diff_parts.append(f"+++ b/{file.filename}")
                diff_parts.append(file.patch)
                diff_parts.append("")

        return "\n".join(diff_parts)

    def get_bot_username(self, installation_id: int) -> str:
        client = self.get_client(installation_id)
        return client.get_user().login

    def get_bot_previous_comments(
        self, installation_id: int, repo_full_name: str, pr_number: int
    ) -> list[dict]:
        try:
            bot_username = self.get_bot_username(installation_id)
            all_bot_comments = []

            issue_comments = self.get_pr_comments(installation_id, repo_full_name, pr_number)
            for comment in issue_comments:
                if comment.user and comment.user.login == bot_username:
                    all_bot_comments.append(
                        {
                            "type": "general",
                            "author": bot_username,
                            "created_at": comment.created_at.isoformat(),
                            "body": comment.body,
                        }
                    )

            review_comments = self.get_pr_review_comments(
                installation_id, repo_full_name, pr_number
            )
            for comment in review_comments:
                if comment.user and comment.user.login == bot_username:
                    all_bot_comments.append(
                        {
                            "type": "inline",
                            "author": bot_username,
                            "created_at": comment.created_at.isoformat(),
                            "file": comment.path,
                            "line": comment.line
                            if hasattr(comment, "line")
                            else comment.original_line,
                            "body": comment.body,
                        }
                    )

            all_bot_comments.sort(key=lambda x: x["created_at"])
            logger.info(f"Found {len(all_bot_comments)} previous bot comments on PR #{pr_number}")
            return all_bot_comments

        except Exception as e:
            logger.warning(f"Error retrieving bot previous comments: {e}")
            return []

    def get_commit_files(
        self, installation_id: int, repo_full_name: str, commit_sha: str
    ) -> list[File]:
        repo = self.get_repo(installation_id, repo_full_name)
        commit = repo.get_commit(commit_sha)
        return list(commit.files)

    def compare_commits(
        self, installation_id: int, repo_full_name: str, base_sha: str, head_sha: str
    ) -> list[File]:
        repo = self.get_repo(installation_id, repo_full_name)
        comparison = repo.compare(base_sha, head_sha)
        return list(comparison.files)

    def format_previous_feedback(self, previous_comments: list[dict]) -> str:
        if not previous_comments:
            return "No previous feedback from bot on this PR."

        formatted_lines = ["## Previous Bot Feedback\n"]

        for idx, comment in enumerate(previous_comments, 1):
            comment_type = comment.get("type", "general")
            created_at = comment.get("created_at", "")
            body = comment.get("body", "")

            if comment_type == "inline":
                file_path = comment.get("file", "unknown")
                line = comment.get("line", "?")
                formatted_lines.append(
                    f"### Comment {idx} (Inline on `{file_path}` line {line})\n"
                    f"**Date**: {created_at}\n"
                    f"{body}\n"
                )
            else:
                formatted_lines.append(
                    f"### Comment {idx} (General PR Comment)\n**Date**: {created_at}\n{body}\n"
                )

        return "\n".join(formatted_lines)

    def get_pr_files_list(
        self, installation_id: int, repo_full_name: str, pr_number: int
    ) -> list[dict]:
        files = self.get_pr_files(installation_id, repo_full_name, pr_number)

        return [
            {
                "filename": f.filename,
                "status": f.status,
                "additions": f.additions,
                "deletions": f.deletions,
                "changes": f.changes,
                "patch": f.patch,
            }
            for f in files
        ]

    def get_pr_files_with_content(
        self, installation_id: int, repo_full_name: str, pr_number: int
    ) -> list[dict]:
        pr = self.get_pull_request(installation_id, repo_full_name, pr_number)
        files = self.get_pr_files(installation_id, repo_full_name, pr_number)

        result = []
        for file in files:
            file_info = {
                "filename": file.filename,
                "status": file.status,
                "additions": file.additions,
                "deletions": file.deletions,
                "changes": file.changes,
                "patch": file.patch,
                "content_before": None,
                "content_after": None,
            }

            # Get content from base branch (before changes)
            if file.status != "added":
                try:
                    file_info["content_before"] = self.get_file_content(
                        installation_id, repo_full_name, file.filename, pr.base.sha
                    )
                except Exception as e:
                    logger.warning(f"Could not get before content for {file.filename}: {e}")

            if file.status != "removed":
                try:
                    file_info["content_after"] = self.get_file_content(
                        installation_id, repo_full_name, file.filename, pr.head.sha
                    )
                except Exception as e:
                    logger.warning(f"Could not get after content for {file.filename}: {e}")

            result.append(file_info)

        return result

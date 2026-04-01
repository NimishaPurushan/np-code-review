import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
from github.File import File

from src.config.config import Config
from src.database.models import FileReview, ReviewComment, ReviewSession
from src.database.repository import ReviewRepository
from src.services.code_review.code_review_service import CodeReviewService
from src.services.github.client import GithubClient


@pytest.fixture
def mock_config():
    return Mock(spec=Config)


@pytest.fixture
def code_review_service(mock_config):
    return CodeReviewService(mock_config)


@pytest.fixture
def mock_github_file():
    def create_file(filename, patch_content, additions=10, deletions=5):
        file = Mock(spec=File)
        file.filename = filename
        file.patch = patch_content
        file.additions = additions
        file.deletions = deletions
        return file

    return create_file


@pytest.fixture
def mock_repo():
    repo = AsyncMock(spec=ReviewRepository)
    return repo


@pytest.fixture
def mock_github_client():
    client = Mock(spec=GithubClient)
    return client


class TestIncrementalReview:
    @pytest.mark.asyncio
    async def test_no_previous_review_reviews_all_files(
        self, code_review_service, mock_repo, mock_github_client, mock_github_file
    ):
        pr = Mock()
        file1 = mock_github_file("file1.py", "@@ -1,3 +1,3 @@\n-old\n+new\n")
        file2 = mock_github_file("file2.py", "@@ -1,3 +1,3 @@\n-old\n+new\n")
        pr.get_files.return_value = [file1, file2]

        mock_repo.get_last_reviewed_commit.return_value = None

        files, previous_reviews, unchanged = await code_review_service._get_incremental_files(
            pr=pr,
            repo_full_name="test/repo",
            pr_number=1,
            current_commit="abc123",
            repo=mock_repo,
            github=mock_github_client,
            installation_id=123,
        )

        assert len(files) == 2
        assert files[0].filename == "file1.py"
        assert files[1].filename == "file2.py"
        assert previous_reviews == {}
        assert unchanged == []

    @pytest.mark.asyncio
    async def test_incremental_review_only_changed_files(
        self, code_review_service, mock_repo, mock_github_client, mock_github_file
    ):
        pr = Mock()
        file1 = mock_github_file("file1.py", "@@ -1,3 +1,3 @@\n-old\n+new\n")
        file2 = mock_github_file("file2.py", "@@ -1,3 +1,3 @@\n-old\n+new\n")
        file3 = mock_github_file("file3.py", "@@ -1,3 +1,3 @@\n-old\n+new\n")
        pr.get_files.return_value = [file1, file2, file3]

        last_review = Mock(spec=ReviewSession)
        last_review.id = uuid4()
        last_review.commit_sha = "xyz789"
        mock_repo.get_last_reviewed_commit.return_value = last_review

        changed_file2 = mock_github_file("file2.py", "@@ -1,3 +1,3 @@\n-old\n+new\n")
        changed_file3 = mock_github_file("file3.py", "@@ -1,3 +1,3 @@\n-old\n+new\n")
        mock_github_client.compare_commits.return_value = [changed_file2, changed_file3]

        mock_repo.get_reviewed_files_from_session.return_value = {
            "file1.py": {
                "status": "success",
                "comment_count": 2,
                "summary": "Has issues",
                "content_hash": "hash1",
                "comments": [
                    {"severity": "CRITICAL", "description": "Issue 1", "line_number": 10},
                    {"severity": "WARNING", "description": "Issue 2", "line_number": 15},
                ],
            },
            "file2.py": {
                "status": "success",
                "comment_count": 0,
                "summary": "Clean",
                "content_hash": "hash2",
                "comments": [],
            },
        }

        files, previous_reviews, unchanged = await code_review_service._get_incremental_files(
            pr=pr,
            repo_full_name="test/repo",
            pr_number=1,
            current_commit="abc123",
            repo=mock_repo,
            github=mock_github_client,
            installation_id=123,
        )

        assert len(files) == 2
        assert files[0].filename == "file2.py"
        assert files[1].filename == "file3.py"

        assert len(unchanged) == 1
        assert unchanged[0]["filename"] == "file1.py"
        assert unchanged[0]["comment_count"] == 2
        assert len(unchanged[0]["comments"]) == 2

    @pytest.mark.asyncio
    async def test_unchanged_files_without_issues_not_reported(
        self, code_review_service, mock_repo, mock_github_client, mock_github_file
    ):
        pr = Mock()
        file1 = mock_github_file("file1.py", "@@ -1,3 +1,3 @@\n-old\n+new\n")
        file2 = mock_github_file("file2.py", "@@ -1,3 +1,3 @@\n-old\n+new\n")
        pr.get_files.return_value = [file1, file2]

        last_review = Mock(spec=ReviewSession)
        last_review.id = uuid4()
        last_review.commit_sha = "xyz789"
        mock_repo.get_last_reviewed_commit.return_value = last_review

        changed_file2 = mock_github_file("file2.py", "@@ -1,3 +1,3 @@\n-old\n+new\n")
        mock_github_client.compare_commits.return_value = [changed_file2]

        mock_repo.get_reviewed_files_from_session.return_value = {
            "file1.py": {
                "status": "success",
                "comment_count": 0,
                "summary": "Clean",
                "content_hash": "hash1",
                "comments": [],
            }
        }

        files, previous_reviews, unchanged = await code_review_service._get_incremental_files(
            pr=pr,
            repo_full_name="test/repo",
            pr_number=1,
            current_commit="abc123",
            repo=mock_repo,
            github=mock_github_client,
            installation_id=123,
        )

        assert len(files) == 1
        assert files[0].filename == "file2.py"
        assert len(unchanged) == 0

    @pytest.mark.asyncio
    async def test_fallback_to_full_review_on_error(
        self, code_review_service, mock_repo, mock_github_client, mock_github_file
    ):
        pr = Mock()
        file1 = mock_github_file("file1.py", "@@ -1,3 +1,3 @@\n-old\n+new\n")
        file2 = mock_github_file("file2.py", "@@ -1,3 +1,3 @@\n-old\n+new\n")
        pr.get_files.return_value = [file1, file2]

        last_review = Mock(spec=ReviewSession)
        last_review.id = uuid4()
        last_review.commit_sha = "xyz789"
        mock_repo.get_last_reviewed_commit.return_value = last_review

        mock_github_client.compare_commits.side_effect = Exception("GitHub API error")

        files, previous_reviews, unchanged = await code_review_service._get_incremental_files(
            pr=pr,
            repo_full_name="test/repo",
            pr_number=1,
            current_commit="abc123",
            repo=mock_repo,
            github=mock_github_client,
            installation_id=123,
        )

        assert len(files) == 2
        assert previous_reviews == {}
        assert unchanged == []


class TestGitHubClientCommitMethods:
    def test_get_commit_files(self):
        client = GithubClient(github_app_id="123", github_private_key="key")

        mock_repo = Mock()
        mock_commit = Mock()
        mock_file1 = Mock(spec=File)
        mock_file1.filename = "file1.py"
        mock_file2 = Mock(spec=File)
        mock_file2.filename = "file2.py"
        mock_commit.files = [mock_file1, mock_file2]
        mock_repo.get_commit.return_value = mock_commit

        with patch.object(client, "get_repo", return_value=mock_repo):
            files = client.get_commit_files(
                installation_id=123, repo_full_name="test/repo", commit_sha="abc123"
            )

            assert len(files) == 2
            assert files[0].filename == "file1.py"
            assert files[1].filename == "file2.py"

    def test_compare_commits(self):
        client = GithubClient(github_app_id="123", github_private_key="key")

        mock_repo = Mock()
        mock_comparison = Mock()
        mock_file1 = Mock(spec=File)
        mock_file1.filename = "changed.py"
        mock_comparison.files = [mock_file1]
        mock_repo.compare.return_value = mock_comparison

        with patch.object(client, "get_repo", return_value=mock_repo):
            files = client.compare_commits(
                installation_id=123,
                repo_full_name="test/repo",
                base_sha="xyz789",
                head_sha="abc123",
            )

            assert len(files) == 1
            assert files[0].filename == "changed.py"
            mock_repo.compare.assert_called_once_with("xyz789", "abc123")


class TestDatabaseIncrementalMethods:
    @pytest.mark.asyncio
    async def test_get_last_reviewed_commit(self):
        from sqlalchemy.ext.asyncio import AsyncSession

        mock_session = AsyncMock(spec=AsyncSession)
        repo = ReviewRepository(mock_session)

        mock_review = Mock(spec=ReviewSession)
        mock_review.id = uuid4()
        mock_review.commit_sha = "xyz789"
        mock_review.status = "completed"
        mock_review.completed_at = datetime.utcnow()

        mock_result = Mock()
        mock_scalars = Mock()
        mock_scalars.first.return_value = mock_review
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        last_review = await repo.get_last_reviewed_commit(
            repo_full_name="test/repo", pr_number=1, before_commit="abc123"
        )

        assert last_review is not None
        assert last_review.commit_sha == "xyz789"
        assert last_review.status == "completed"

    @pytest.mark.asyncio
    async def test_get_reviewed_files_from_session(self):
        from sqlalchemy.ext.asyncio import AsyncSession

        mock_session = AsyncMock(spec=AsyncSession)
        repo = ReviewRepository(mock_session)

        session_id = uuid4()

        mock_file_review = Mock(spec=FileReview)
        mock_file_review.file_path = "test.py"
        mock_file_review.status = "success"
        mock_file_review.comment_count = 2
        mock_file_review.summary = "Has issues"
        mock_file_review.content_hash = "hash123"

        mock_comment1 = Mock(spec=ReviewComment)
        mock_comment1.severity = "CRITICAL"
        mock_comment1.description = "Issue 1"
        mock_comment1.line_number = 10
        mock_comment1.category = "security"

        mock_comment2 = Mock(spec=ReviewComment)
        mock_comment2.severity = "WARNING"
        mock_comment2.description = "Issue 2"
        mock_comment2.line_number = 20
        mock_comment2.category = "style"

        mock_file_review.comments = [mock_comment1, mock_comment2]

        mock_result = Mock()
        mock_scalars = Mock()
        mock_scalars.all.return_value = [mock_file_review]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        reviewed_files = await repo.get_reviewed_files_from_session(session_id)

        assert "test.py" in reviewed_files
        assert reviewed_files["test.py"]["status"] == "success"
        assert reviewed_files["test.py"]["comment_count"] == 2
        assert len(reviewed_files["test.py"]["comments"]) == 2
        assert reviewed_files["test.py"]["comments"][0]["severity"] == "CRITICAL"

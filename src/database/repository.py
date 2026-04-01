import hashlib
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import FileReview, PullRequest, ReviewComment, ReviewSession

logger = logging.getLogger(__name__)


class ReviewRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_pull_request(
        self,
        repo_full_name: str,
        pr_number: int,
        title: str,
        description: str | None = None,
        author: str | None = None,
    ) -> PullRequest:
        stmt = select(PullRequest).where(
            and_(
                PullRequest.repo_full_name == repo_full_name,
                PullRequest.pr_number == pr_number,
            )
        )
        result = await self.session.execute(stmt)
        pr = result.scalar_one_or_none()

        if pr is None:
            pr = PullRequest(
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                title=title,
                description=description,
                author=author,
            )
            self.session.add(pr)
            await self.session.flush()
            logger.info(f"Created PR record: {repo_full_name}#{pr_number}")
        else:
            pr.title = title
            pr.description = description
            pr.updated_at = datetime.utcnow()
            logger.info(f"Updated PR record: {repo_full_name}#{pr_number}")

        return pr

    async def get_review_by_commit(
        self,
        repo_full_name: str,
        pr_number: int,
        commit_sha: str,
    ) -> ReviewSession | None:
        stmt = (
            select(ReviewSession)
            .join(PullRequest)
            .where(
                and_(
                    PullRequest.repo_full_name == repo_full_name,
                    PullRequest.pr_number == pr_number,
                    ReviewSession.commit_sha == commit_sha,
                    ReviewSession.status == "completed",
                )
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_review_session(
        self,
        pr_id: UUID,
        commit_sha: str,
        trigger_event: str | None = None,
        ai_metadata: dict[str, Any] | None = None,
    ) -> ReviewSession:
        session = ReviewSession(
            pr_id=pr_id,
            commit_sha=commit_sha,
            status="in_progress",
            trigger_event=trigger_event,
            ai_metadata=ai_metadata,
        )
        self.session.add(session)
        await self.session.flush()
        logger.info(f"Created review session: {session.id}")
        return session

    async def update_review_session(
        self,
        session_id: UUID,
        status: str | None = None,
        files_reviewed: int | None = None,
        files_failed: int | None = None,
        total_comments: int | None = None,
        critical_count: int | None = None,
        warning_count: int | None = None,
        suggestion_count: int | None = None,
        praise_count: int | None = None,
        error_message: str | None = None,
        completed_at: datetime | None = None,
    ) -> ReviewSession:
        """Update review session statistics."""
        stmt = select(ReviewSession).where(ReviewSession.id == session_id)
        result = await self.session.execute(stmt)
        session = result.scalar_one()

        if status is not None:
            session.status = status
        if files_reviewed is not None:
            session.files_reviewed = files_reviewed
        if files_failed is not None:
            session.files_failed = files_failed
        if total_comments is not None:
            session.total_comments = total_comments
        if critical_count is not None:
            session.critical_count = critical_count
        if warning_count is not None:
            session.warning_count = warning_count
        if suggestion_count is not None:
            session.suggestion_count = suggestion_count
        if praise_count is not None:
            session.praise_count = praise_count
        if error_message is not None:
            session.error_message = error_message
        if completed_at is not None:
            session.completed_at = completed_at

        await self.session.flush()
        return session

    async def create_file_review(
        self,
        session_id: UUID,
        file_path: str,
        language: str,
        file_content: str,
        summary: str | None = None,
        status: str = "success",
        lines_added: int = 0,
        lines_deleted: int = 0,
    ) -> FileReview:
        content_hash = hashlib.sha256(file_content.encode()).hexdigest()

        file_review = FileReview(
            session_id=session_id,
            file_path=file_path,
            language=language,
            content_hash=content_hash,
            summary=summary,
            status=status,
            lines_added=lines_added,
            lines_deleted=lines_deleted,
        )
        self.session.add(file_review)
        await self.session.flush()
        return file_review

    async def create_review_comment(
        self,
        file_review_id: UUID,
        severity: str,
        description: str,
        category: str | None = None,
        title: str | None = None,
        line_number: int | None = None,
        recommendation: str | None = None,
        code_snippet: str | None = None,
    ) -> ReviewComment:
        comment = ReviewComment(
            file_review_id=file_review_id,
            severity=severity,
            description=description,
            category=category,
            title=title,
            line_number=line_number,
            recommendation=recommendation,
            code_snippet=code_snippet,
        )
        self.session.add(comment)
        await self.session.flush()

        fr_stmt = select(FileReview).where(FileReview.id == file_review_id)
        fr_result = await self.session.execute(fr_stmt)
        file_review = fr_result.scalar_one()
        file_review.comment_count = (file_review.comment_count or 0) + 1
        await self.session.flush()

        return comment

    async def get_review_session_with_details(self, session_id: UUID) -> ReviewSession:
        stmt = (
            select(ReviewSession)
            .where(ReviewSession.id == session_id)
            .options(selectinload(ReviewSession.file_reviews).selectinload(FileReview.comments))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_last_reviewed_commit(
        self, repo_full_name: str, pr_number: int, before_commit: str | None = None
    ) -> ReviewSession | None:
        stmt = (
            select(ReviewSession)
            .join(PullRequest)
            .where(
                and_(
                    PullRequest.repo_full_name == repo_full_name,
                    PullRequest.pr_number == pr_number,
                    ReviewSession.status == "completed",
                )
            )
        )

        if before_commit:
            stmt = stmt.where(ReviewSession.commit_sha != before_commit)

        stmt = stmt.order_by(ReviewSession.completed_at.desc())

        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_reviewed_files_from_session(self, session_id: UUID) -> dict[str, dict]:
        stmt = (
            select(FileReview)
            .where(FileReview.session_id == session_id)
            .options(selectinload(FileReview.comments))
        )
        result = await self.session.execute(stmt)
        file_reviews = result.scalars().all()

        reviewed_files = {}
        for file_review in file_reviews:
            reviewed_files[file_review.file_path] = {
                "status": file_review.status,
                "comment_count": file_review.comment_count,
                "summary": file_review.summary,
                "content_hash": file_review.content_hash,
                "comments": [
                    {
                        "severity": comment.severity,
                        "description": comment.description,
                        "line_number": comment.line_number,
                        "category": comment.category,
                    }
                    for comment in file_review.comments
                ],
            }

        return reviewed_files

    async def mark_comments_posted(self, comment_ids: list[UUID], github_review_id: int):
        for comment_id in comment_ids:
            stmt = select(ReviewComment).where(ReviewComment.id == comment_id)
            result = await self.session.execute(stmt)
            comment = result.scalar_one_or_none()
            if comment:
                comment.posted_to_github = True
                comment.github_review_id = github_review_id

        await self.session.flush()

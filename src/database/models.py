import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_full_name = Column(String(255), nullable=False, index=True)
    pr_number = Column(Integer, nullable=False, index=True)
    title = Column(Text, nullable=False)
    description = Column(Text)
    author = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    review_sessions = relationship(
        "ReviewSession", back_populates="pull_request", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<PullRequest {self.repo_full_name}#{self.pr_number}>"


class ReviewSession(Base):
    __tablename__ = "review_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pr_id = Column(
        UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False
    )
    commit_sha = Column(String(40), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="queued", index=True)
    trigger_event = Column(String(50))

    files_reviewed = Column(Integer, default=0)
    files_failed = Column(Integer, default=0)
    total_comments = Column(Integer, default=0)
    critical_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)
    suggestion_count = Column(Integer, default=0)
    praise_count = Column(Integer, default=0)

    ai_metadata = Column(JSON)

    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    error_message = Column(Text)

    pull_request = relationship("PullRequest", back_populates="review_sessions")
    file_reviews = relationship(
        "FileReview", back_populates="review_session", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<ReviewSession {self.id} - {self.status}>"


class FileReview(Base):
    __tablename__ = "file_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True), ForeignKey("review_sessions.id", ondelete="CASCADE"), nullable=False
    )
    file_path = Column(String(500), nullable=False)
    language = Column(String(50))
    content_hash = Column(String(64), index=True)
    summary = Column(Text)
    status = Column(String(20), default="success")

    lines_added = Column(Integer, default=0)
    lines_deleted = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    review_session = relationship("ReviewSession", back_populates="file_reviews")
    comments = relationship(
        "ReviewComment", back_populates="file_review", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<FileReview {self.file_path}>"


class ReviewComment(Base):
    __tablename__ = "review_comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_review_id = Column(
        UUID(as_uuid=True), ForeignKey("file_reviews.id", ondelete="CASCADE"), nullable=False
    )

    line_number = Column(Integer)
    line_range_start = Column(Integer)
    line_range_end = Column(Integer)

    severity = Column(String(20), nullable=False, index=True)
    category = Column(String(50))

    title = Column(String(255))
    description = Column(Text, nullable=False)
    recommendation = Column(Text)
    code_snippet = Column(Text)

    posted_to_github = Column(Boolean, default=False)
    github_comment_id = Column(Integer)
    github_review_id = Column(Integer)

    created_at = Column(DateTime, default=datetime.utcnow)

    file_review = relationship("FileReview", back_populates="comments")

    def __repr__(self):
        return f"<ReviewComment {self.severity} - {self.title}>"

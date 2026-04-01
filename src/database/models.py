"""SQLAlchemy database models for code review system."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class PullRequest(Base):
    """Pull request entity."""

    __tablename__ = "pull_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_full_name = Column(String(255), nullable=False, index=True)
    pr_number = Column(Integer, nullable=False, index=True)
    title = Column(Text, nullable=False)
    description = Column(Text)
    author = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    review_sessions = relationship(
        "ReviewSession", back_populates="pull_request", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<PullRequest {self.repo_full_name}#{self.pr_number}>"


class ReviewSession(Base):
    """Review session entity - one per review attempt."""

    __tablename__ = "review_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pr_id = Column(
        UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False
    )
    commit_sha = Column(String(40), nullable=False, index=True)
    status = Column(
        String(20), nullable=False, default="queued", index=True
    )  # queued, in_progress, completed, failed
    trigger_event = Column(String(50))  # opened, synchronize, ready_for_review

    # Review statistics
    files_reviewed = Column(Integer, default=0)
    files_failed = Column(Integer, default=0)
    total_comments = Column(Integer, default=0)
    critical_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)
    suggestion_count = Column(Integer, default=0)
    praise_count = Column(Integer, default=0)

    # AI metadata (stored as JSON)
    ai_metadata = Column(JSON)  # model_id, prompt_version, token_usage, cost, etc.

    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    # Error tracking
    error_message = Column(Text)

    # Relationships
    pull_request = relationship("PullRequest", back_populates="review_sessions")
    file_reviews = relationship(
        "FileReview", back_populates="review_session", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<ReviewSession {self.id} - {self.status}>"


class FileReview(Base):
    """File review entity - one per file reviewed."""

    __tablename__ = "file_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True), ForeignKey("review_sessions.id", ondelete="CASCADE"), nullable=False
    )
    file_path = Column(String(500), nullable=False)
    language = Column(String(50))
    content_hash = Column(String(64), index=True)  # SHA-256 of file content
    summary = Column(Text)
    status = Column(String(20), default="success")  # success, failed, skipped

    # File statistics
    lines_added = Column(Integer, default=0)
    lines_deleted = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    review_session = relationship("ReviewSession", back_populates="file_reviews")
    comments = relationship(
        "ReviewComment", back_populates="file_review", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<FileReview {self.file_path}>"


class ReviewComment(Base):
    """Individual review comment entity."""

    __tablename__ = "review_comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_review_id = Column(
        UUID(as_uuid=True), ForeignKey("file_reviews.id", ondelete="CASCADE"), nullable=False
    )

    # Location
    line_number = Column(Integer)  # NULL for file-level comments
    line_range_start = Column(Integer)
    line_range_end = Column(Integer)

    # Classification
    severity = Column(
        String(20), nullable=False, index=True
    )  # critical, warning, suggestion, praise
    category = Column(String(50))  # security, performance, bug, style, best-practice

    # Content
    title = Column(String(255))
    description = Column(Text, nullable=False)
    recommendation = Column(Text)
    code_snippet = Column(Text)

    # GitHub integration
    posted_to_github = Column(Boolean, default=False)
    github_comment_id = Column(Integer)
    github_review_id = Column(Integer)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    file_review = relationship("FileReview", back_populates="comments")

    def __repr__(self):
        return f"<ReviewComment {self.severity} - {self.title}>"

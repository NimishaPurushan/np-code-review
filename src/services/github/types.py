from enum import StrEnum


class GitHubEventType(StrEnum):
    PULL_REQUEST = "pull_request"
    PULL_REQUEST_REVIEW = "pull_request_review"
    PULL_REQUEST_REVIEW_COMMENT = "pull_request_review_comment"
    PUSH = "push"
    PING = "ping"


class PullRequestAction(StrEnum):
    OPENED = "opened"
    SYNCHRONIZE = "synchronize"
    READY_FOR_REVIEW = "ready_for_review"

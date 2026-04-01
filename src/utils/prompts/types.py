from enum import StrEnum


class ReviewSeverity(StrEnum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    SUGGESTION = "SUGGESTION"
    PRAISE = "PRAISE"

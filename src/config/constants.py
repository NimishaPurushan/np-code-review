from enum import StrEnum


class ReviewSeverity(StrEnum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    SUGGESTION = "SUGGESTION"
    PRAISE = "PRAISE"


REVIEW_SEVERITY_EMOJI = {
    ReviewSeverity.CRITICAL: "🔴",
    ReviewSeverity.WARNING: "⚠️",
    ReviewSeverity.SUGGESTION: "💡",
    ReviewSeverity.PRAISE: "✅",
}

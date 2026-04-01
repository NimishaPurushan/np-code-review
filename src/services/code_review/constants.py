from ...utils.prompts.types import ReviewSeverity

# Chunking constants
MAX_FILES_PER_BATCH = 10
MAX_TOKENS_PER_FILE = 10_000  # Rough estimate: 40KB of code
MAX_TOKENS_PER_BATCH = 50_000  # Conservative limit to stay within AI context window

REVIEW_SEVERITY_EMOJI = {
    ReviewSeverity.CRITICAL: "🔴",
    ReviewSeverity.WARNING: "⚠️",
    ReviewSeverity.SUGGESTION: "💡",
    ReviewSeverity.PRAISE: "✅",
}

EXTENSION_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".cpp": "C++",
    ".c": "C",
    ".h": "C/C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".sh": "Shell",
    ".bash": "Bash",
    ".ps1": "PowerShell",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".xml": "XML",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "SASS",
    ".sql": "SQL",
    ".md": "Markdown",
    ".tf": "Terraform",
    ".dockerfile": "Dockerfile",
}

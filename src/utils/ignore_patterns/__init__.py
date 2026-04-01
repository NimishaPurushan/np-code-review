from .patterns import IGNORE_PATTERNS, UNWANTED_FILE_PATTERNS


def is_ignored_file(file_path: str) -> bool:
    return any(pattern.search(file_path) for pattern in IGNORE_PATTERNS) or any(
        pattern.search(file_path) for pattern in UNWANTED_FILE_PATTERNS
    )


def is_unwanted_file(file_path: str) -> bool:
    return any(pattern.search(file_path) for pattern in UNWANTED_FILE_PATTERNS)

from .patterns import IGNORE_PATTERNS


def is_ignored_file(file_path: str) -> bool:
    return any(pattern.match(file_path) for pattern in IGNORE_PATTERNS)

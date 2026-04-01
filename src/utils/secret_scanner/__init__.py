from .entropy_scanner import calculate_shannon_entropy, scan_entropy
from .pattern_scanner import scan_patterns
from .types import SecretMatch


def detect_secrets(
    text: str,
    enable_entropy: bool = True,
    entropy_threshold: float = 4.5,
    min_entropy_length: int = 20,
) -> list[SecretMatch]:
    matches = scan_patterns(text)

    if enable_entropy:
        matches.extend(scan_entropy(text, entropy_threshold, min_entropy_length))

    return _deduplicate(matches)


def _deduplicate(matches: list[SecretMatch]) -> list[SecretMatch]:
    seen = set()
    unique = []

    for match in matches:
        key = (match.type, match.value, match.line_number, match.column_start)
        if key not in seen:
            seen.add(key)
            unique.append(match)

    return unique


__all__ = [
    "detect_secrets",
    "SecretMatch",
    "scan_patterns",
    "scan_entropy",
    "calculate_shannon_entropy",
]

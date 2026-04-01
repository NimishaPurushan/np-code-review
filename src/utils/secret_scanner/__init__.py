from .entropy_scanner import calculate_shannon_entropy, scan_entropy
from .pattern_scanner import scan_patterns
from .types import SecretMatch

_PLACEHOLDER_MARKERS = (
    "your_",
    "changeme",
    "change_me",
    "placeholder",
    "<your",
    "todo: replace",
    "example_key",
    "sample_token",
    "insert_",
    "fake_",
    "dummy_",
    "test_token",
    "not_a_real",
)


def _filter_placeholder_matches(matches: list[SecretMatch], text: str) -> list[SecretMatch]:
    lines = text.splitlines()
    kept: list[SecretMatch] = []
    for m in matches:
        line = lines[m.line_number - 1] if 0 < m.line_number <= len(lines) else ""
        blob = f"{line} {m.value}".lower()
        if any(marker in blob for marker in _PLACEHOLDER_MARKERS):
            continue
        kept.append(m)
    return kept


def detect_secrets(
    text: str,
    enable_entropy: bool = True,
    entropy_threshold: float = 4.5,
    min_entropy_length: int = 20,
) -> list[SecretMatch]:
    matches = scan_patterns(text)

    if enable_entropy:
        matches.extend(scan_entropy(text, entropy_threshold, min_entropy_length))

    matches = _deduplicate(matches)
    return _filter_placeholder_matches(matches, text)


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

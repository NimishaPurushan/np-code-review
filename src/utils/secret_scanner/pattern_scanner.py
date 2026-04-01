from .patterns import COMPILED_PATTERNS
from .types import SecretMatch


def scan_patterns(text: str) -> list[SecretMatch]:
    matches = []
    lines = text.splitlines()

    for line_number, line in enumerate(lines, start=1):
        for secret_type, pattern in COMPILED_PATTERNS.items():
            for match in pattern.finditer(line):
                matches.append(
                    SecretMatch(
                        type=secret_type,
                        value=match.group(),
                        line_number=line_number,
                        column_start=match.start(),
                        column_end=match.end(),
                        confidence=1.0,
                    )
                )

    return matches

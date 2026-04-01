import math

from .patterns import ENTROPY_PATTERN
from .types import SecretMatch


def calculate_shannon_entropy(data: str) -> float:
    if not data:
        return 0.0

    char_count = {}
    for char in data:
        char_count[char] = char_count.get(char, 0) + 1

    length = len(data)
    entropy = 0.0
    for count in char_count.values():
        probability = count / length
        entropy -= probability * math.log2(probability)

    return entropy


def scan_entropy(text: str, threshold: float = 4.5, min_length: int = 20) -> list[SecretMatch]:
    matches = []
    lines = text.splitlines()

    for line_number, line in enumerate(lines, start=1):
        for match in ENTROPY_PATTERN.finditer(line):
            value = match.group()

            if len(value) < min_length:
                continue

            entropy = calculate_shannon_entropy(value)

            if entropy >= threshold:
                confidence = min(entropy / 6.0, 1.0)

                matches.append(
                    SecretMatch(
                        type="high_entropy",
                        value=value,
                        line_number=line_number,
                        column_start=match.start(),
                        column_end=match.end(),
                        confidence=confidence,
                    )
                )

    return matches

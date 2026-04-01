from dataclasses import dataclass


@dataclass
class SecretMatch:
    type: str
    value: str
    line_number: int
    column_start: int
    column_end: int
    confidence: float

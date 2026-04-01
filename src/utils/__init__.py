from .secret_scanner import SecretMatch, detect_secrets


def has_secrets(text: str) -> bool:
    return len(detect_secrets(text)) > 0


def scan_for_secrets(text: str) -> list[SecretMatch]:
    return detect_secrets(text)


__all__ = ["detect_secrets", "SecretMatch", "has_secrets", "scan_for_secrets"]

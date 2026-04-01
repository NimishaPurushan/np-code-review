"""Utility modules."""

from .secret_scanner import SecretMatch, detect_secrets

__all__ = ["detect_secrets", "SecretMatch"]

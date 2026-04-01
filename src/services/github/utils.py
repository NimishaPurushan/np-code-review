import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)


def verify_github_signature(payload: bytes, signature: str, secret: str) -> bool:
    hash_object = hmac.new(secret.encode(), msg=payload, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()

    is_valid = hmac.compare_digest(expected_signature, signature)

    if not is_valid:
        logger.warning(f"Invalid webhook signature. Expected prefix: {expected_signature[:20]}...")

    return is_valid

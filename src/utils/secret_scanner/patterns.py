from re import compile

_SECRET_PATTERNS = {
    "aws_access_key": r"AKIA[0-9A-Z]{16}",
    "aws_secret_key": r"(?i)(aws_secret_access_key|aws_secret|secret)\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?",
    "github_token": r"gh[pousr]_[a-zA-Z0-9]{36,}",
    "slack_token": r"xox[baprs]-[0-9a-zA-Z\-]+",
    "slack_webhook": r"https://hooks\.slack\.com/services/T[a-zA-Z0-9_]+/B[a-zA-Z0-9_]+/[a-zA-Z0-9_]+",
    "private_key_header": r"-----BEGIN (RSA|EC|OPENSSH)? PRIVATE KEY-----",
    "jwt": r"eyJ[a-zA-Z0-9_-]{5,}\.eyJ[a-zA-Z0-9_-]{5,}\.[a-zA-Z0-9_-]{5,}",
    "generic_api_key": r"(?i)(api[_-]?key|apikey|access[_-]?token|secret[_-]?key)\s*[:=]\s*['\"]([A-Za-z0-9_\-\/+=]{20,})['\"]",
    "password": r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]([^'\"]{12,})['\"]",
    "database_url": r"(postgres|mysql|mongodb):\/\/[a-zA-Z0-9._%-]+:[^@\s]+@[a-zA-Z0-9.-]+",
    "stripe_key": r"sk_live_[0-9a-zA-Z]{24,}",
    "square_token": r"sq0atp-[0-9A-Za-z\-_]{22}",
    "google_api_key": r"AIza[0-9A-Za-z\-_]{35}",
    "authorization_bearer": r"(?i)['\"]Bearer\s+[A-Za-z0-9_\-]{8,}['\"]",
    "authorization_header": r"(?i)['\"]Authorization['\"]:\s*['\"]Bearer\s+[A-Za-z0-9_\-]{8,}['\"]",
    "authorization_token": r"(?i)(authorization|auth[_-]?token|bearer)\s*[:=]\s*['\"]?([A-Za-z0-9_\-\/+=]{20,})['\"]?",
}


COMPILED_PATTERNS = {k: compile(v) for k, v in _SECRET_PATTERNS.items()}

ENTROPY_PATTERN = compile(r"[A-Za-z0-9+/=_-]{20,}")

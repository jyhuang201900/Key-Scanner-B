"""Strict normalization for leaked account lines."""
import re

import config


PREFIX_PATTERN = re.compile(
    r"^\s*(?:email_line|account_line|credential|account|result|line)\s*=\s*",
    re.IGNORECASE,
)
EMAIL_PATTERN = re.compile(
    r"[A-Za-z0-9._%+-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+"
)
CLIENT_ID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9._~!@#$%^&*+/=-]+")


def _strip_wrappers(value: str) -> str:
    clean = value.strip()
    wrapper_chars = "\"'`"
    trailing_chars = "\"'`),;]}"
    leading_chars = "\"'`([{"

    while clean and clean[-1] in trailing_chars:
        clean = clean[:-1].rstrip()
    while clean and clean[0] in leading_chars:
        clean = clean[1:].lstrip()
    while clean and clean[-1] in wrapper_chars:
        clean = clean[:-1].rstrip()
    return clean


def normalize_account_line(line: str) -> str | None:
    """Return canonical email----password----client_id----refresh_token."""
    clean = (line or "").strip()
    clean = PREFIX_PATTERN.sub("", clean, count=1)
    clean = clean.strip().strip("\"'`")

    parts = clean.split(config.ACCOUNT_SEPARATOR, 3)
    if len(parts) != 4:
        return None

    email = _strip_wrappers(parts[0])
    password = parts[1].strip()
    client_id = _strip_wrappers(parts[2])
    refresh_token = _strip_wrappers(parts[3])

    if not EMAIL_PATTERN.fullmatch(email):
        return None
    if not password or any(char.isspace() for char in password):
        return None
    if not CLIENT_ID_PATTERN.fullmatch(client_id):
        return None
    if len(refresh_token) < config.MIN_REFRESH_TOKEN_LENGTH:
        return None
    if not TOKEN_PATTERN.fullmatch(refresh_token):
        return None

    return config.ACCOUNT_SEPARATOR.join([
        email,
        password,
        client_id,
        refresh_token,
    ])

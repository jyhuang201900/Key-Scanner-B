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


def normalize_account_line(line: str) -> str | None:
    """Return canonical email----password----client_id----refresh_token."""
    clean = (line or "").strip()
    clean = PREFIX_PATTERN.sub("", clean, count=1)
    clean = clean.strip().strip("\"'`")

    parts = clean.split(config.ACCOUNT_SEPARATOR, 3)
    if len(parts) != 4:
        return None

    email = parts[0].strip().strip("\"'`")
    password = parts[1].strip()
    client_id = parts[2].strip().strip("\"'`")
    refresh_token = parts[3].strip().strip("\"'`")
    refresh_token = refresh_token.rstrip(",;)]}")

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

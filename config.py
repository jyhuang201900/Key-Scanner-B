"""Outlook credential scanner configuration."""
import os


# GitHub
def _github_token() -> str:
    raw = os.getenv("GITHUB_TOKEN", "").strip().strip('"').strip("'")
    lower = raw.lower()
    if lower.startswith("bearer "):
        raw = raw[7:].strip()
    elif lower.startswith("token "):
        raw = raw[6:].strip()
    return raw


GITHUB_TOKEN = _github_token()
GITHUB_API_BASE = "https://api.github.com"
MAX_PAGES = int(os.getenv("MAX_PAGES", "10"))
PER_PAGE = 100


# Leaked line format:
# email----password----client_id----refresh_token
ACCOUNT_SEPARATOR = "----"
CLIENT_ID = "9e5f94bc-e8a4-4e73-b8be-63364c29d753"
MIN_REFRESH_TOKEN_LENGTH = int(os.getenv("MIN_REFRESH_TOKEN_LENGTH", "80"))

_default_queries = "|".join([
    f'"{CLIENT_ID}" "{ACCOUNT_SEPARATOR}"',
    f'"M.C5" "{ACCOUNT_SEPARATOR}"',
    f'"M.C" "{ACCOUNT_SEPARATOR}"',
    '"M.C50"',
    '"M.C5"',
    '"MsaArtifacts"',
    '"BAY.0.U"',
    f'"refresh_token" "{ACCOUNT_SEPARATOR}"',
    f'"@outlook.com" "{ACCOUNT_SEPARATOR}"',
    f'"@hotmail.com" "{ACCOUNT_SEPARATOR}"',
    f'"@live.com" "{ACCOUNT_SEPARATOR}"',
    f'"@msn.com" "{ACCOUNT_SEPARATOR}"',
    f'"@yahoo.com" "{ACCOUNT_SEPARATOR}"',
    f'"@icloud.com" "{ACCOUNT_SEPARATOR}"',
    f'"@163.com" "{ACCOUNT_SEPARATOR}"',
    f'"@qq.com" "{ACCOUNT_SEPARATOR}"',
    'filename:results.txt "M.C"',
    'filename:accounts.txt "M.C"',
    'filename:outlook.txt "M.C"',
    f'extension:txt "M.C" "{ACCOUNT_SEPARATOR}"',
])
SEARCH_QUERIES = [
    item.strip()
    for item in os.getenv("SEARCH_QUERIES", _default_queries).split("|")
    if item.strip()
]


# Limits and pacing
MAX_FILES_PER_QUERY = int(os.getenv("MAX_FILES_PER_QUERY", "250"))
MAX_FILES_PER_SCAN = int(os.getenv("MAX_FILES_PER_SCAN", "5000"))
MAX_FILE_BYTES = int(os.getenv("MAX_FILE_BYTES", "2000000"))
DOWNLOAD_WORKERS = int(os.getenv("DOWNLOAD_WORKERS", "12"))
MIN_REMAINING_REQUESTS = 5
ABUSE_WAIT_TIME = 300
REQUEST_DELAY_MIN = 0.02
REQUEST_DELAY_MAX = 0.08
REQUEST_TIMEOUT = 30


# Output
RESULTS_FILE = os.getenv("RESULTS_FILE", "results.txt")

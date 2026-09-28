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

_default_plan = [
    ('"MsaArtifacts"', 12),
    ('"BAY.0.U"', 6),
    ('"M.C5"', 6),
    ('"@hotmail.com" "MsaArtifacts"', 6),
    ('"@outlook.com" "MsaArtifacts"', 6),
    ('"@live.com" "MsaArtifacts"', 6),
    ('"@msn.com" "MsaArtifacts"', 6),
    ('"@hotmail.com" "refresh_token"', 4),
    ('"@outlook.com" "refresh_token"', 4),
    ('"@live.com" "refresh_token"', 4),
    ('"@msn.com" "refresh_token"', 4),
    ('"@hotmail.com" "M.C"', 3),
    ('"@outlook.com" "M.C"', 3),
    ('"@live.com" "M.C"', 3),
    ('"@msn.com" "M.C"', 3),
    ('filename:results.txt "MsaArtifacts"', 3),
    ('filename:accounts.txt "MsaArtifacts"', 3),
    ('filename:outlook.txt "MsaArtifacts"', 3),
    ('filename:tokens.txt "MsaArtifacts"', 3),
    ('extension:txt "MsaArtifacts"', 3),
    ('extension:txt "@hotmail.com"', 3),
    ('extension:txt "@outlook.com"', 3),
]
_override_queries = os.getenv("SEARCH_QUERIES", "").strip()
if _override_queries:
    SEARCH_PLAN = [
        (item.strip(), 1)
        for item in _override_queries.split("|")
        if item.strip()
    ]
else:
    SEARCH_PLAN = _default_plan
SEARCH_QUERIES = [query for query, _ in SEARCH_PLAN]


# Limits and pacing
MAX_FILES_PER_QUERY = int(os.getenv("MAX_FILES_PER_QUERY", "120"))
MAX_FILES_PER_SCAN = int(os.getenv("MAX_FILES_PER_SCAN", "600"))
MAX_FILE_BYTES = int(os.getenv("MAX_FILE_BYTES", "2000000"))
DOWNLOAD_WORKERS = int(os.getenv("DOWNLOAD_WORKERS", "16"))
MIN_REMAINING_REQUESTS = 5
ABUSE_WAIT_TIME = 300
REQUEST_DELAY_MIN = 0.02
REQUEST_DELAY_MAX = 0.08
REQUEST_TIMEOUT = 30


# Output
RESULTS_FILE = os.getenv("RESULTS_FILE", "results.txt")

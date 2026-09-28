"""Outlook credential scanner configuration."""
import os


# GitHub
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_API_BASE = "https://api.github.com"
MAX_PAGES = int(os.getenv("MAX_PAGES", "3"))
PER_PAGE = 100


# Leaked line format:
# email----password----client_id----refresh_token
ACCOUNT_SEPARATOR = "----"
CLIENT_ID = "9e5f94bc-e8a4-4e73-b8be-63364c29d753"
MIN_REFRESH_TOKEN_LENGTH = int(os.getenv("MIN_REFRESH_TOKEN_LENGTH", "80"))

_default_queries = "|".join([
    f'"{CLIENT_ID}" "{ACCOUNT_SEPARATOR}"',
    f'"M.C" "{ACCOUNT_SEPARATOR}"',
    f'"refresh_token" "{ACCOUNT_SEPARATOR}"',
    f'"@outlook.com" "{ACCOUNT_SEPARATOR}"',
    f'"@hotmail.com" "{ACCOUNT_SEPARATOR}"',
])
SEARCH_QUERIES = [
    item.strip()
    for item in os.getenv("SEARCH_QUERIES", _default_queries).split("|")
    if item.strip()
]


# Limits and pacing
MAX_FILES_PER_SCAN = int(os.getenv("MAX_FILES_PER_SCAN", "500"))
MAX_FILE_BYTES = int(os.getenv("MAX_FILE_BYTES", "2000000"))
MIN_REMAINING_REQUESTS = 5
ABUSE_WAIT_TIME = 300
REQUEST_DELAY_MIN = 0.3
REQUEST_DELAY_MAX = 0.8


# Output
RESULTS_FILE = os.getenv("RESULTS_FILE", "results.txt")

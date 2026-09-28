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
    # 高密度目标是大文件：每行约 500 字节，50KB≈100 行，200KB≈400 行
    ('"@hotmail.com" size:>200000', 10),
    ('"@outlook.com" size:>200000', 10),
    ('"@hotmail.com" size:>50000', 8),
    ('"@outlook.com" size:>50000', 8),
    # 邮箱单关键词查询：每个查询独享 1000 条结果窗口
    ('"@hotmail.com"', 6),
    ('"@outlook.com"', 6),
    # 单一内容指纹查询，不与邮箱组合；dump 文件必然是大文件
    ('"MsaArtifacts"', 6),
    ('"M.C5"', 6),
    ('"BAY.0.U"', 6),
    ('"@hotmail.com" extension:txt', 5),
    ('"@outlook.com" extension:txt', 5),
    ('"@hotmail.com" extension:csv', 4),
    ('"@outlook.com" extension:csv', 4),
    ('"@hotmail.com" extension:json', 4),
    ('"@outlook.com" extension:json', 4),
    ('filename:results.txt "@hotmail.com"', 3),
    ('filename:results.txt "@outlook.com"', 3),
    ('filename:accounts.txt "@hotmail.com"', 3),
    ('filename:accounts.txt "@outlook.com"', 3),
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
MAX_FILES_PER_QUERY = int(os.getenv("MAX_FILES_PER_QUERY", "500"))
MAX_FILES_PER_SCAN = int(os.getenv("MAX_FILES_PER_SCAN", "3000"))
MAX_FILE_BYTES = int(os.getenv("MAX_FILE_BYTES", "2000000"))
DOWNLOAD_WORKERS = int(os.getenv("DOWNLOAD_WORKERS", "16"))
# 单文件命中行数达到该值即视为高密度 dump 文件
DENSE_FILE_LINES = int(os.getenv("DENSE_FILE_LINES", "20"))
MIN_REMAINING_REQUESTS = 5
ABUSE_WAIT_TIME = 300
REQUEST_DELAY_MIN = 0.02
REQUEST_DELAY_MAX = 0.08
REQUEST_TIMEOUT = 30


# Output
RESULTS_FILE = os.getenv("RESULTS_FILE", "results.txt")
STATS_FILE = os.getenv("STATS_FILE", "scan_stats.json")

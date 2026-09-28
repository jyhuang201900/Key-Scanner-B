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
    # A. 稀有指纹：全网仅 142 个文件，结果不会被 1000 上限截断
    ('MsaArtifacts', 8),
    ('MsaArtifacts hotmail', 8),
    ('MsaArtifacts outlook', 8),
    # B. filename 分区：泄露文件命名可预测，是唯一未验证的高潜力切分轴
    ('hotmail filename:results', 5),
    ('outlook filename:results', 5),
    ('hotmail filename:accounts', 5),
    ('outlook filename:accounts', 5),
    ('hotmail filename:token', 5),
    ('outlook filename:token', 5),
    ('hotmail filename:email', 5),
    ('outlook filename:email', 5),
    # C. 纯字母数字共现词，缩小裸域名查询的范围
    ('hotmail refreshtoken', 3),
    ('outlook refreshtoken', 3),
    ('hotmail clientid', 3),
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

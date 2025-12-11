"""配置文件"""
import os

# GitHub配置
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')
GITHUB_API_BASE = 'https://api.github.com'

# 搜索配置
SEARCH_PREFIX = 'AIzaSy'
MIN_KEY_LENGTH = 39
MAX_PAGES = 10
PER_PAGE = 100

# API验证
GEMINI_API_BASE = 'https://generativelanguage.googleapis.com/v1beta/models'
MAX_WORKERS = 15
REQUEST_TIMEOUT = 10

# 速率限制
MIN_REMAINING_REQUESTS = 5
ABUSE_WAIT_TIME = 300
REQUEST_DELAY_MIN = 2
REQUEST_DELAY_MAX = 5

# 文件路径
OUTPUT_DIR = 'output'
FOUND_KEYS_FILE = f'{OUTPUT_DIR}/found_keys.json'
VALID_KEYS_FILE = f'{OUTPUT_DIR}/valid_keys.json'
LOG_FILE = f'{OUTPUT_DIR}/scanner.log'

# 过滤配置
EXCLUDE_PATTERNS = ['example', 'test', 'demo', 'sample', 'fake', 'placeholder', 
                    'your', 'xxxx', 'yyyy', 'zzzz', 'mock', 'dummy', 'invalid']
MIN_UNIQUE_CHARS = 10

"""核心扫描器"""
import requests
import time
import random
import re
from datetime import datetime, timedelta
from typing import Set, List, Dict
from tqdm import tqdm
import config

class KeyScanner:
    def __init__(self):
        if not config.GITHUB_TOKEN:
            raise ValueError("请设置GITHUB_TOKEN环境变量")
        self.headers = {
            'Authorization': f'token {config.GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3.text-match+json'
        }
        self.found_keys: Set[str] = set()
        
    def check_rate_limit(self) -> None:
        """检查并处理速率限制"""
        try:
            resp = requests.get(f'{config.GITHUB_API_BASE}/rate_limit', 
                              headers=self.headers, timeout=10)
            resp.raise_for_status()
            rate = resp.json()['resources']['search']
            remaining = rate['remaining']
            
            if remaining < config.MIN_REMAINING_REQUESTS:
                reset_time = rate['reset']
                wait = max(0, reset_time - time.time()) + 5
                print(f"⏳ 速率限制，等待 {wait:.0f}秒")
                time.sleep(wait)
        except Exception as e:
            print(f"⚠️  检查速率限制失败: {e}")
            time.sleep(60)
    
    def is_valid_key(self, key: str) -> bool:
        """验证密钥格式"""
        if not key.startswith(config.SEARCH_PREFIX) or len(key) < config.MIN_KEY_LENGTH:
            return False
        
        key_lower = key.lower()
        if any(pattern in key_lower for pattern in config.EXCLUDE_PATTERNS):
            return False
        
        if len(set(key)) < config.MIN_UNIQUE_CHARS:
            return False
        
        if not re.match(r'^[A-Za-z0-9_-]+$', key):
            return False
            
        return True
    
    def extract_keys_from_content(self, content: str) -> Set[str]:
        """从内容中提取密钥"""
        keys = set()
        pattern = rf'{config.SEARCH_PREFIX}[A-Za-z0-9_-]{{33,}}'
        matches = re.findall(pattern, content)
        
        for match in matches:
            if self.is_valid_key(match):
                keys.add(match)
        return keys
    
    def search_github(self, query: str) -> Set[str]:
        """搜索GitHub代码"""
        found = set()
        url = f'{config.GITHUB_API_BASE}/search/code'
        params = {'q': query, 'per_page': config.PER_PAGE, 'page': 1}
        
        try:
            for page in range(1, config.MAX_PAGES + 1):
                self.check_rate_limit()
                params['page'] = page
                
                resp = requests.get(url, headers=self.headers, params=params, timeout=15)
                
                if resp.status_code == 403:
                    print("⚠️  触发滥用检测，等待5分钟")
                    time.sleep(config.ABUSE_WAIT_TIME)
                    continue
                
                if resp.status_code != 200:
                    break
                
                data = resp.json()
                items = data.get('items', [])
                
                if not items:
                    break
                
                for item in items:
                    repo = item.get('repository', {}).get('full_name', 'unknown')
                    for match in item.get('text_matches', []):
                        fragment = match.get('fragment', '')
                        keys = self.extract_keys_from_content(fragment)
                        for key in keys:
                            if key not in self.found_keys:
                                found.add(key)
                                self.found_keys.add(key)
                                print(f"  ✓ {key[:15]}... ({repo})")
                
                if 'next' not in resp.links:
                    break
                    
                time.sleep(random.uniform(config.REQUEST_DELAY_MIN, 
                                        config.REQUEST_DELAY_MAX))
                
        except Exception as e:
            print(f"搜索错误: {e}")
            time.sleep(30)
        
        return found
    
    def generate_queries(self) -> List[str]:
        """生成搜索查询"""
        queries = []
        
        now = datetime.now()
        for months_back in range(0, 12):
            date = now - timedelta(days=30 * months_back)
            year_month = date.strftime('%Y-%m')
            queries.append(f'"{config.SEARCH_PREFIX}" created:{year_month}')
        
        chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'
        for char in chars:
            queries.append(f'"{config.SEARCH_PREFIX}{char}"')
        
        languages = ['python', 'javascript', 'java', 'go', 'php', 'ruby']
        for lang in languages:
            queries.append(f'"{config.SEARCH_PREFIX}" language:{lang}')
        
        return queries
    
    def scan(self) -> Dict[str, any]:
        """执行扫描"""
        print("🚀 开始扫描...")
        queries = self.generate_queries()
        print(f"📝 生成 {len(queries)} 个查询")
        
        total_found = 0
        start_time = time.time()
        
        for query in tqdm(queries, desc="扫描进度"):
            tqdm.write(f"🔍 {query}")
            new_keys = self.search_github(query)
            total_found += len(new_keys)
        
        elapsed = time.time() - start_time
        
        return {
            'total_queries': len(queries),
            'total_found': total_found,
            'unique_keys': len(self.found_keys),
            'elapsed_time': elapsed,
            'keys': list(self.found_keys)
        }

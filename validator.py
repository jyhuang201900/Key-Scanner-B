"""密钥验证器"""
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple
import time
import config

class KeyValidator:
    def __init__(self):
        self.valid_keys: List[str] = []
        self.invalid_keys: List[str] = []
        
    def validate_key(self, key: str) -> Tuple[bool, str, str]:
        """验证单个密钥"""
        url = f'{config.GEMINI_API_BASE}?key={key}'
        try:
            resp = requests.get(url, timeout=config.REQUEST_TIMEOUT)
            
            if resp.status_code == 200:
                data = resp.json()
                if 'models' in data:
                    models = [m.get('name', '') for m in data.get('models', [])]
                    return True, key, f"有效 (模型数: {len(models)})"
            elif resp.status_code == 429:
                # 速率限制但密钥有效
                return True, key, "有效 (速率限制)"
            elif resp.status_code == 400:
                error_msg = resp.json().get('error', {}).get('message', '')
                if 'API key not valid' in error_msg:
                    return False, key, "无效密钥"
            
            return False, key, f"状态码: {resp.status_code}"
            
        except Exception as e:
            return False, key, f"错误: {str(e)[:50]}"
    
    def validate_batch(self, keys: List[str]) -> Dict[str, any]:
        """批量验证密钥"""
        if not keys:
            return {'valid': [], 'invalid': [], 'total': 0}
        
        print(f"\n🔍 开始验证 {len(keys)} 个密钥...")
        start_time = time.time()
        
        valid = []
        invalid = []
        
        with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
            futures = {executor.submit(self.validate_key, key): key 
                      for key in keys}
            
            for i, future in enumerate(as_completed(futures), 1):
                try:
                    is_valid, key, msg = future.result()
                    
                    if is_valid:
                        valid.append(key)
                        print(f"✅ [{i}/{len(keys)}] {key[:15]}... - {msg}")
                    else:
                        invalid.append(key)
                        print(f"❌ [{i}/{len(keys)}] {key[:15]}... - {msg}")
                        
                except Exception as e:
                    print(f"⚠️  处理失败: {e}")
        
        elapsed = time.time() - start_time
        
        result = {
            'valid': valid,
            'invalid': invalid,
            'total': len(keys),
            'valid_count': len(valid),
            'invalid_count': len(invalid),
            'elapsed_time': elapsed
        }
        
        print(f"\n✨ 验证完成!")
        print(f"⏱️  耗时: {elapsed:.2f}秒")
        print(f"✅ 有效: {len(valid)}")
        print(f"❌ 无效: {len(invalid)}")
        
        return result

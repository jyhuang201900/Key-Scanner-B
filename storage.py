"""存储管理"""
import json
import os
from datetime import datetime
from typing import List, Dict
import config

class Storage:
    def __init__(self):
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    
    def save_scan_result(self, result: Dict) -> str:
        """保存扫描结果"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'scan_info': {
                'total_queries': result.get('total_queries', 0),
                'total_found': result.get('total_found', 0),
                'unique_keys': result.get('unique_keys', 0),
                'elapsed_time': result.get('elapsed_time', 0)
            },
            'keys': result.get('keys', [])
        }
        
        with open(config.FOUND_KEYS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return config.FOUND_KEYS_FILE
    
    def save_validation_result(self, result: Dict) -> str:
        """保存验证结果"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'validation_info': {
                'total': result.get('total', 0),
                'valid_count': result.get('valid_count', 0),
                'invalid_count': result.get('invalid_count', 0),
                'elapsed_time': result.get('elapsed_time', 0)
            },
            'valid_keys': result.get('valid', []),
            'invalid_keys': result.get('invalid', [])
        }
        
        with open(config.VALID_KEYS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return config.VALID_KEYS_FILE
    
    def load_found_keys(self) -> List[str]:
        """加载找到的密钥"""
        if not os.path.exists(config.FOUND_KEYS_FILE):
            return []
        
        try:
            with open(config.FOUND_KEYS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('keys', [])
        except:
            return []
    
    def load_valid_keys(self) -> List[str]:
        """加载有效密钥"""
        if not os.path.exists(config.VALID_KEYS_FILE):
            return []
        
        try:
            with open(config.VALID_KEYS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('valid_keys', [])
        except:
            return []
    
    def export_plain_text(self, keys: List[str], filename: str) -> str:
        """导出为纯文本"""
        filepath = f'{config.OUTPUT_DIR}/{filename}'
        with open(filepath, 'w', encoding='utf-8') as f:
            for key in keys:
                f.write(f"{key}\n")
        return filepath

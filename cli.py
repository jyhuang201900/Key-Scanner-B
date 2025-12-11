"""命令行接口"""
import argparse
from scanner import KeyScanner
from validator import KeyValidator
from storage import Storage

def main():
    parser = argparse.ArgumentParser(description='Gemini API Key Scanner')
    parser.add_argument('action', choices=['scan', 'validate', 'both'],
                       help='执行的操作')
    parser.add_argument('--export-txt', action='store_true',
                       help='导出为txt文件')
    
    args = parser.parse_args()
    storage = Storage()
    
    if args.action in ['scan', 'both']:
        print("\n" + "="*50)
        print("🔍 开始扫描GitHub")
        print("="*50)
        scanner = KeyScanner()
        result = scanner.scan()
        storage.save_scan_result(result)
        
        print(f"\n✅ 扫描完成!")
        print(f"📊 查询数: {result['total_queries']}")
        print(f"🔑 发现密钥: {result['unique_keys']}")
        print(f"⏱️  耗时: {result['elapsed_time']:.2f}秒")
    
    if args.action in ['validate', 'both']:
        print("\n" + "="*50)
        print("🔍 开始验证密钥")
        print("="*50)
        keys = storage.load_found_keys()
        
        if not keys:
            print("❌ 没有找到密钥，请先运行扫描")
            return
        
        validator = KeyValidator()
        result = validator.validate_batch(keys)
        storage.save_validation_result(result)
        
        if args.export_txt and result['valid']:
            txt_file = storage.export_plain_text(result['valid'], 'valid_keys.txt')
            print(f"\n📄 已导出到: {txt_file}")

if __name__ == '__main__':
    main()

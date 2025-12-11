"""Flask API服务"""
from flask import Flask, jsonify, request
import os
from scanner import KeyScanner
from validator import KeyValidator
from storage import Storage
import config

app = Flask(__name__)
storage = Storage()

@app.route('/')
def index():
    """API首页"""
    return jsonify({
        'name': 'Gemini Key Scanner API',
        'version': '2.0',
        'endpoints': {
            '/scan': 'POST - 执行密钥扫描',
            '/validate': 'POST - 验证密钥',
            '/keys': 'GET - 获取所有找到的密钥',
            '/valid-keys': 'GET - 获取有效密钥',
            '/stats': 'GET - 获取统计信息'
        }
    })

@app.route('/scan', methods=['POST'])
def scan():
    """执行扫描"""
    try:
        scanner = KeyScanner()
        result = scanner.scan()
        storage.save_scan_result(result)
        
        return jsonify({
            'success': True,
            'data': {
                'total_queries': result['total_queries'],
                'total_found': result['total_found'],
                'unique_keys': result['unique_keys'],
                'elapsed_time': round(result['elapsed_time'], 2)
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/validate', methods=['POST'])
def validate():
    """验证密钥"""
    try:
        data = request.get_json()
        keys = data.get('keys', [])
        
        if not keys:
            keys = storage.load_found_keys()
        
        if not keys:
            return jsonify({'success': False, 'error': '没有密钥需要验证'}), 400
        
        validator = KeyValidator()
        result = validator.validate_batch(keys)
        storage.save_validation_result(result)
        
        return jsonify({
            'success': True,
            'data': {
                'total': result['total'],
                'valid_count': result['valid_count'],
                'invalid_count': result['invalid_count'],
                'elapsed_time': round(result['elapsed_time'], 2)
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/keys', methods=['GET'])
def get_keys():
    """获取所有找到的密钥"""
    keys = storage.load_found_keys()
    return jsonify({
        'success': True,
        'count': len(keys),
        'keys': keys
    })

@app.route('/valid-keys', methods=['GET'])
def get_valid_keys():
    """获取有效密钥"""
    keys = storage.load_valid_keys()
    return jsonify({
        'success': True,
        'count': len(keys),
        'keys': keys
    })

@app.route('/stats', methods=['GET'])
def get_stats():
    """获取统计信息"""
    found_keys = storage.load_found_keys()
    valid_keys = storage.load_valid_keys()
    
    return jsonify({
        'success': True,
        'stats': {
            'total_found': len(found_keys),
            'total_valid': len(valid_keys),
            'validation_rate': round(len(valid_keys) / len(found_keys) * 100, 2) if found_keys else 0
        }
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

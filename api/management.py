# Server/api/management.py
import os
import sys
import psutil
import subprocess
import functools
from flask import Blueprint, request, jsonify, current_app
from extensions import limiter

management_endpoint = Blueprint('management', __name__, url_prefix='/api/management')

def admin_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('X-Admin-Token')
        correct_token = os.environ.get('ADMIN_SECRET_TOKEN')
        if not token or token != correct_token:
            return jsonify(error="Unauthorized"), 401
        return f(*args, **kwargs)
    return decorated_function

@management_endpoint.route('/status', methods=['GET'])
@admin_required
def get_status():
    try:
        process = psutil.Process(os.getpid())
        return jsonify({
            'status': 'Running',
            'pid': os.getpid(),
            'cpu_usage': psutil.cpu_percent(interval=None),
            'ram_usage': psutil.virtual_memory().percent,
            'memory_info': process.memory_info()._asdict(),
            'uptime': process.create_time()
        })
    except Exception as e:
        return jsonify(error=str(e)), 500

@management_endpoint.route('/restart', methods=['POST'])
@admin_required
def restart_server():
    """Restart the server process."""
    try:
        # Trigger restart in a separate process to avoid killing the response
        python = sys.executable
        os.execv(python, [python] + sys.argv)
        return jsonify(success=True, message="Restarting...")
    except Exception as e:
        return jsonify(error=str(e)), 500

@management_endpoint.route('/execute', methods=['POST'])
@admin_required
def execute_command():
    data = request.get_json()
    command = data.get('command')
    if not command:
        return jsonify(error="No command provided"), 400
    
    try:
        # Chạy lệnh trong thư mục gốc của server chính
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30, cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        return jsonify({
            'stdout': result.stdout,
            'stderr': result.stderr,
            'exit_code': result.returncode
        })
    except subprocess.TimeoutExpired:
        return jsonify(error="Command timed out"), 408
    except Exception as e:
        return jsonify(error=str(e)), 500

# === REMOTE FILE MANAGEMENT ===
def is_safe_path(path_to_check):
    # Đảm bảo không truy cập ra ngoài thư mục dự án
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    requested_path = os.path.abspath(os.path.join(base_dir, path_to_check))
    return requested_path.startswith(base_dir)

@management_endpoint.route('/files/list', methods=['GET'])
@admin_required
def list_files():
    path = request.args.get('path', '.')
    if not is_safe_path(path): return jsonify(error="Forbidden"), 403
    
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        abs_path = os.path.join(base_dir, path)
        items = []
        for item in sorted(os.listdir(abs_path)):
            item_path = os.path.join(abs_path, item)
            items.append({
                'name': item,
                'type': 'directory' if os.path.isdir(item_path) else 'file',
                'size': os.path.getsize(item_path) if os.path.isfile(item_path) else 0
            })
        return jsonify(items)
    except Exception as e:
        return jsonify(error=str(e)), 500

@management_endpoint.route('/files/content', methods=['GET'])
@admin_required
def get_file_content():
    filepath = request.args.get('filepath')
    if not is_safe_path(filepath): return jsonify(error="Forbidden"), 403
    
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        abs_path = os.path.join(base_dir, filepath)
        with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
            return jsonify(content=f.read())
    except Exception as e:
        return jsonify(error=str(e)), 500

@management_endpoint.route('/files/content', methods=['POST'])
@admin_required
def save_file_content():
    data = request.get_json()
    filepath = data.get('filepath')
    content = data.get('content')
    if not is_safe_path(filepath): return jsonify(error="Forbidden"), 403
    
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        abs_path = os.path.join(base_dir, filepath)
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(error=str(e)), 500

@management_endpoint.route('/config', methods=['GET', 'POST'])
@admin_required
def manage_config():
    config_path = 'config.json'
    if request.method == 'GET':
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                import json
                return jsonify(json.load(f))
        return jsonify(error="Config file not found"), 404
    
    if request.method == 'POST':
        data = request.get_json()
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                import json
                json.dump(data, f, indent=4, ensure_ascii=False)
            return jsonify(success=True, message="Config updated")
        except Exception as e:
            return jsonify(error=str(e)), 500

@management_endpoint.route('/test-key', methods=['POST'])
@admin_required
def test_key():
    data = request.get_json()
    provider = data.get('provider')
    api_key = data.get('api_key')
    
    if provider == 'gemini':
        import google.generativeai as genai
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content("Ping")
            return jsonify(success=True, message="Gemini API Key is valid")
        except Exception as e:
            return jsonify(success=False, message=str(e))
            
    elif provider == 'virustotal':
        import requests
        try:
            url = f"https://www.virustotal.com/api/v3/users/me"
            headers = {"x-apikey": api_key}
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                return jsonify(success=True, message="VirusTotal API Key is valid")
            return jsonify(success=False, message=resp.json().get('error', {}).get('message', 'Invalid key'))
        except Exception as e:
            return jsonify(success=False, message=str(e))
            
    return jsonify(error="Unsupported provider"), 400

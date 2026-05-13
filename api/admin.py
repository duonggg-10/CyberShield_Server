# api/admin.py
import functools
import json
import os
import psutil # << IMPORT MỚI
import sys # << IMPORT MỚI
from flask import (
    Blueprint, request, render_template, redirect, url_for, session, flash, jsonify
)
from api.utils import get_dynamic_config # Import hàm đọc config dùng chung
from extensions import limiter
from api.logger import audit_log # << IMPORT AUDIT LOGGER

admin_endpoint = Blueprint('admin', __name__, url_prefix='/admin')

# Lấy đường dẫn gốc của dự án
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


# --- HÀM BẢO MẬT NÂNG CẤP ---
def is_safe_path(path_to_check):
    """
    Kiểm tra bảo mật nghiêm ngặt.
    CHỈ CHO PHÉP truy cập vào các file cấu hình (.json, .txt, .log) cụ thể.
    CHẶN TUYỆT ĐỐI việc đọc source code (.py) hoặc secrets (.env, .db).
    """
    # 1. Chống Path Traversal cơ bản
    if '..' in path_to_check or path_to_check.startswith('/'):
        return False
        
    requested_path = os.path.abspath(os.path.join(PROJECT_ROOT, path_to_check))
    
    # 2. Phải nằm trong thư mục dự án
    if not requested_path.startswith(PROJECT_ROOT):
        return False

    # 3. [QUAN TRỌNG] WHITELIST EXTENSIONS - Chỉ cho phép các đuôi file vô hại
    ALLOWED_EXTENSIONS = {'.json', '.txt', '.log', '.html', '.css', '.js', '.md'}
    _, ext = os.path.splitext(requested_path)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        audit_log.critical(f"Security Alert: Attempt to access unauthorized file type '{ext}' at {path_to_check}")
        return False

    # 4. BLACKLIST SPECIFIC FILES - Chặn các file nhạy cảm dù đúng đuôi
    SENSITIVE_FILES = {'secrets', 'token.json', 'google_credentials.json', '.env'}
    for part in requested_path.split(os.sep):
        if part in SENSITIVE_FILES:
            audit_log.critical(f"Security Alert: Attempt to access sensitive file/folder '{part}'")
            return False

    return True

# --- DECORATOR ĐỂ BẢO VỆ ---
# ... (giữ nguyên phần login_required)
def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'admin_logged_in' not in session:
            if request.path.startswith('/api/'):
                return jsonify(error="Authentication required"), 401
            return redirect(url_for('admin.login'))
        return view(**kwargs)
    return wrapped_view

# --- ROUTE GIAO DIỆN (UI) ---
@admin_endpoint.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute") # << THÊM RATE LIMIT
def login():
    # ... (giữ nguyên)
    if 'admin_logged_in' in session:
        return redirect(url_for('admin.dashboard'))
    if request.method == 'POST':
        submitted_token = request.form.get('token')
        # Lấy token từ biến môi trường thay vì config file
        correct_token = os.environ.get('ADMIN_SECRET_TOKEN')
        if submitted_token and correct_token and submitted_token == correct_token:
            session['admin_logged_in'] = True
            session.permanent = True
            audit_log.info(f"Successful login from IP: {request.remote_addr}") # << AUDIT LOG
            return redirect(url_for('admin.dashboard'))
        else:
            audit_log.warning(f"Failed login attempt from IP: {request.remote_addr}") # << AUDIT LOG
            flash('Admin Secret Token không chính xác!')
    return render_template('admin_login.html')

@admin_endpoint.route('/')
@login_required
def dashboard():
    return render_template('admin_dashboard.html')

@admin_endpoint.route('/logout')
def logout():
    audit_log.info(f"Successful logout from IP: {request.remote_addr}") # << AUDIT LOG
    session.clear()
    return redirect(url_for('admin.login'))

# --- API ENDPOINTS CHO ADMIN ---

# API cho Config Editor
@admin_endpoint.route('/api/config', methods=['GET', 'POST'])
@login_required
def config_api():
    if request.method == 'GET':
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                return jsonify(json.load(f))
        except Exception as e:
            return jsonify(error=f"Lỗi khi đọc file: {str(e)}"), 500
    
    if request.method == 'POST':
        if not request.is_json:
            return jsonify(error="Yêu cầu phải là dạng JSON."), 400
        try:
            new_config = request.get_json()
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(new_config, f, indent=2, ensure_ascii=False)
            audit_log.info(f"Config updated by IP: {request.remote_addr}. New config: {json.dumps(new_config)}") # << AUDIT LOG
            return jsonify(success=True, message="Cập nhật config.json thành công!")
        except Exception as e:
            return jsonify(error=f"Lỗi khi ghi file: {str(e)}"), 500

# === API MỚI CHO FILE EDITOR ===

@admin_endpoint.route('/api/files', methods=['GET'])
@login_required
def list_files_api():
    """API để liệt kê các file và thư mục."""
    try:
        path = request.args.get('path', '.') # Lấy path từ query param, mặc định là thư mục gốc
        if not is_safe_path(path):
            return jsonify(error="Truy cập bị từ chối."), 403

        abs_path = os.path.join(PROJECT_ROOT, path)
        items = []
        for item in sorted(os.listdir(abs_path)):
            item_path = os.path.join(abs_path, item)
            if os.path.isdir(item_path):
                items.append({'name': item, 'type': 'directory'})
            else:
                items.append({'name': item, 'type': 'file'})
        return jsonify(items)
    except Exception as e:
        return jsonify(error=f"Lỗi khi liệt kê file: {str(e)}"), 500

@admin_endpoint.route('/api/file-content', methods=['GET'])
@login_required
def get_file_content_api():
    """API để đọc nội dung file."""
    filepath = request.args.get('filepath')
    if not filepath:
        return jsonify(error="Thiếu tham số 'filepath'"), 400
    if not is_safe_path(filepath):
        return jsonify(error="Truy cập bị từ chối."), 403
    
    try:
        abs_path = os.path.join(PROJECT_ROOT, filepath)
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify(content=content, filepath=filepath)
    except Exception as e:
        return jsonify(error=f"Không thể đọc file: {str(e)}"), 500

@admin_endpoint.route('/api/file-content', methods=['POST'])
@login_required
def update_file_content_api():
    """API để ghi nội dung vào file."""
    data = request.get_json()
    filepath = data.get('filepath')
    content = data.get('content')

    if not filepath or content is None:
        return jsonify(error="Thiếu 'filepath' hoặc 'content'."), 400
    if not is_safe_path(filepath):
        audit_log.warning(f"Path traversal attempt blocked from IP: {request.remote_addr}. Path: {filepath}") # << AUDIT LOG
        return jsonify(error="Truy cập bị từ chối."), 403

    try:
        abs_path = os.path.join(PROJECT_ROOT, filepath)
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(content)
        audit_log.info(f"File '{filepath}' saved by IP: {request.remote_addr}") # << AUDIT LOG
        return jsonify(success=True, message=f"Đã lưu file '{filepath}' thành công!")
    except Exception as e:
        return jsonify(error=f"Không thể ghi file: {str(e)}"), 500

# === API MỚI CHO SYSTEM STATUS ===
@admin_endpoint.route('/api/system-metrics', methods=['GET'])
@login_required
def get_system_metrics_api():
    """API để lấy thông số hệ thống (CPU, RAM, Disk)."""
    try:
        cpu_usage = psutil.cpu_percent(interval=1)
        ram_usage = psutil.virtual_memory().percent
        disk_usage = psutil.disk_usage('/').percent
        return jsonify({
            'cpu': cpu_usage,
            'ram': ram_usage,
            'disk': disk_usage
        })
    except Exception as e:
        return jsonify(error=f"Lỗi khi lấy thông số hệ thống: {str(e)}"), 500

# === API MỚI CHO LOG VIEWER ===
@admin_endpoint.route('/api/logs', methods=['GET'])
@login_required
def get_logs_api():
    """API để lấy N dòng log gần nhất từ nohup.out."""
    LOG_FILE_PATH = 'nohup.out' # Tên file log chính
    NUM_LINES = request.args.get('lines', 100, type=int) # Mặc định lấy 100 dòng

    if not os.path.exists(LOG_FILE_PATH):
        return jsonify(error="File log không tồn tại."), 404

    try:
        with open(LOG_FILE_PATH, 'r', encoding='utf-8', errors='ignore') as f:
            # Đọc tất cả các dòng và chỉ lấy N dòng cuối cùng
            lines = f.readlines()
            last_n_lines = "".join(lines[-NUM_LINES:])
        return jsonify(logs=last_n_lines)
    except Exception as e:
        return jsonify(error=f"Lỗi khi đọc file log: {str(e)}"), 500

# === API MỚI CHO SERVER ACTIONS ===
@admin_endpoint.route('/api/server/restart', methods=['POST'])
@login_required
def restart_server_api():
    """API để khởi động lại server."""
    audit_log.info(f"Server restart initiated by IP: {request.remote_addr}")
    # Trả về phản hồi ngay lập tức để client không bị treo
    response = jsonify(success=True, message="Server đang khởi động lại...")
    # Sau đó, khởi động lại server
    # os.execv thay thế tiến trình hiện tại bằng một tiến trình mới
    # Đảm bảo PYTHONPATH được giữ nguyên nếu cần
    python = sys.executable
    os.execv(python, [python] + sys.argv)
    return response # Dòng này sẽ không bao giờ được chạy


# app.py
# IMPORTANT: Monkey-patch for eventlet is crucial for WebSocket compatibility
import eventlet
eventlet.monkey_patch()

import os
import logging
from dotenv import load_dotenv
load_dotenv()

# Import các thư viện cần thiết
from eventlet import wsgi
from flask import Flask, jsonify, render_template, request, abort
import re
from flask_cors import CORS
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.middleware.proxy_fix import ProxyFix # Import ProxyFix
from socketio import WSGIApp

from extensions import limiter

# Import các ứng dụng con và các instance socketio của chúng
from api.analyze import analyze_endpoint
from api.admin import admin_endpoint
from api.utils import print_masked_api_keys # Import helper function

GOOGLE_API_KEYS_STR = os.environ.get('GOOGLE_API_KEYS')
if not GOOGLE_API_KEYS_STR:
    raise ValueError("Biến môi trường GOOGLE_API_KEYS là bắt buộc.")
GOOGLE_API_KEYS = [key.strip() for key in GOOGLE_API_KEYS_STR.split(',') if key.strip()]
print_masked_api_keys(GOOGLE_API_KEYS, "GOOGLE_API_KEYS") # Sử dụng hàm helper

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Ứng dụng Flask gốc ---
app = Flask(__name__)

# [SECURITY CRITICAL] Cấu hình ProxyFix để nhận diện IP thật từ Cloudflare
# x_for=1: Tin tưởng 1 lớp proxy (Cloudflare) cho header X-Forwarded-For
# x_proto=1: Tin tưởng header X-Forwarded-Proto (https/http)
# x_host=1: Tin tưởng header X-Forwarded-Host
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

CORS(app)

limiter.init_app(app)

app.secret_key = os.environ.get('SECRET_KEY', 'default-secret-key-for-dev-only')
if app.secret_key == 'default-secret-key-for-dev-only':
    logger.warning("Sử dụng SECRET_KEY mặc định. Hãy thay đổi nó trong môi trường production!")

# Đăng ký blueprint cho ứng dụng gốc

@app.before_request
def firewall():
    """Tường lửa nâng cao: Chặn truy cập file nhạy cảm và các mẫu tấn công phổ biến."""
    path = request.path.lower()
    
    # 1. Danh sách đen các file/thư mục nhạy cảm
    sensitive_patterns = [
        r'\.env', r'\.git', r'\.db', r'\.sql', r'\.py', r'\.sh',
        r'secrets/', r'venv/', r'__pycache__', r'requirements\.txt',
        r'config\.json', r'nohup\.out', r'\.log'
    ]
    
    # 2. Các mẫu tấn công phổ biến
    attack_patterns = [
        r'\/wp-', r'\/xmlrpc', r'\/phpmyadmin', r'\/pma', r'\/admin\/', # Quét CMS/Admin
        r'\.\.\/', r'\.\.\\', # Path Traversal
        r'etc\/passwd', r'proc\/self' # Linux system files
    ]
    
    # Kiểm tra
    for pattern in sensitive_patterns + attack_patterns:
        if re.search(pattern, path):
            # CHẶN NGAY LẬP TỨC
            logger.warning(f"🚨 [FIREWALL BLOCK] IP {request.remote_addr} tried to access: {path}")
            abort(403)

app.register_blueprint(analyze_endpoint, url_prefix='/api')
app.register_blueprint(admin_endpoint)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/health')
def health_check():
    return jsonify({
        'status': '🟢 Systems Nominal',
        'hp': '100/100',
        'mana': '∞',
        'latency_ms': 5,
        'service': 'cybershield-backend',
        'note': 'Tế đàn còn ổn'
    })

@app.route('/about')
def about_page():
    return render_template('about.html')

# --- Security Headers Middleware ---
@app.after_request
def add_security_headers(response):
    """Thêm các header bảo mật vào mỗi response."""
    # Ngăn trình duyệt tự ý thay đổi content-type (MIME-sniffing).
    response.headers['X-Content-Type-Options'] = 'nosniff'
    # Ngăn trang web bị nhúng vào iframe trên domain khác (chống clickjacking).
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'

    # Chính sách An toàn Nội dung (Content Security Policy) chi tiết hơn
    # Cho phép các nguồn cần thiết, giải quyết các lỗi "Refused to load/apply"
    csp_policy = (
        "default-src 'self' https://*.youtube.com https://*.ytimg.com;"
        "script-src 'self' 'unsafe-inline' https://static.cloudflareinsights.com https://cdnjs.cloudflare.com https://cdn.socket.io https://www.youtube.com https://s.ytimg.com https://cdn.tailwindcss.com;"
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com https://cdn.tailwindcss.com;"
        "img-src 'self' data: https://*.ytimg.com;"
        "font-src 'self' https://fonts.gstatic.com https://fonts.googleapis.com https://cdnjs.cloudflare.com;"
        "frame-src 'self' https://www.youtube.com;"
        "connect-src 'self' ws: wss: https://cdn.tailwindcss.com;"
    )

    response.headers['Content-Security-Policy'] = csp_policy
    return response

# --- Error Handlers ---
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {str(error)}")
    return jsonify({'error': '💥 500: Quay về phòng thủ. Tế đàn bị tấn công'}), 500


# --- Khởi chạy Server ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🚀 Starting CyberShield server on http://localhost:{port}")
    # Sử dụng server của eventlet để chạy ứng dụng Flask chính
    wsgi.server(eventlet.listen(('', port)), app)
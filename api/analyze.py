import json
import os
import gc
import re
import base64
from email.mime.text import MIMEText
import random
from flask import Blueprint, request, jsonify
import requests
import eventlet
from datetime import datetime, timezone, timedelta

# --- Import các module phân tích ---
from api.chatgpt import analyze_with_chatgpt_http
from api.gemini import analyze_with_anna_ai_http
from api.pre_filter import is_trivial_message
from api.utils import get_dynamic_config
from api.logger import log_analysis # Import Excel Logger
from extensions import limiter

# --- Blueprint ---
analyze_endpoint = Blueprint('analyze_endpoint', __name__)

# VirusTotal API Keys (hỗ trợ xoay vòng)
VIRUSTOTAL_API_KEYS_STR = os.environ.get('VIRUSTOTAL_API_KEYS')
VIRUSTOTAL_API_KEYS = [key.strip() for key in VIRUSTOTAL_API_KEYS_STR.split(',') if key.strip()] if VIRUSTOTAL_API_KEYS_STR else []

def send_email_alert(to_email, subject, body):
    """Gửi email cảnh báo (sử dụng thư viện Google chỉ khi cần)."""
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    
    config = get_dynamic_config()
    if not config.get('enable_email_alerts', True): return
    
    token_path = os.environ.get('GMAIL_TOKEN_PATH', 'secrets/token.json')
    if not os.path.exists(token_path): return

    try:
        creds = Credentials.from_authorized_user_file(token_path, ['https://www.googleapis.com/auth/gmail.send'])
        service = build('gmail', 'v1', credentials=creds)
        message = MIMEText(body, 'html')
        message['to'] = to_email
        message['subject'] = subject
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
        print("✅ [Email] Cảnh báo đã được gửi.")
    except Exception as e:
        print(f"🔴 [Email] Lỗi: {e}")

def check_urls_with_virustotal(urls: list) -> list:
    if not VIRUSTOTAL_API_KEYS: return []
    malicious_urls = []
    for url in urls:
        try:
            headers = {"x-apikey": random.choice(VIRUSTOTAL_API_KEYS)}
            vt_url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
            resp = requests.get(f"https://www.virustotal.com/api/v3/urls/{vt_url_id}", headers=headers, timeout=10)
            if resp.status_code == 200:
                stats = resp.json().get('data', {}).get('attributes', {}).get('last_analysis_stats', {})
                if stats.get('malicious', 0) > 0 or stats.get('suspicious', 0) > 0:
                    malicious_urls.append(url)
        except: pass
    return malicious_urls

# --- Cache Đơn giản ---
analysis_cache = {}
MAX_CACHE_SIZE = 100

def get_from_cache(text: str):
    return analysis_cache.get(text)

def add_to_cache(text: str, result: dict):
    if len(analysis_cache) >= MAX_CACHE_SIZE:
        # Xóa bớt cache cũ nhất (FIFO đơn giản)
        first_key = next(iter(analysis_cache))
        analysis_cache.pop(first_key)
    analysis_cache[text] = result

def perform_full_analysis(text: str, urls_from_request: list):
    # 0. Kiểm tra Cache
    cached_result = get_from_cache(text)
    if cached_result:
        print(f"🚀 [Cache] Trả về kết quả từ bộ nhớ đệm cho: {text[:20]}...")
        return cached_result

    # 1. Lọc nhanh (Local)
    if is_trivial_message(text):
        return {'is_dangerous': False, 'reason': 'Tin nhắn vô hại.', 'score': 0, 'types': ['an toàn']}

    config = get_dynamic_config()
    provider = config.get('analysis_provider', 'AUTO').upper()
    if provider == 'OFF': return {"error": "SERVICE_DISABLED", "message": "Dịch vụ đang tắt.", "status_code": 503}

    # 2. Chuẩn bị URLs
    url_pattern = re.compile(r'https?://[^\s]+', re.IGNORECASE)
    found_urls = url_pattern.findall(text)
    all_urls = list(set(urls_from_request + found_urls))
    
    # 3. Chạy SONG SONG VirusTotal và AI Analysis
    pool = eventlet.GreenPool()
    
    # Hàm AI cụ thể
    ai_func = analyze_with_chatgpt_http if provider == 'CHATGPT' else analyze_with_anna_ai_http
    
    # Spawn các tác vụ
    vt_thread = pool.spawn(check_urls_with_virustotal, all_urls) if all_urls else None
    ai_thread = pool.spawn(ai_func, text)
    
    # Lấy kết quả từ VirusTotal trước (thường nhanh hơn)
    malicious = vt_thread.wait() if vt_thread else []
    if malicious:
        result = {'is_dangerous': True, 'types': ['lừa đảo'], 'score': 5, 'reason': f"URL độc hại: {', '.join(malicious)}", 'recommend': "Không nhấn vào link."}
        eventlet.spawn_n(log_analysis, text, result)
        add_to_cache(text, result)
        return result

    # Lấy kết quả từ AI
    final_result = ai_thread.wait()
    
    # Fallback nếu AI chính lỗi (Luôn thử nếu có thể)
    if (not final_result or 'error' in final_result):
        print(f"🟡 [Analyze] Provider chính ({provider}) lỗi. Đang thử fallback...")
        fallback_func = analyze_with_chatgpt_http if ai_func == analyze_with_anna_ai_http else analyze_with_anna_ai_http
        final_result = fallback_func(text)

    # 4. Hậu xử lý (Log & Cache)
    if final_result and 'error' not in final_result:
        eventlet.spawn_n(log_analysis, text, final_result) # Ghi log Excel
        add_to_cache(text, final_result) # Lưu vào cache
        
        if final_result.get("is_dangerous"):
            eventlet.spawn_n(send_email_alert, "duongpham18210@gmail.com", f"[CyberShield] Nguy hiểm!", f"Phân tích: {json.dumps(final_result, ensure_ascii=False)}")

    gc.collect()
    return final_result

@analyze_endpoint.route('/analyze', methods=['POST'])
@limiter.limit("15/minute;3/second")
def analyze_text():
    data = request.get_json(silent=True)
    if not data or 'text' not in data: return jsonify({'error': 'Thiếu dữ liệu'}), 400
    
    text = data.get('text', '').strip()
    if not text: return jsonify({'error': 'Văn bản rỗng'}), 400
    if len(text) > 5000: return jsonify({'error': 'Văn bản quá dài'}), 413

    result = perform_full_analysis(text, data.get('urls', []))
    if result and 'error' in result:
        return jsonify({'error': result.get('message', 'Lỗi phân tích')}), result.get('status_code', 500)
    
    return jsonify({'result': result})

@analyze_endpoint.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'Bình thường', 'logger': 'Excel-based'})

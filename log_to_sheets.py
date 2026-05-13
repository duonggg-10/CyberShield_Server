import os
import sys
import json
import base64
from datetime import datetime, timezone, timedelta

# Google API imports (placed here so they are loaded in the subprocess)
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# --- Cấu hình (cần truy cập biến môi trường) ---
GMAIL_TOKEN_PATH = os.environ.get('GMAIL_TOKEN_PATH', 'secrets/token.json')
GOOGLE_SHEET_ID = os.environ.get('GOOGLE_SHEET_ID')

def get_google_credentials(scopes):
    if not os.path.exists(GMAIL_TOKEN_PATH):
        print(f"🔴 [Google API Subprocess] Lỗi: Không tìm thấy tệp token tại '{GMAIL_TOKEN_PATH}'")
        return None
    try:
        return Credentials.from_authorized_user_file(GMAIL_TOKEN_PATH, scopes)
    except Exception as e:
        print(f"🔴 [Google API Subprocess] Lỗi khi tải credentials: {e}")
        return None

def save_to_history_sheet(text: str, result_json: str):
    if not GOOGLE_SHEET_ID:
        print("🟡 [Google Sheet Subprocess] GOOGLE_SHEET_ID chưa được thiết lập. Bỏ qua lưu.")
        return

    try:
        # Giải mã JSON từ chuỗi truyền vào
        result = json.loads(result_json)
    except json.JSONDecodeError as e:
        print(f"🔴 [Google Sheet Subprocess] Lỗi giải mã JSON từ đối số: {e}")
        return

    creds = get_google_credentials(['https://www.googleapis.com/auth/spreadsheets'])
    if not creds: return

    try:
        service = build('sheets', 'v4', credentials=creds)
        vn_timezone = timezone(timedelta(hours=7))
        timestamp = datetime.now(vn_timezone).strftime('%Y-%m-%d %H:%M:%S')
        
        row_data = [
            timestamp, text, result.get('is_dangerous', False),
            str(result.get('types', 'N/A')),
            result.get('reason', 'N/A'),
            result.get('score', 0), result.get('recommend', 'N/A')
        ]
        body = {'values': [row_data]}
        service.spreadsheets().values().append(
            spreadsheetId=GOOGLE_SHEET_ID, range='History!A2',
            valueInputOption='USER_ENTERED', insertDataOption='INSERT_ROWS', body=body
        ).execute()
        print("✅ [Google Sheet Subprocess] Đã lưu thành công.")
    except Exception as e:
        print(f"🔴 [Google Sheet Subprocess] Lỗi khi đang lưu: {e}")

if __name__ == '__main__':
    # Đọc đối số từ dòng lệnh
    if len(sys.argv) > 2:
        try:
            text = base64.b64decode(sys.argv[1]).decode('utf-8')
            result_json = base64.b64decode(sys.argv[2]).decode('utf-8')
            save_to_history_sheet(text, result_json)
        except Exception as e:
            print(f"🔴 [Google Sheet Subprocess] Lỗi khi đọc đối số hoặc thực thi: {e}")
    else:
        print("🔴 [Google Sheet Subprocess] Không đủ đối số. Cần 'text' và 'result_json'.")

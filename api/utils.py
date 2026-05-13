# api/utils.py
import json

def get_dynamic_config():
    """Đọc file config.json để lấy cấu hình động."""
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Fallback nếu file không tồn tại hoặc bị lỗi
        return {
            "analysis_provider": "AUTO",
            "enable_email_alerts": True,
            "pre_filter_model_id": "openai/gpt-3.5-turbo"
        }

def print_masked_api_keys(key_list: list, key_name: str):
    """
    In danh sách các API keys đã được che một phần để bảo mật và định dạng đẹp hơn.
    """
    if not key_list:
        print(f"🟡 [CONFIG] Không có {key_name} nào được thiết lập.")
        return

    masked_keys = [f"...{key[-4:]}" for key in key_list]
    print(f"🟢 [CONFIG] {key_name} đã tải ({len(key_list)} key): {', '.join(masked_keys)}")
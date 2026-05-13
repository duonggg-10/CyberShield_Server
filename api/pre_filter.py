# api/pre_filter.py
import re

def is_trivial_message(text: str) -> bool:
    """
    Kiểm tra tin nhắn có phải là tin nhắn rác, chào hỏi hoặc quá ngắn 
    bằng logic nội bộ (Local) để tiết kiệm thời gian và Quota AI.
    """
    text = text.strip().lower()
    
    # 1. Kiểm tra độ dài (Quá ngắn thường không gây nguy hiểm)
    if len(text) < 2:
        return True
        
    # 2. Danh sách các từ khóa chào hỏi, cảm ơn, xã giao phổ biến (Tiếng Việt & Anh)
    trivial_keywords = {
        "chào", "hi", "hello", "xin chào", "chào bạn", "alo", "ô kê", "ok", "oke",
        "tks", "thanks", "cảm ơn", "cám ơn", "thank you", "đã rõ", "vâng", "dạ",
        "bye", "tạm biệt", "g9", "ngủ ngon", "haha", "hihi", "huhu", "vcl", "vl",
        "được", "ko", "không", "yes", "no", "rep", "đâu", "nào"
    }
    
    # Kiểm tra nếu tin nhắn chỉ chứa 1-2 từ và nằm trong danh sách trivial
    words = text.split()
    if len(words) <= 2 and any(word in trivial_keywords for word in words):
        return True
        
    # 3. Sử dụng Regex để lọc các mẫu câu xã giao cực ngắn
    # Ví dụ: "chào shop", "ad ơi", "bạn ơi"
    social_patterns = [
        r'^(chào|hi|hello)\s+(admin|ad|shop|bạn|mọi người)$',
        r'^(bạn|ad|admin|shop)\s+ơi$',
        r'^[\?\.\!]+$' # Chỉ chứa dấu câu
    ]
    
    for pattern in social_patterns:
        if re.match(pattern, text):
            return True

    return False

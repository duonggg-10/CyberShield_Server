# extensions.py
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100000000 per hour", "100000000000000 per minute", "10000000000000000000 per day"],
    storage_uri="memory://",
    strategy="fixed-window"
)

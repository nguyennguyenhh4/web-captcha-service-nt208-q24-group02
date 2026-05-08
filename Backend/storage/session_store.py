import time
import threading
from typing import Optional


class SessionStore:
    """
    Lưu session CAPTCHA trong bộ nhớ (dict).
    Thread-safe với Lock, tự dọn session hết hạn theo định kỳ.

    Nếu sau này cần scale ngang (nhiều worker), thay bằng RedisSessionStore
    (cùng interface) mà không cần sửa code ở tầng routes/services.
    """

    def __init__(self, cleanup_interval: int = 60):
        self._store: dict = {}
        self._lock  = threading.Lock()

        # Tự dọn session hết hạn mỗi `cleanup_interval` giây
        self._start_cleanup_thread(cleanup_interval)

    # ── Ghi ─────────────────────────────────────────────────────────
    def save(self, token: str, data: dict, ttl: int) -> None:
        """Lưu session với thời gian sống ttl giây."""
        with self._lock:
            self._store[token] = {
                "data":       data,
                "expires_at": time.time() + ttl,
            }

    # ── Đọc ─────────────────────────────────────────────────────────
    def get(self, token: str) -> Optional[dict]:
        """
        Lấy dữ liệu session.
        Trả về None nếu token không tồn tại hoặc đã hết hạn.
        """
        if not token:
            return None

        with self._lock:
            entry = self._store.get(token)

        if not entry:
            return None

        if time.time() > entry["expires_at"]:
            self.delete(token)
            return None

        return entry["data"]

    # ── Xóa ─────────────────────────────────────────────────────────
    def delete(self, token: str) -> None:
        """Xóa session (dùng sau khi verify xong — one-time use)."""
        with self._lock:
            self._store.pop(token, None)

    # ── Thống kê (debug) ─────────────────────────────────────────────
    def count(self) -> int:
        with self._lock:
            return len(self._store)

    # ── Dọn dẹp nền ─────────────────────────────────────────────────
    def _cleanup(self) -> None:
        """Xóa tất cả session đã hết hạn."""
        now = time.time()
        with self._lock:
            expired = [t for t, v in self._store.items() if now > v["expires_at"]]
            for t in expired:
                del self._store[t]

    def _start_cleanup_thread(self, interval: int) -> None:
        def loop():
            while True:
                time.sleep(interval)
                self._cleanup()

        thread = threading.Thread(target=loop, daemon=True)
        thread.start()


# ── Singleton dùng chung toàn app ────────────────────────────────────
session_store = SessionStore(cleanup_interval=60)

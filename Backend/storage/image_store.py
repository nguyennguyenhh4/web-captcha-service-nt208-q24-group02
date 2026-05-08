import os
import random
from typing import List


class ImageStore:
    """
    Quản lý danh sách ảnh puzzle trong thư mục static/images/.

    Hỗ trợ: .jpg, .jpeg, .png, .webp
    Nếu thư mục trống, trả về tên ảnh placeholder để tránh crash.
    """

    SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
    PLACEHOLDER    = "placeholder.jpg"

    def __init__(self, images_dir: str = "static/images"):
        self._dir   = images_dir
        self._cache: List[str] = []
        self._reload()

    def _reload(self) -> None:
        """Quét lại thư mục ảnh và cập nhật cache."""
        if not os.path.isdir(self._dir):
            self._cache = []
            return

        self._cache = [
            f for f in os.listdir(self._dir)
            if os.path.splitext(f)[1].lower() in self.SUPPORTED_EXTS
        ]

    def random_image(self) -> str:
        """
        Trả về tên file ảnh ngẫu nhiên.
        Nếu không có ảnh nào, trả về PLACEHOLDER.
        """
        if not self._cache:
            self._reload()

        if not self._cache:
            return self.PLACEHOLDER

        return random.choice(self._cache)

    def list_images(self) -> List[str]:
        """Trả về danh sách toàn bộ ảnh hiện có."""
        self._reload()
        return list(self._cache)

    def exists(self, filename: str) -> bool:
        """Kiểm tra file có tồn tại trong thư mục không."""
        path = os.path.join(self._dir, filename)
        return os.path.isfile(path)


# ── Singleton dùng chung toàn app ────────────────────────────────────
image_store = ImageStore(images_dir="static/images")

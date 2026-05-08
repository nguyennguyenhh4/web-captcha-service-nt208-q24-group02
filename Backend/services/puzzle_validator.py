import random
from typing import Tuple


class PuzzleValidator:
    """
    Sinh tọa độ đích (target) cho mảnh ghép và kiểm tra xem
    người dùng đã đặt mảnh vào đúng vị trí chưa.
    """

    @staticmethod
    def generate_target(canvas_width: int, piece_size: int) -> Tuple[int, int]:
        """
        Sinh ngẫu nhiên target_x sao cho mảnh ghép không nằm sát biên.
        target_y cố định ở giữa (frontend chỉ trượt ngang).

        Returns:
            (target_x, target_y) tính bằng pixel.
        """
        margin   = piece_size + 20          # khoảng cách tối thiểu từ biên
        max_x    = canvas_width - piece_size - margin
        target_x = random.randint(margin, max_x)
        target_y = 0    # frontend chỉ dùng target_x để kiểm tra snap

        return target_x, target_y

    @staticmethod
    def validate(
        user_x: float,
        target_x: int,
        threshold: int,
    ) -> Tuple[bool, str]:
        """
        So sánh vị trí người dùng thả mảnh ghép với tọa độ đích.

        Args:
            user_x:    Tọa độ X người dùng thả mảnh (float từ frontend).
            target_x:  Tọa độ X đích được sinh lúc /init.
            threshold: Sai số cho phép tính bằng pixel (mặc định 10px).

        Returns:
            (passed: bool, reason: str)
        """
        if user_x is None:
            return False, "Thiếu vị trí mảnh ghép (user_x)"

        try:
            user_x = float(user_x)
        except (TypeError, ValueError):
            return False, "Giá trị user_x không hợp lệ"

        diff = abs(user_x - target_x)

        if diff <= threshold:
            return True, f"Mảnh ghép khớp (sai số {diff:.1f}px)"

        return False, f"Mảnh ghép chưa khớp (sai số {diff:.1f}px, cho phép {threshold}px)"

import secrets


class SessionService:
    """
    Tạo token ngẫu nhiên, an toàn cho mỗi phiên CAPTCHA.
    Token là chuỗi hex 32 bytes (64 ký tự), đủ entropy để chống đoán.
    """

    TOKEN_BYTES = 32

    @staticmethod
    def create_token() -> str:
        """Sinh một token hex ngẫu nhiên."""
        return secrets.token_hex(SessionService.TOKEN_BYTES)

    @staticmethod
    def is_valid_format(token: str) -> bool:
        """Kiểm tra sơ bộ định dạng token (64 ký tự hex)."""
        if not isinstance(token, str):
            return False
        if len(token) != SessionService.TOKEN_BYTES * 2:
            return False
        try:
            int(token, 16)
            return True
        except ValueError:
            return False

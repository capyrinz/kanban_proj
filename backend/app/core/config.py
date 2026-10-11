import os
import secrets
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]


def load_secret_key() -> str:
    key = os.getenv("SECRET_KEY", "").strip()
    return key or secrets.token_urlsafe(32)


class Settings:
    def __init__(self) -> None:
        self.secret_key: str = load_secret_key()
        self.jwt_algorithm: str = "HS256"
        self.access_token_ttl_hours: int = int(os.getenv("ACCESS_TOKEN_TTL_HOURS", "12"))
        default_url = f"sqlite+aiosqlite:///{BACKEND_DIR / 'kanban.db'}"
        self.database_url: str = os.getenv("DATABASE_URL", default_url)
        self.bcrypt_rounds: int = int(os.getenv("BCRYPT_ROUNDS", "12"))
        self.admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
        self.admin_password: str = os.getenv("ADMIN_PASSWORD", "admin")


settings = Settings()

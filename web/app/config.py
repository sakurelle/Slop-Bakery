from dataclasses import dataclass
from functools import lru_cache
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = "Bakery DB Security Web"
    secret_key: str = os.getenv("APP_SECRET_KEY", "change_me_session_key")
    session_cookie: str = "bakery_session"
    db_host: str = os.getenv("DB_HOST", "db")
    db_port: int = int(os.getenv("DB_PORT", os.getenv("POSTGRES_PORT", "5432")))
    db_name: str = os.getenv("DB_NAME", os.getenv("POSTGRES_DB", "bakery_security_db"))
    db_user: str = os.getenv("DB_USER", os.getenv("POSTGRES_USER", "bakery_admin_user"))
    db_password: str = os.getenv("DB_PASSWORD", os.getenv("POSTGRES_PASSWORD", "change_me"))
    web_port: int = int(os.getenv("WEB_PORT", "8000"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

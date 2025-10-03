import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass
class Settings:
    api_id: int
    api_hash: str
    tz: str
    db_url: str
    host: str
    port: int
    max_concurrency: int
    jwt_secret_key: str
    jwt_algorithm: str
    jwt_expire_minutes: int
    admin_username: str
    admin_password: str


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is not None:
        return _settings
    load_dotenv()
    api_id = int(os.getenv("API_ID", "0"))
    api_hash = os.getenv("API_HASH", "")
    tz = os.getenv("TZ", "UTC")
    db_url = os.getenv("DB_URL", "sqlite:///./data.sqlite3")
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    max_concurrency = int(os.getenv("MAX_CONCURRENCY", "2"))
    jwt_secret_key = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-this-in-production")
    jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expire_minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))  # 24 hours
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "9999")
    _settings = Settings(
        api_id=api_id,
        api_hash=api_hash,
        tz=tz,
        db_url=db_url,
        host=host,
        port=port,
        max_concurrency=max_concurrency,
        jwt_secret_key=jwt_secret_key,
        jwt_algorithm=jwt_algorithm,
        jwt_expire_minutes=jwt_expire_minutes,
        admin_username=admin_username,
        admin_password=admin_password,
    )
    return _settings
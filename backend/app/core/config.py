from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment & Info
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "Workflow Automation & Document Intelligence Engine"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # CORS
    BACKEND_CORS_ORIGINS: list[str | AnyHttpUrl] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:5173",
        # NOTE: Do NOT add "*" or "null" here in production — they bypass CORS security.
        # For production, restrict to your actual frontend domain(s) only.
    ]

    # Security
    SECRET_KEY: str = "supersecret_jwt_key_change_me_in_production_min32chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "doc_intel_db"
    DATABASE_URL: str = "sqlite+aiosqlite:///./doc_intel.db"
    SYNC_DATABASE_URL: str = "sqlite:///./doc_intel.db"

    # Redis & Celery
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Storage
    STORAGE_PROVIDER: str = "local"
    STORAGE_LOCAL_DIR: str = "./storage_data"
    MAX_FILE_SIZE_MB: int = 25
    ALLOWED_EXTENSIONS: list[str] = ["pdf", "png", "jpg", "jpeg", "tiff"]

    # Initial Admin Seed
    FIRST_SUPERUSER_EMAIL: str = "admin@example.com"
    FIRST_SUPERUSER_PASSWORD: str = "AdminSecurePassword123!"
    FIRST_SUPERUSER_NAME: str = "Super Administrator"

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


settings = Settings()

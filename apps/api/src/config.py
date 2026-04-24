from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Postgres
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "retail_orders"
    postgres_user: str = "retail"
    postgres_password: str = "retail_secret"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin"
    minio_bucket: str = "orders"
    minio_secure: bool = False

    # Phoenix — HTTP OTLP endpoint is on the same port as the UI (6006),
    # not the OpenTelemetry-standard 4318.
    phoenix_endpoint: str = "http://localhost:6006"

    # n8n
    n8n_webhook_url: str = "http://localhost:5678"

    # JWT — secret must be >= 32 bytes for HS256 (RFC 7518 §3.2).
    # Override in production via env var.
    jwt_secret: str = "change-me-in-production-please-use-32-byte-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Anthropic
    anthropic_api_key: str = ""

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # General
    timezone: str = "Europe/Madrid"

    model_config = SettingsConfigDict(
        # Load root .env first, then apps/api/.env (later files override earlier).
        env_file=("../../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def samples_orders_dir(self) -> Path:
        # config.py → parents[3] = repo root → samples/orders/
        return Path(__file__).resolve().parents[3] / "samples" / "orders"


settings = Settings()

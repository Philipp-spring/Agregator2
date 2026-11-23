from pydantic import AliasChoices, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    postgres_username: str = "postgres"
    postgres_password: str = "postgres"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_database_name: str = "aggregator_db"
    
    postgres_connection_string: str | None = None

    api_key: str = "YOUR_API_KEY"
    api_base_url: str = (
        "http://student-system-events-provider-web.student-system-events-provider.svc:8000"
    )
    capashino_url: str = "http://student-system-capashino-web.student-system-capashino.svc:8000"

    outbox_poll_interval: float = 5.0
    outbox_batch_size: int = 10
    outbox_max_retries: int = 5
    idempotency_ttl_seconds: int = 86400

    sentry_dsn: str | None = Field(default=None, validation_alias=AliasChoices("SENTRY_DSN", "GLITCHTIP_DSN"))

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @computed_field
    @property
    def database_url(self) -> str:
        if self.postgres_connection_string:
            conn_str = self.postgres_connection_string
            if conn_str.startswith("postgres://"):
                conn_str = conn_str.replace("postgres://", "postgresql+asyncpg://", 1)
            return conn_str
        return (
            f"postgresql+asyncpg://{self.postgres_username}:"
            f"{self.postgres_password}@{self.postgres_host}:"
            f"{self.postgres_port}/{self.postgres_database_name}"
        )




settings = Settings()

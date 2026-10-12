from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# --- Common ---
class CommonSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


# --- Postgres ---
class PostgresSettings(CommonSettings):
    postgres_server: str = Field(
        validation_alias="POSTGRES_SERVER",
    )

    postgres_port: int = Field(
        validation_alias="POSTGRES_PORT",
    )

    postgres_user: str = Field(
        validation_alias="POSTGRES_USER",
    )

    postgres_password: SecretStr = Field(
        validation_alias="POSTGRES_PASSWORD",
    )

    postgres_db: str = Field(
        validation_alias="POSTGRES_DB",
    )

    @property
    def postgres_async_url(self) -> str:
        return (
            f"postgresql+asyncpg://"
            f"{self.postgres_user}:"
            f"{self.postgres_password.get_secret_value()}"
            f"@{self.postgres_server}:"
            f"{self.postgres_port}/"
            f"{self.postgres_db}"
        )


# --- Redis ---
class RedisSettings(CommonSettings):
    redis_host: str = Field(
        validation_alias="REDIS_HOST",
    )

    redis_port: int = Field(
        validation_alias="REDIS_PORT",
    )

    redis_db: int = Field(
        validation_alias="REDIS_DB",
    )

    redis_password: Optional[SecretStr] = Field(
        default=None,
        validation_alias="REDIS_PASSWORD",
    )

    redis_tls: bool = Field(
        validation_alias="REDIS_TLS",
    )

    @property
    def redis_url(self) -> str:
        scheme = "rediss" if self.redis_tls else "redis"

        password = (
            f":{self.redis_password.get_secret_value()}@" if self.redis_password else ""
        )

        return (
            f"{scheme}://"
            f"{password}"
            f"{self.redis_host}:"
            f"{self.redis_port}/"
            f"{self.redis_db}"
        )


# --- Kafka ---
class KafkaSettings(CommonSettings):
    bootstrap_servers: str = Field(
        validation_alias="KAFKA_BOOTSTRAP_SERVERS",
    )

    client_id: str = Field(
        default="sonclarus-backend",
        validation_alias="KAFKA_CLIENT_ID",
    )

    security_protocol: Literal["PLAINTEXT", "SASL_SSL"] = Field(
        default="PLAINTEXT",
        validation_alias="KAFKA_SECURITY_PROTOCOL",
    )

    sasl_mechanism: Optional[str] = Field(
        default=None,
        validation_alias="KAFKA_SASL_MECHANISM",
    )

    sasl_username: Optional[str] = Field(
        default=None,
        validation_alias="KAFKA_SASL_USERNAME",
    )

    sasl_password: Optional[SecretStr] = Field(
        default=None,
        validation_alias="KAFKA_SASL_PASSWORD",
    )

    request_timeout_ms: int = Field(
        default=30000,
        validation_alias="KAFKA_REQUEST_TIMEOUT_MS",
    )

    send_timeout_seconds: float = Field(
        default=15,
        validation_alias="KAFKA_SEND_TIMEOUT_SECONDS",
    )

    start_max_attempts: int = Field(
        default=5,
        validation_alias="KAFKA_START_MAX_ATTEMPTS",
    )

    denoise_topic: str = Field(
        validation_alias="KAFKA_DENOISE_TOPIC",
    )

    separate_topic: str = Field(
        validation_alias="KAFKA_SEPARATE_TOPIC",
    )

    transcribe_topic: str = Field(
        validation_alias="KAFKA_TRANSCRIBE_TOPIC",
    )

    summarize_topic: str = Field(
        validation_alias="KAFKA_SUMMARIZE_TOPIC",
    )

    ml_result_topic: str = Field(
        default="ml-results",
        validation_alias="KAFKA_ML_RESULT_TOPIC",
    )

    ml_result_group_id: str = Field(
        default="sonclarus-backend-ml-results",
        validation_alias="KAFKA_ML_RESULT_GROUP_ID",
    )

    @model_validator(mode="after")
    def _check_sasl_credentials(self) -> "KafkaSettings":
        if self.security_protocol == "SASL_SSL" and not (
            self.sasl_mechanism and self.sasl_username and self.sasl_password
        ):
            raise ValueError(
                "SASL_SSL requires KAFKA_SASL_MECHANISM, "
                "KAFKA_SASL_USERNAME and KAFKA_SASL_PASSWORD"
            )
        return self


# --- App settings ---
class AppSettings(CommonSettings):
    project_name: str = Field(
        default="SonClarus",
        validation_alias="PROJECT_NAME",
    )

    version: str = Field(
        validation_alias="PROJECT_VERSION",
    )

    docs_endpoint: str = Field(
        validation_alias="DOCS_ENDPOINT",
    )

    upload_url_ttl_seconds: int = Field(
        gt=0,
        validation_alias="UPLOAD_URL_TTL_SECONDS",
    )
    download_url_ttl_seconds: int = Field(
        gt=0,
        validation_alias="DOWNLOAD_URL_TTL_SECONDS",
    )


# --- Jwt Auth ---
class JwtSettings(CommonSettings):
    secret_key: str = Field(validation_alias="JWT_SECRET_KEY")
    algorithm: str = Field(
        default="HS256",
        validation_alias="ALGORITHM",
    )
    access_token_expire_minutes: int = Field(
        default=30,
        validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )
    refresh_token_expire_days: int = Field(
        default=30,
        validation_alias="REFRESH_TOKEN_EXPIRE_DAYS",
    )
    refresh_grace_period_minutes: int = Field(
        default=5,
        validation_alias="REFRESH_GRACE_PERIOD_MINUTES",
    )


# --- CORS ---
class CORSSettings(CommonSettings):
    allowed_origins: list[str] = Field(
        validation_alias="ALLOWED_ORIGINS",
    )

    allowed_methods: list[str] = Field(
        validation_alias="ALLOWED_METHODS",
    )

    allowed_headers: list[str] = Field(
        validation_alias="ALLOWED_HEADERS",
    )

    allow_credentials: bool = Field(
        validation_alias="ALLOW_CREDENTIALS",
    )

    max_age: int = Field(
        validation_alias="CORS_MAX_AGE",
    )


# --- Aws ---
class AWSSettings(CommonSettings):
    access_key_id: str = Field(
        validation_alias="AWS_ACCESS_KEY_ID",
    )

    secret_access_key: SecretStr = Field(
        validation_alias="AWS_SECRET_ACCESS_KEY",
    )

    region: str = Field(
        validation_alias="AWS_REGION",
    )

    bucket_name: str = Field(
        validation_alias="AWS_BUCKET_NAME",
    )
    endpoint_url: str = Field(
        validation_alias="AWS_ENDPOINT_URL",
    )
    public_endpoint_url: Optional[str] = Field(
        default=None,
        validation_alias="AWS_PUBLIC_ENDPOINT_URL",
    )


# --- Gemini / LLM ---
class GeminiSettings(CommonSettings):
    api_key: SecretStr = Field(
        validation_alias="GEMINI_API_KEY",
    )


# --- File Upload ---
class FileSettings(CommonSettings):
    max_file_size: int = Field(
        default=50 * 1024 * 1024,
        validation_alias="MAX_FILE_SIZE",
    )


# --- Main Settings ---
class Settings(CommonSettings):
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    app: AppSettings = Field(default_factory=AppSettings)
    jwt: JwtSettings = Field(default_factory=JwtSettings)
    cors: CORSSettings = Field(default_factory=CORSSettings)
    aws: AWSSettings = Field(default_factory=AWSSettings)
    gemini: GeminiSettings = Field(default_factory=GeminiSettings)
    file: FileSettings = Field(default_factory=FileSettings)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

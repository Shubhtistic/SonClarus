from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class CommonSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_parse_none_str="",
    )


class KafkaSettings(CommonSettings):
    bootstrap_servers: str = Field(validation_alias="KAFKA_BOOTSTRAP_SERVERS")
    security_protocol: Literal["PLAINTEXT", "SASL_SSL"] = Field(
        default="PLAINTEXT", validation_alias="KAFKA_SECURITY_PROTOCOL"
    )
    sasl_mechanism: str | None = Field(
        default=None, validation_alias="KAFKA_SASL_MECHANISM"
    )
    sasl_username: str | None = Field(
        default=None, validation_alias="KAFKA_SASL_USERNAME"
    )
    sasl_password: SecretStr | None = Field(
        default=None, validation_alias="KAFKA_SASL_PASSWORD"
    )
    client_id: str = Field(
        default="sonclarus-backend", validation_alias="KAFKA_CLIENT_ID"
    )
    group_id_prefix: str = Field(
        default="sonclarus-ml", validation_alias="KAFKA_GROUP_ID_PREFIX"
    )
    denoise_topic: str = Field(validation_alias="KAFKA_DENOISE_TOPIC")
    separate_topic: str = Field(validation_alias="KAFKA_SEPARATE_TOPIC")
    transcribe_topic: str = Field(validation_alias="KAFKA_TRANSCRIBE_TOPIC")
    summarize_topic: str = Field(validation_alias="KAFKA_SUMMARIZE_TOPIC")
    result_topic: str = Field(validation_alias="KAFKA_ML_RESULT_TOPIC")
    start_max_attempts: int = Field(
        default=5, validation_alias="KAFKA_START_MAX_ATTEMPTS"
    )
    request_timeout_ms: int = Field(
        default=30_000, validation_alias="KAFKA_REQUEST_TIMEOUT_MS"
    )
    send_timeout_seconds: float = Field(
        default=15, validation_alias="KAFKA_SEND_TIMEOUT_SECONDS"
    )
    max_poll_interval_ms: int = Field(
        default=3_600_000, validation_alias="KAFKA_MAX_POLL_INTERVAL_MS"
    )

    @model_validator(mode="after")
    def validate_sasl_credentials(self) -> "KafkaSettings":
        if self.security_protocol == "SASL_SSL" and not (
            self.sasl_mechanism and self.sasl_username and self.sasl_password
        ):
            raise ValueError(
                "SASL_SSL requires KAFKA_SASL_MECHANISM, KAFKA_SASL_USERNAME, "
                "and KAFKA_SASL_PASSWORD"
            )
        return self


class AWSSettings(CommonSettings):
    access_key_id: str = Field(validation_alias="AWS_ACCESS_KEY_ID")
    secret_access_key: SecretStr = Field(validation_alias="AWS_SECRET_ACCESS_KEY")
    region: str = Field(validation_alias="AWS_REGION")
    bucket_name: str = Field(validation_alias="AWS_BUCKET_NAME")
    endpoint_url: str | None = Field(default=None, validation_alias="AWS_ENDPOINT_URL")


class GeminiSettings(CommonSettings):
    api_key: SecretStr = Field(validation_alias="GEMINI_API_KEY")
    model_name: str = Field(
        default="gemini-3.8-flash", validation_alias="GEMINI_MODEL"
    )
    timeout_seconds: int = Field(default=120, validation_alias="GEMINI_TIMEOUT_S")


class DenoiseSettings(CommonSettings):
    model_name: str = Field(default="DeepFilterNet3", validation_alias="DF_MODEL_NAME")
    post_filter: bool = Field(default=True, validation_alias="DF_POST_FILTER")
    atten_lim_db: float | None = Field(default=None, validation_alias="DF_ATTEN_LIM_DB")
    model_dir: str | None = Field(default=None, validation_alias="DF_MODEL_DIR")
    log_level: str = Field(default="WARNING", validation_alias="DF_LOG_LEVEL")


class SeparateSettings(CommonSettings):
    source: str = Field(
        default="speechbrain/sepformer-wsj02mix", validation_alias="SEPFORMER_SOURCE"
    )
    savedir: str = Field(
        default="pretrained_models/sepformer-wsj02mix",
        validation_alias="SEPFORMER_SAVEDIR",
    )
    sample_rate: int = Field(default=8000, validation_alias="SEPFORMER_SAMPLE_RATE")
    chunk_samples: int = Field(
        default=120_000, validation_alias="SEPARATOR_CHUNK_SAMPLES"
    )
    device: str | None = Field(default=None, validation_alias="SEPARATOR_DEVICE")


class TranscribeSettings(CommonSettings):
    model_size: str = Field(default="base", validation_alias="WHISPER_MODEL_SIZE")
    compute_type: str = Field(
        default="int8", validation_alias="WHISPER_COMPUTE_TYPE"
    )
    beam_size: int = Field(default=5, validation_alias="WHISPER_BEAM_SIZE")
    vad_filter: bool = Field(default=True, validation_alias="WHISPER_VAD_FILTER")
    vad_min_silence_duration_ms: int = Field(
        default=500, validation_alias="WHISPER_VAD_MIN_SILENCE_MS"
    )
    device: str | None = Field(default=None, validation_alias="WHISPER_DEVICE")


class WorkerSettings(CommonSettings):
    work_dir: str = Field(default="/tmp/sonclarus-ml", validation_alias="ML_WORK_DIR")
    torch_num_threads: int = Field(default=2, validation_alias="ML_TORCH_NUM_THREADS")


class Settings(CommonSettings):
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    aws: AWSSettings = Field(default_factory=AWSSettings)
    gemini: GeminiSettings = Field(default_factory=GeminiSettings)
    denoise: DenoiseSettings = Field(default_factory=DenoiseSettings)
    separate: SeparateSettings = Field(default_factory=SeparateSettings)
    transcribe: TranscribeSettings = Field(default_factory=TranscribeSettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)


@lru_cache
def get_settings() -> Settings:
    return Settings()

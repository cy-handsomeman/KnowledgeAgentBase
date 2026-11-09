from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    database_url: str
    upload_dir: str
    chroma_dir: str
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    embedding_model: str
    jwt_secret_key: str
    jwt_expire_minutes: int = 120

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

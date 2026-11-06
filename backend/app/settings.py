"""Application settings, read from the environment or a local .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DIDI_", env_file=PROJECT_ROOT / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg://didi:didi_dev@localhost:5433/didi"
    corpus_path: Path = PROJECT_ROOT / "data" / "processed" / "didi_corpus.db"
    build_version: str = "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()

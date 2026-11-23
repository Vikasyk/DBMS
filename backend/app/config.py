from dataclasses import dataclass
from os import getenv
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    db_app_url: str
    db_nl_url: str


def load_settings() -> Settings:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    app_url = getenv("DB_APP_URL")
    nl_url = getenv("DB_NL_URL")
    if not app_url or not nl_url:
        raise RuntimeError("Set DB_APP_URL and DB_NL_URL in the environment or .env")
    return Settings(app_url, nl_url)

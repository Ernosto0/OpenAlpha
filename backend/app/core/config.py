from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


load_dotenv()


def _csv_env(name: str, default: str) -> list[str]:
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "OpenAlpha API"))
    app_version: str = field(default_factory=lambda: os.getenv("APP_VERSION", "0.1.0"))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "local"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./openalpha.db")
    )
    cors_origins: list[str] = field(
        default_factory=lambda: _csv_env(
            "CORS_ORIGINS",
            ",".join(
                [
                    "http://localhost:3000",
                    "http://localhost:5173",
                    "http://localhost:5174",
                    "http://127.0.0.1:3000",
                    "http://127.0.0.1:5173",
                    "http://127.0.0.1:5174",
                ]
            ),
        )
    )


settings = Settings()

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_SECRETS_FILE = "secrets.json"
SETTINGS_KEY = "app_settings"


def openalpha_home() -> Path:
    configured_home = os.getenv("OPENALPHA_HOME")
    if configured_home:
        return Path(configured_home).expanduser()
    return Path.home() / ".openalpha"


def load_local_secrets(secrets_path: Path | None = None) -> dict[str, Any]:
    path = secrets_path or openalpha_home() / DEFAULT_SECRETS_FILE
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in local secrets file: {path}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Local secrets file must contain a JSON object: {path}")
    return data


def get_provider_api_key(
    provider: str,
    *,
    secrets_path: Path | None = None,
    env_var: str | None = None,
) -> str | None:
    provider_key = provider.strip().lower()
    secrets = load_local_secrets(secrets_path)

    provider_config = secrets.get(provider_key)
    if isinstance(provider_config, dict):
        for key_name in ("api_key", "key", f"{provider_key}_api_key"):
            value = provider_config.get(key_name)
            if isinstance(value, str) and value.strip():
                return value.strip()

    for key_name in (
        f"{provider_key}_api_key",
        f"{provider_key.upper()}_API_KEY",
        "api_key",
    ):
        value = secrets.get(key_name)
        if isinstance(value, str) and value.strip():
            return value.strip()

    if secrets_path is None:
        stored_value = _get_provider_api_key_from_settings(provider_key)
        if stored_value:
            return stored_value

    if env_var:
        value = os.getenv(env_var)
        if value and value.strip():
            return value.strip()

    return None


def _get_provider_api_key_from_settings(provider_key: str) -> str | None:
    try:
        from sqlmodel import Session

        from backend.app.db.models import Setting
        from backend.app.db.session import engine
    except Exception:
        return None

    try:
        with Session(engine) as session:
            row = session.get(Setting, SETTINGS_KEY)
    except Exception:
        return None

    if row is None or not isinstance(row.value_json, dict):
        return None

    provider_value = row.value_json.get(provider_key)
    if isinstance(provider_value, dict):
        for key_name in ("api_key", "key", f"{provider_key}_api_key"):
            value = provider_value.get(key_name)
            if isinstance(value, str) and value.strip():
                return value.strip()

    direct_value = row.value_json.get(f"{provider_key}_api_key")
    if isinstance(direct_value, str) and direct_value.strip():
        return direct_value.strip()

    return None

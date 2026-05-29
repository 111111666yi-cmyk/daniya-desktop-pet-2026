from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from dotenv import dotenv_values

from .chat_client import mask_key
from .config_manager import DEFAULT_APP_CONFIG, ConfigManager, deep_merge
from .utils import ensure_dir, runtime_root


DEFAULT_API_CONFIG: dict[str, Any] = {
    "provider": "deepseek",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-chat",
    "local_mode": False,
    "timeout_seconds": 20,
    "api_key_env": "DEEPSEEK_API_KEY",
}


class SettingsManager:
    def __init__(self, config_manager: ConfigManager | None = None, root: Path | None = None) -> None:
        self.root = root or runtime_root()
        self.config_manager = config_manager or ConfigManager()
        self.config_dir = ensure_dir(self.root / "config")
        self.env_path = self.root / ".env"
        self.api_config_path = self.config_dir / "api_config.json"
        self.ensure_configs()

    def ensure_configs(self) -> None:
        self.config_manager.load_app_config()
        if not self.api_config_path.exists():
            self.save_api_config(DEFAULT_API_CONFIG)
            return
        loaded = self._load_json(self.api_config_path, DEFAULT_API_CONFIG)
        self.save_api_config(loaded)

    def load_app_config(self) -> dict[str, Any]:
        return self.config_manager.load_app_config()

    def save_app_config(self, config: dict[str, Any]) -> None:
        self.config_manager.save_app_config(config)

    def load_api_config(self) -> dict[str, Any]:
        loaded = self._load_json(self.api_config_path, DEFAULT_API_CONFIG)
        if not isinstance(loaded, dict):
            loaded = {}
        config = deep_merge(DEFAULT_API_CONFIG, loaded)
        config["api_key_masked"] = mask_key(self.current_api_key())
        return config

    def save_api_config(self, config: dict[str, Any]) -> None:
        safe = deep_merge(DEFAULT_API_CONFIG, config if isinstance(config, dict) else {})
        safe.pop("api_key", None)
        safe.pop("api_key_masked", None)
        self._save_json_atomic(self.api_config_path, safe)

    def save_api_settings(
        self,
        provider: str,
        base_url: str,
        model: str,
        api_key: str | None = None,
        local_mode: bool = False,
    ) -> None:
        config = self.load_api_config()
        config.update(
            {
                "provider": provider or "deepseek",
                "base_url": base_url or DEFAULT_API_CONFIG["base_url"],
                "model": model or DEFAULT_API_CONFIG["model"],
                "local_mode": bool(local_mode),
            }
        )
        self.save_api_config(config)
        self._sync_app_api(config)
        if api_key is not None:
            self.write_env_values(
                {
                    "DEEPSEEK_API_KEY": api_key.strip(),
                    "DEEPSEEK_BASE_URL": str(config["base_url"]).strip(),
                    "DEEPSEEK_MODEL": str(config["model"]).strip(),
                }
            )

    def current_api_key(self) -> str:
        env = dotenv_values(self.env_path) if self.env_path.exists() else {}
        return str(env.get("DEEPSEEK_API_KEY") or "").strip()

    def write_env_values(self, values: dict[str, str]) -> None:
        current = _read_env_lines(self.env_path)
        merged = dict(current)
        for key, value in values.items():
            if key:
                merged[key] = value
        lines = [f"{key}={_quote_env(value)}" for key, value in merged.items()]
        tmp = self.env_path.with_suffix(".env.tmp")
        tmp.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        tmp.replace(self.env_path)

    def test_api_connection(self, timeout: int = 8) -> tuple[bool, str]:
        config = self.load_api_config()
        if config.get("local_mode"):
            return True, "本地模式已开启，API 测试跳过。"
        api_key = self.current_api_key()
        if not api_key or api_key == "your_api_key_here":
            return False, "未配置 API Key。"
        try:
            response = requests.post(
                str(config.get("base_url", DEFAULT_API_CONFIG["base_url"])).rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": str(config.get("model", DEFAULT_API_CONFIG["model"])),
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 4,
                    "temperature": 0,
                },
                timeout=max(1, min(timeout, 20)),
            )
            if response.status_code < 400:
                return True, f"连接成功，key={mask_key(api_key)}。"
            return False, f"连接失败：HTTP {response.status_code}，key={mask_key(api_key)}。"
        except requests.RequestException as exc:
            return False, f"连接失败：{exc.__class__.__name__}，key={mask_key(api_key)}。"

    def _sync_app_api(self, api_config: dict[str, Any]) -> None:
        app_config = self.load_app_config()
        app_config.setdefault("api", {})["base_url"] = api_config.get("base_url", DEFAULT_API_CONFIG["base_url"])
        app_config.setdefault("api", {})["model"] = api_config.get("model", DEFAULT_API_CONFIG["model"])
        app_config.setdefault("api", {})["provider"] = api_config.get("provider", "deepseek")
        app_config.setdefault("api", {})["local_mode"] = bool(api_config.get("local_mode", False))
        self.save_app_config(app_config)

    def _load_json(self, path: Path, default: dict[str, Any]) -> Any:
        try:
            if not path.exists():
                return deepcopy(default)
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self._backup_broken(path)
            return deepcopy(default)
        except OSError:
            return deepcopy(default)

    def _save_json_atomic(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def _backup_broken(self, path: Path) -> None:
        if not path.exists():
            return
        backup = path.with_suffix(path.suffix + f".broken-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        try:
            path.replace(backup)
        except OSError:
            pass


def _read_env_lines(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _quote_env(value: str) -> str:
    if not value:
        return ""
    if any(ch.isspace() for ch in value):
        return json.dumps(value, ensure_ascii=False)
    return value

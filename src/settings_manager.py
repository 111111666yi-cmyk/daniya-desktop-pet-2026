from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from .chat_client import mask_key
from .config_manager import ConfigManager, deep_merge
from .utils import ensure_dir, runtime_root
from .llm.provider_manager import ProviderManager


DEFAULT_API_CONFIG: dict[str, Any] = {
    "active_provider": "deepseek",
    "providers": {
        "deepseek": {
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-chat",
            "timeout": 20,
            "max_tokens": 360,
            "temperature": 0.8,
            "api_key_env": "DEEPSEEK_API_KEY"
        },
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o",
            "timeout": 30,
            "max_tokens": 360,
            "temperature": 0.8,
            "api_key_env": "OPENAI_API_KEY"
        },
        "claude": {
            "base_url": "https://api.anthropic.com/v1",
            "model": "claude-3-5-sonnet-20240620",
            "timeout": 30,
            "max_tokens": 1024,
            "temperature": 0.8,
            "api_key_env": "ANTHROPIC_API_KEY"
        },
        "local_openai_compatible": {
            "base_url": "http://localhost:1234/v1",
            "model": "local-model",
            "timeout": 60,
            "max_tokens": 512,
            "temperature": 0.8,
            "api_key_env": "OPENAI_COMPATIBLE_API_KEY"
        }
    },
    "local_mode": False,
    "chat": {
        "fallback_reply": "达妮娅现在还没有连上大脑，但我已经在这里啦！",
        "api_error_fallback_reply": "达妮娅刚刚走神了一下……但我还在哦。"
    }
}


class SettingsManager:
    def __init__(self, config_manager: ConfigManager | None = None, root: Path | None = None) -> None:
        self.root = root or runtime_root()
        self.config_manager = config_manager or ConfigManager()
        self.config_dir = ensure_dir(self.root / "config")
        self.env_path = self.root / ".env"
        self.api_config_path = self.config_dir / "api_config.json"
        self.model_profiles_path = self.config_dir / "model_profiles.json"
        self.ensure_configs()

    def ensure_configs(self) -> None:
        self.config_manager.load_app_config()
        if not self.api_config_path.exists():
            self.save_api_config(DEFAULT_API_CONFIG)
        else:
            loaded = self._load_json(self.api_config_path, DEFAULT_API_CONFIG)
            self.save_api_config(loaded)
            
        if not self.model_profiles_path.exists():
            default_profiles = {
                "active_text_profile_id": "deepseek_default",
                "active_vision_profile_id": "",
                "active_tts_profile_id": "",
                "active_image_profile_id": "",
                "profiles": [
                    {
                        "id": "deepseek_default",
                        "name": "DeepSeek 默认",
                        "type": "text",
                        "provider": "deepseek",
                        "api_style": "openai_compatible",
                        "base_url": "https://api.deepseek.com",
                        "model": "deepseek-chat",
                        "api_key_env": "DEEPSEEK_API_KEY",
                        "enabled": True,
                        "capabilities": ["text"],
                        "source": "cloud"
                    },
                    {
                        "id": "openai_default",
                        "name": "OpenAI GPT-4o",
                        "type": "text",
                        "provider": "openai",
                        "api_style": "openai_compatible",
                        "base_url": "https://api.openai.com/v1",
                        "model": "gpt-4o",
                        "api_key_env": "OPENAI_API_KEY",
                        "enabled": True,
                        "capabilities": ["text"],
                        "source": "cloud"
                    },
                    {
                        "id": "ollama_qwen25_05b",
                        "name": "Qwen2.5 0.5B - Ollama",
                        "type": "text",
                        "provider": "ollama",
                        "api_style": "ollama",
                        "base_url": "http://localhost:11434",
                        "model": "qwen2.5:0.5b",
                        "enabled": False,
                        "capabilities": ["text"],
                        "source": "local",
                        "license_required": True
                    }
                ]
            }
            self.save_model_profiles(default_profiles)
        else:
            self.load_model_profiles()

    def load_model_profiles(self) -> dict[str, Any]:
        default_profiles = {
            "active_text_profile_id": "deepseek_default",
            "active_vision_profile_id": "",
            "active_tts_profile_id": "",
            "active_image_profile_id": "",
            "profiles": []
        }
        loaded = self._load_json(self.model_profiles_path, default_profiles)
        # 自动脱敏，防止明文 key 写入 JSON
        profiles = loaded.get("profiles", [])
        for p in profiles:
            p.pop("api_key", None)
            p.pop("api_key_masked", None)
        return loaded

    def save_model_profiles(self, profiles_dict: dict[str, Any]) -> None:
        clean = deepcopy(profiles_dict)
        profiles = clean.get("profiles", [])
        for p in profiles:
            p.pop("api_key", None)
            p.pop("api_key_masked", None)
        self._save_json_atomic(self.model_profiles_path, clean)

    def load_app_config(self) -> dict[str, Any]:
        return self.config_manager.load_app_config()

    def save_app_config(self, config: dict[str, Any]) -> None:
        self.config_manager.save_app_config(config)

    def load_api_config(self) -> dict[str, Any]:
        loaded = self._load_json(self.api_config_path, DEFAULT_API_CONFIG)
        if not isinstance(loaded, dict):
            loaded = {}
        # 向下兼容旧版本 api_config.json
        if "providers" not in loaded:
            old_provider = loaded.get("provider", "deepseek")
            loaded = {
                "active_provider": old_provider,
                "providers": {
                    old_provider: {
                        "base_url": loaded.get("base_url", "https://api.deepseek.com"),
                        "model": loaded.get("model", "deepseek-chat"),
                        "timeout": loaded.get("timeout_seconds", 20),
                        "api_key_env": loaded.get("api_key_env", "DEEPSEEK_API_KEY"),
                    }
                },
                "local_mode": loaded.get("local_mode", False),
                "chat": loaded.get("chat", DEFAULT_API_CONFIG["chat"])
            }
        config = deep_merge(DEFAULT_API_CONFIG, loaded)

        # 为当前 active_provider 脱敏 key（不创建完整 ProviderManager 实例）
        active_provider = config.get("active_provider", "deepseek")
        providers = config.get("providers", {})
        if active_provider in providers:
            env_key_name = providers[active_provider].get("api_key_env", f"{active_provider.upper()}_API_KEY")
            raw_key = self.current_api_key(env_key_name)
            providers[active_provider]["api_key_masked"] = mask_key(raw_key)

        return config

    def save_api_config(self, config: dict[str, Any]) -> None:
        safe = deep_merge(DEFAULT_API_CONFIG, config if isinstance(config, dict) else {})
        # 清除可能存在的明文 key
        for p_name, p_conf in safe.get("providers", {}).items():
            p_conf.pop("api_key", None)
            p_conf.pop("api_key_masked", None)
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
        config["active_provider"] = provider or "deepseek"
        config["local_mode"] = bool(local_mode)
        
        providers = config.setdefault("providers", {})
        prov_conf = providers.setdefault(provider, {})
        prov_conf["base_url"] = base_url or DEFAULT_API_CONFIG["providers"]["deepseek"]["base_url"]
        prov_conf["model"] = model or DEFAULT_API_CONFIG["providers"]["deepseek"]["model"]
        
        env_key_name = ""
        if provider == "deepseek":
            env_key_name = "DEEPSEEK_API_KEY"
        elif provider == "openai":
            env_key_name = "OPENAI_API_KEY"
        elif provider == "claude":
            env_key_name = "ANTHROPIC_API_KEY"
        elif provider == "local_openai_compatible":
            env_key_name = "OPENAI_COMPATIBLE_API_KEY"
        else:
            env_key_name = f"{provider.upper()}_API_KEY"
            
        prov_conf["api_key_env"] = env_key_name

        self.save_api_config(config)
        self._sync_app_api(config)
        self._sync_model_profiles(provider, base_url, model, env_key_name)

        if api_key is not None and env_key_name:
            self.write_env_values(
                {
                    env_key_name: api_key.strip(),
                }
            )

    def current_api_key(self, env_key_name: str = "DEEPSEEK_API_KEY") -> str:
        env = dotenv_values(self.env_path) if self.env_path.exists() else {}
        key = os.environ.get(env_key_name) or env.get(env_key_name)
        return str(key or "").strip()

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

        pm = ProviderManager(config)
        profile = pm.get_active_profile()

        env_key_name = profile.get("api_key_env", "")
        raw_key = self.current_api_key(env_key_name)
        provider = profile.get("provider", "")

        ok, msg = pm.test_profile_model(profile)

        if provider not in ("ollama",) and raw_key:
            msg += f" (key={mask_key(raw_key)})"

        return ok, msg

    def _sync_app_api(self, api_config: dict[str, Any]) -> None:
        app_config = self.load_app_config()
        app_config.setdefault("api", {})["local_mode"] = bool(api_config.get("local_mode", False))
        self.save_app_config(app_config)

    def _sync_model_profiles(self, provider: str, base_url: str, model: str, env_key_name: str) -> None:
        """将 api_config.json 的 active_provider 同步到 model_profiles.json 的 active_text_profile_id。"""
        profiles_data = self.load_model_profiles()
        profiles = profiles_data.get("profiles", [])

        # 查找匹配的 profile，或创建新的
        target_id = f"{provider}_default"
        found = False
        for p in profiles:
            if p.get("id") == target_id:
                p["base_url"] = base_url
                p["model"] = model
                p["api_key_env"] = env_key_name
                p["enabled"] = True
                found = True
                break

        if not found:
            source = "local" if provider in ("ollama", "lm_studio", "llama_cpp", "local_openai_compatible") else "cloud"
            profiles.append({
                "id": target_id,
                "name": f"{provider} ({model})",
                "type": "text",
                "provider": provider,
                "api_style": "ollama" if provider == "ollama" else "openai_compatible",
                "base_url": base_url,
                "model": model,
                "api_key_env": env_key_name,
                "enabled": True,
                "capabilities": ["text"],
                "source": source,
            })

        profiles_data["active_text_profile_id"] = target_id
        self.save_model_profiles(profiles_data)

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

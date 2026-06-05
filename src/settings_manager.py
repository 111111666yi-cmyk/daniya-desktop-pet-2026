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
from .llm.provider_registry import Provider, ProviderMeta


def _build_default_api_config() -> dict[str, Any]:
    """从 ProviderRegistry 自动生成 DEFAULT_API_CONFIG，避免硬编码。"""
    config: dict[str, Any] = {
        "active_provider": Provider.DEEPSEEK,
        "providers": {},
        "local_mode": False,
        "chat": {
            "fallback_reply": "……那边暂时没有回音。我先在这里。",
            "fallback_replies": [
                "……那边暂时没有回音。我先在这里。",
                "……现在连不上。你可以稍后再试。",
                "……这次没有收到回复。先别重复发送。"
            ],
            "api_error_fallback_reply": "……刚才没有连上。我先在这里。",
            "api_error_fallback_replies": [
                "……刚才没有连上。我先在这里。",
                "……连接暂时不稳定。稍后再试。",
                "……那边没有回音。这次先停在这里。"
            ]
        },
    }
    # 只为云端 Provider 生成默认 entry
    for key in (Provider.DEEPSEEK, Provider.OPENAI, Provider.CLAUDE, Provider.ZAI, Provider.LOCAL_OPENAI_COMPATIBLE):
        meta = ProviderMeta.get(key)
        config["providers"][key] = {
            "base_url": meta["base_url"],
            "model": meta["default_model"],
            "timeout": meta["timeout"],
            "max_tokens": meta["max_tokens"],
            "temperature": 0.8,
            "api_key_env": meta["api_key_env"],
            "auth_header": meta["auth_header"],
        }
    return config


DEFAULT_API_CONFIG: dict[str, Any] = _build_default_api_config()


def _build_default_model_profiles() -> dict[str, Any]:
    """从 ProviderRegistry 自动生成默认 model_profiles，避免硬编码。"""
    cloud_keys = (Provider.DEEPSEEK, Provider.OPENAI, Provider.ZAI)
    local_entries = [
        ("ollama_qwen25_05b", "Qwen2.5 0.5B - Ollama", Provider.OLLAMA, "ollama", "qwen2.5:0.5b"),
    ]

    profiles: list[dict[str, Any]] = []
    for key in cloud_keys:
        meta = ProviderMeta.get(key)
        profiles.append({
            "id": ProviderMeta.make_profile_id(key),
            "name": f"{meta['display_name']} 默认",
            "type": "text",
            "provider": key,
            "api_style": meta["api_style"],
            "base_url": meta["base_url"],
            "model": meta["default_model"],
            "api_key_env": meta["api_key_env"],
            "auth_header": meta["auth_header"],
            "enabled": True,
            "capabilities": ["text"],
            "source": "cloud",
        })

    for pid, pname, pkey, pstyle, pmodel in local_entries:
        profiles.append({
            "id": pid,
            "name": pname,
            "type": "text",
            "provider": pkey,
            "api_style": pstyle,
            "base_url": ProviderMeta.get_default_url(pkey),
            "model": pmodel,
            "enabled": False,
            "capabilities": ["text"],
            "source": "local",
            "license_required": True,
        })

    return {
        "active_text_profile_id": ProviderMeta.make_profile_id(Provider.DEEPSEEK),
        "active_vision_profile_id": "",
        "active_tts_profile_id": "",
        "active_image_profile_id": "",
        "profile_history": {
            "text": [ProviderMeta.make_profile_id(Provider.DEEPSEEK)],
            "vision": [],
            "tts": [],
            "image": [],
        },
        "profiles": profiles,
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
            default_profiles = _build_default_model_profiles()
            self.save_model_profiles(default_profiles)
        else:
            self.load_model_profiles()

    def load_model_profiles(self) -> dict[str, Any]:
        default_profiles = {
            "active_text_profile_id": ProviderMeta.make_profile_id(Provider.DEEPSEEK),
            "active_vision_profile_id": "",
            "active_tts_profile_id": "",
            "active_image_profile_id": "",
            "profile_history": {
                "text": [ProviderMeta.make_profile_id(Provider.DEEPSEEK)],
                "vision": [],
                "tts": [],
                "image": [],
            },
            "profiles": []
        }
        loaded = self._load_json(self.model_profiles_path, default_profiles)
        for key, value in default_profiles.items():
            loaded.setdefault(key, deepcopy(value))
        if not isinstance(loaded.get("profile_history"), dict):
            loaded["profile_history"] = deepcopy(default_profiles["profile_history"])
        for slot in ("text", "vision", "tts", "image"):
            history = loaded["profile_history"].get(slot, [])
            loaded["profile_history"][slot] = history if isinstance(history, list) else []
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

        # 为当前 active_provider 脱敏 key
        active_provider = config.get("active_provider", Provider.DEEPSEEK)
        providers = config.get("providers", {})
        if active_provider in providers:
            env_key_name = providers[active_provider].get("api_key_env", ProviderMeta.get_api_key_env(active_provider))
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
        auth_header: str | None = None,
        local_mode: bool = False,
        activate: bool = False,
    ) -> None:
        config = self.load_api_config()
        if activate:
            config["active_provider"] = provider or Provider.DEEPSEEK
        else:
            config.setdefault("active_provider", Provider.DEEPSEEK)
        config["local_mode"] = bool(local_mode)

        providers = config.setdefault("providers", {})
        prov_conf = providers.setdefault(provider, {})
        default_meta = ProviderMeta.get(provider)
        prov_conf["base_url"] = base_url or default_meta["base_url"]
        prov_conf["model"] = model or default_meta["default_model"]

        env_key_name = ProviderMeta.get_api_key_env(provider)
        auth_header_name = _resolve_auth_header(provider, base_url, auth_header)

        prov_conf["api_key_env"] = env_key_name
        prov_conf["auth_header"] = auth_header_name

        if api_key is not None and env_key_name:
            self.write_env_values(
                {
                    env_key_name: api_key.strip(),
                }
            )

        self.save_api_config(config)
        self._sync_app_api(config)
        self._sync_model_profiles(provider, base_url, model, env_key_name, auth_header_name, activate=False)

        if activate and not local_mode:
            target_id = ProviderMeta.make_profile_id(provider)
            ok, msg = self.activate_text_profile(target_id)
            if not ok:
                raise RuntimeError(msg)

    def current_api_key(self, env_key_name: str = "DEEPSEEK_API_KEY") -> str:
        if not env_key_name:
            return ""
        env = dotenv_values(self.env_path) if self.env_path.exists() else {}
        key = os.environ.get(env_key_name) or env.get(env_key_name)
        return str(key or "").strip()

    def clear_api_key(self, env_key_name: str) -> None:
        """从 .env 文件中删除指定 API Key。"""
        if not env_key_name:
            return
        current = _read_env_lines(self.env_path)
        if env_key_name in current:
            del current[env_key_name]
            lines = [f"{k}={_quote_env(v)}" for k, v in current.items()]
            tmp = self.env_path.with_suffix(".env.tmp")
            tmp.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
            tmp.replace(self.env_path)

    def delete_provider_config(self, provider: str) -> None:
        """从 api_config.json 中删除某个 provider 的配置。"""
        config = self.load_api_config()
        providers = config.get("providers", {})
        if provider in providers:
            del providers[provider]
            if config.get("active_provider") == provider:
                config["active_provider"] = "deepseek"
            self.save_api_config(config)

    def load_multimodal_config(self) -> dict[str, str]:
        """读取多模态配置文件。"""
        return self._load_json(
            self.config_dir / "multimodal_config.json",
            {"tts": "none", "tts_lang": "zh-CN", "image": "none", "image_to_image": "none", "video": "none"},
        )

    def save_multimodal_config(self, config: dict[str, str]) -> None:
        """保存多模态配置。"""
        self._save_json_atomic(self.config_dir / "multimodal_config.json", config)

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
            return False, "本地 fallback 模式已开启，云端 API 未测试；关闭本地模式后再测试连接。"

        pm = ProviderManager(config)
        profile = pm.get_active_profile()

        env_key_name = profile.get("api_key_env", "")
        raw_key = self.current_api_key(env_key_name)
        provider = profile.get("provider", "")

        ok, msg = pm.test_profile_model(profile, timeout=timeout)

        if provider not in ("ollama",) and raw_key:
            msg += f" (key={mask_key(raw_key)})"

        return ok, msg

    def resolve_auth_header(self, provider: str, base_url: str, auth_header: str | None = None) -> str:
        return _resolve_auth_header(provider, base_url, auth_header)

    def activate_text_profile(self, profile_id: str) -> tuple[bool, str]:
        pm = ProviderManager(api_config=self.load_api_config())
        pm.model_profiles_path = self.model_profiles_path
        pm.env_path = self.env_path
        pm.reload()
        ok, msg = pm.switch_active_profile(profile_id, slot="text")
        if ok:
            self.sync_api_active_provider_from_profile(profile_id)
        return ok, msg

    def sync_api_active_provider_from_profile(self, profile_id: str) -> None:
        profiles_data = self.load_model_profiles()
        profile = next((p for p in profiles_data.get("profiles", []) if p.get("id") == profile_id), None)
        if not profile:
            return
        provider = str(profile.get("provider", Provider.DEEPSEEK))
        config = self.load_api_config()
        config["active_provider"] = provider
        config["local_mode"] = False
        providers = config.setdefault("providers", {})
        entry = providers.setdefault(provider, {})
        entry["base_url"] = str(profile.get("base_url", ""))
        entry["model"] = str(profile.get("model", ""))
        entry["api_key_env"] = str(profile.get("api_key_env", ProviderMeta.get_api_key_env(provider)))
        entry["auth_header"] = str(profile.get("auth_header", ProviderMeta.get_auth_header(provider)))
        self.save_api_config(config)
        self._sync_app_api(config)

    def set_profile_enabled(self, profile_id: str, enabled: bool, slot: str = "text") -> tuple[bool, str]:
        profiles_data = self.load_model_profiles()
        active_key = _active_key_for_slot(slot)
        if not enabled and profiles_data.get(active_key) == profile_id:
            return False, "当前生效模型不能停用；请先切换到另一个可用模型。"

        for profile in profiles_data.get("profiles", []):
            if profile.get("id") == profile_id:
                profile["enabled"] = bool(enabled)
                self.save_model_profiles(profiles_data)
                return True, "已启用" if enabled else "已停用"
        return False, f"未找到模型配置: {profile_id}"

    def _sync_app_api(self, api_config: dict[str, Any]) -> None:
        app_config = self.load_app_config()
        app_config.setdefault("api", {})["local_mode"] = bool(api_config.get("local_mode", False))
        self.save_app_config(app_config)

    def _sync_model_profiles(
        self,
        provider: str,
        base_url: str,
        model: str,
        env_key_name: str,
        auth_header: str,
        activate: bool = False,
    ) -> None:
        """将 api_config.json 的 Provider 同步到 model_profiles.json。

        只更新/创建 profile 条目；生效切换必须走 activate_text_profile() 的验证事务。
        activate 参数保留给旧调用签名，不再直接写 active_text_profile_id。
        """
        profiles_data = self.load_model_profiles()
        profiles = profiles_data.get("profiles", [])

        target_id = ProviderMeta.make_profile_id(provider)
        found = False
        for p in profiles:
            if p.get("id") == target_id:
                p["base_url"] = base_url
                p["model"] = model
                p["api_key_env"] = env_key_name
                p["auth_header"] = auth_header
                p["enabled"] = True
                found = True
                break

        if not found:
            norm_key = ProviderMeta.normalize(provider)
            source = "local" if ProviderMeta.is_local(norm_key) else "cloud"
            profiles.append({
                "id": target_id,
                "name": f"{provider} ({model})",
                "type": "text",
                "provider": norm_key,
                "api_style": ProviderMeta.get_api_style(norm_key),
                "base_url": base_url,
                "model": model,
                "api_key_env": env_key_name,
                "auth_header": auth_header,
                "enabled": True,
                "capabilities": ["text"],
                "source": source,
            })

        self.save_model_profiles(profiles_data)

    def save_local_model_profile(self, provider: str, base_url: str, model: str, service_label: str = "") -> None:
        """保存本地模型 profile 到 model_profiles.json，不改变当前活跃的云端 Provider。"""
        profiles_data = self.load_model_profiles()
        profiles = profiles_data.get("profiles", [])

        norm_key = ProviderMeta.normalize(provider)
        target_id = ProviderMeta.make_profile_id(norm_key, model)
        found = False
        for p in profiles:
            if p.get("id") == target_id:
                p["base_url"] = base_url
                p["model"] = model
                p["provider"] = norm_key
                p["enabled"] = True
                found = True
                break

        if not found:
            profiles.append({
                "id": target_id,
                "name": f"{service_label or ProviderMeta.get_display_name(norm_key)} {model}",
                "type": "text",
                "provider": norm_key,
                "api_style": ProviderMeta.get_api_style(norm_key),
                "base_url": base_url,
                "model": model,
                "api_key_env": "",
                "enabled": True,
                "capabilities": ["text"],
                "source": "local",
            })

        # 不改变 active_text_profile_id
        self.save_model_profiles(profiles_data)

    def save_and_activate_local_model_profile(self, provider: str, base_url: str, model: str, service_label: str = "") -> tuple[bool, str]:
        """保存本地模型 profile，并且只在连接验证成功后切换为当前文本模型。"""
        self.save_local_model_profile(provider, base_url, model, service_label)
        target_id = ProviderMeta.make_profile_id(provider, model)
        return self.activate_text_profile(target_id)

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
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
            try:
                tmp.replace(path)
            except OSError:
                path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
                if tmp.exists():
                    try:
                        tmp.unlink()
                    except OSError:
                        pass
        except Exception:
            try:
                path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

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


def _resolve_auth_header(provider: str, base_url: str, auth_header: str | None = None) -> str:
    normalized = ProviderMeta.normalize(provider)
    if normalized == Provider.OPENAI_COMPATIBLE and "xiaomimimo.com" in base_url.lower():
        return "api-key"
    if auth_header and auth_header.strip():
        return auth_header.strip()
    return ProviderMeta.get_auth_header(normalized)


def _active_key_for_slot(slot: str) -> str:
    mapping = {
        "text": "active_text_profile_id",
        "vision": "active_vision_profile_id",
        "tts": "active_tts_profile_id",
        "image": "active_image_profile_id",
    }
    return mapping.get(slot, f"active_{slot}_profile_id")

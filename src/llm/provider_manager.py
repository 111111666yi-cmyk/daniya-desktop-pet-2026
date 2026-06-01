import json
import os
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from src.utils import runtime_root

from .boundaries import (
    AuthError,
    BoundaryError,
    MalformedResponse,
    NetworkError,
    RateLimitError,
    ServerError,
)
from .boundaries import deepseek_api
from .boundaries import ollama_api
from .boundaries import openai_api
from .boundaries import anthropic_api
from .boundaries.ollama_api import ModelNotFoundError
from .provider_registry import Provider, ProviderMeta


class ProviderManager:
    """统一的模型 Provider 管理中心。

    职责：
    - 读取 model_profiles.json，决定当前活跃模型
    - 将请求路由到对应的边界模块 (boundaries/*.py)
    - 不直接处理 HTTP、重试、鉴权 —— 这些在边界模块中

    边界模块处理各自外部系统的失败模式：
    - DeepSeek: deepseek_api.py  (限流/鉴权/格式异常)
    - OpenAI:   openai_api.py    (限流/鉴权/格式异常)
    - Ollama:   ollama_api.py    (服务不可达/模型不存在)
    - Claude:   anthropic_api.py (限流/鉴权/格式异常)
    """

    def __init__(self, api_config: dict[str, Any], system_prompt: str = "", prompt_prefix: str = ""):
        self.api_config = api_config
        self.system_prompt = system_prompt
        self.prompt_prefix = prompt_prefix

        self.root = runtime_root()
        self.model_profiles_path = self.root / "config" / "model_profiles.json"
        self.env_path = self.root / ".env"

        self.profiles_data = self.load_profiles()
        self.last_source = "无"
        self.last_error = "无"
        self._fallback_index = 0

    # ── config ──────────────────────────────────────────────

    def load_profiles(self) -> dict[str, Any]:
        """读取 model_profiles.json，失败则返回默认结构。"""
        if self.model_profiles_path.exists():
            try:
                with open(self.model_profiles_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "profiles" in data:
                        return data
            except Exception:
                pass
        return _default_profiles()

    def reload(self) -> None:
        self.profiles_data = self.load_profiles()

    def get_active_profile(self) -> dict[str, Any]:
        profiles = self.profiles_data.get("profiles", [])
        active_id = self.profiles_data.get("active_text_profile_id", ProviderMeta.make_profile_id(Provider.DEEPSEEK))
        for p in profiles:
            if p.get("id") == active_id and _profile_enabled(p) and _profile_supports_slot(p, "text"):
                return p
        for p in profiles:
            if p.get("id") == ProviderMeta.make_profile_id(Provider.DEEPSEEK) and _profile_enabled(p):
                return p
        for p in profiles:
            if _profile_enabled(p) and _profile_supports_slot(p, "text"):
                return p
        if profiles:
            return profiles[0]
        return _default_profiles()["profiles"][0]

    # ── routing ─────────────────────────────────────────────

    def chat(self, messages: list[dict[str, str]]) -> tuple[str, str]:
        """向当前 active 模型发送消息。
        返回 (response_text, source)。
        所有外部系统的失败模式由边界模块处理。
        """
        profile = self.get_active_profile()
        provider = profile.get("provider", "deepseek")
        model = profile.get("model", "")
        base_url = str(profile.get("base_url", ""))
        api_key = self._get_api_key(profile.get("api_key_env", ""))
        auth_header = self._auth_header_for_profile(profile)

        try:
            if provider == Provider.OLLAMA:
                response = ollama_api.chat(
                    messages,
                    base_url=base_url,
                    model=model,
                    timeout=int(profile.get("timeout", 20)),
                )
            elif provider in (Provider.CLAUDE, "anthropic"):  # "anthropic" 为历史兼容
                response = anthropic_api.chat(
                    messages,
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    max_tokens=int(profile.get("max_tokens", 1024)),
                    timeout=int(profile.get("timeout", 30)),
                )
            elif provider == Provider.DEEPSEEK:
                response = deepseek_api.chat(
                    messages,
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    max_tokens=int(profile.get("max_tokens", 360)),
                    timeout=int(profile.get("timeout", 20)),
                )
            else:
                # openai, openai_compatible, lm_studio, llama_cpp, local_openai_compatible, custom
                response = openai_api.chat(
                    messages,
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    auth_header=auth_header,
                    max_tokens=int(profile.get("max_tokens", 360)),
                    timeout=int(profile.get("timeout", 20)),
                )

            self.last_source = f"{provider} ({model})"
            self.last_error = "无"
            print(f"[Daniya] Chat response: provider={provider}, model={model}, source={profile.get('source', 'cloud')}, fallback_used=False")
            return response, "api"

        except AuthError as e:
            self.last_error = f"auth: {e}"
        except RateLimitError as e:
            self.last_error = f"rate_limit: {e}"
        except ServerError as e:
            self.last_error = f"server_error: {e}"
        except NetworkError as e:
            self.last_error = f"network: {e}"
        except MalformedResponse as e:
            self.last_error = f"malformed: {e}"
        except ModelNotFoundError as e:
            self.last_error = f"model_not_found: {e}"
        except BoundaryError as e:
            self.last_error = f"boundary: {e}"
        except Exception as e:
            self.last_error = str(e)

        print(f"[Daniya] Chat response: provider={provider}, model={model}, source=local, fallback_used=True, error_summary=\"{self.last_error}\"")
        self.last_source = "local_fallback"
        return self.local_fallback(api_error=True), "local"

    def local_fallback(self, api_error: bool = False) -> str:
        chat_config = self.api_config.get("chat", {})
        list_key = "api_error_fallback_replies" if api_error else "fallback_replies"
        replies = chat_config.get(list_key)
        if isinstance(replies, list):
            candidates = [str(item).strip() for item in replies if str(item).strip()]
            if candidates:
                reply = candidates[self._fallback_index % len(candidates)]
                self._fallback_index += 1
                return reply
        if api_error:
            return str(chat_config.get("api_error_fallback_reply", "达妮娅刚刚走神了一下……但我还在哦。"))
        return str(chat_config.get("fallback_reply", "达妮娅现在还没有连上大脑，但我已经在这里啦！"))

    def test_profile_model(
        self,
        profile: dict[str, Any],
        api_key_override: str | None = None,
        timeout: int = 8,
    ) -> tuple[bool, str]:
        """向模型发送测试消息验证可用性。返回 (ok, message)。"""
        provider = profile.get("provider", "deepseek")
        model = profile.get("model", "")
        base_url = str(profile.get("base_url", ""))
        api_key = str(api_key_override).strip() if api_key_override is not None else self._get_api_key(profile.get("api_key_env", ""))
        auth_header = self._auth_header_for_profile(profile)

        try:
            if provider == Provider.OLLAMA:
                ok = ollama_api.test_connection(base_url=base_url)
                return ok, "Ollama 服务连接成功" if ok else "Ollama 服务不可达"
            elif provider in (Provider.CLAUDE, "anthropic"):
                ok = anthropic_api.chat(
                    [{"role": "user", "content": "Hi"}],
                    api_key=api_key, base_url=base_url, model=model,
                    max_tokens=5, timeout=timeout,
                )
                return True, "连接成功"
            elif provider == Provider.DEEPSEEK:
                ok = deepseek_api.test_connection(
                    api_key=api_key, base_url=base_url, model=model, timeout=timeout,
                )
                return ok, "连接成功" if ok else "连接失败"
            else:
                ok = openai_api.test_connection(
                    api_key=api_key, base_url=base_url, model=model, auth_header=auth_header, timeout=timeout,
                )
                return ok, "连接成功" if ok else "连接失败"
        except Exception as e:
            return False, str(e)

    def switch_active_profile(self, new_profile_id: str, slot: str = "text") -> tuple[bool, str]:
        if slot != "text":
            return False, "ProviderManager 只负责 text 模型切换；TTS/图像等能力必须使用独立切换器。"

        profiles = self.profiles_data.get("profiles", [])
        target = next((p for p in profiles if p.get("id") == new_profile_id), None)
        if not target:
            return False, f"未找到模型配置: {new_profile_id}"
        if not _profile_supports_slot(target, slot):
            return False, f"模型配置 {new_profile_id} 不支持 {slot}"
        if not _profile_enabled(target):
            return False, f"模型配置 {new_profile_id} 已停用"

        ok, msg = self.test_profile_model(target)
        if not ok:
            return False, f"模型测试未通过: {msg}"

        active_key = _active_key_for_slot(slot)
        old_id = self.profiles_data.get(active_key, ProviderMeta.make_profile_id(Provider.DEEPSEEK))
        self.profiles_data[active_key] = new_profile_id
        _record_profile_history(self.profiles_data, slot, new_profile_id)

        try:
            self.model_profiles_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.model_profiles_path.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.profiles_data, f, ensure_ascii=False, indent=2)
            tmp.replace(self.model_profiles_path)
            self.reload()
            if self.profiles_data.get(active_key) != new_profile_id:
                self.profiles_data[active_key] = old_id
                return False, "写入后读回校验失败"
            return True, "切换成功"
        except Exception as e:
            self.profiles_data[active_key] = old_id
            return False, f"写入配置文件失败: {str(e)}"

    def prompt_to_messages(self, prompt: str, history_messages: list[dict[str, str]] | None = None) -> list[dict[str, str]]:
        system_content = f"{self.prompt_prefix}\n\n角色设定：\n{self.system_prompt}".strip()
        messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]
        if history_messages:
            messages.extend(history_messages)
        messages.append({"role": "user", "content": prompt})
        return messages

    # ── internal ────────────────────────────────────────────

    def _get_api_key(self, env_key_name: str) -> str:
        if not env_key_name:
            return ""
        env = dotenv_values(self.env_path) if self.env_path.exists() else {}
        key = os.environ.get(env_key_name) or env.get(env_key_name)
        return str(key or "").strip()

    def _auth_header_for_profile(self, profile: dict[str, Any]) -> str:
        value = str(profile.get("auth_header", "")).strip()
        if value:
            return value
        provider = str(profile.get("provider", ""))
        return ProviderMeta.get_auth_header(provider)


def _default_profiles() -> dict[str, Any]:
    meta = ProviderMeta.get(Provider.DEEPSEEK)
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
        "profiles": [
            {
                "id": ProviderMeta.make_profile_id(Provider.DEEPSEEK),
                "name": f"{meta['display_name']} 默认",
                "type": "text",
                "provider": Provider.DEEPSEEK,
                "api_style": meta["api_style"],
                "base_url": meta["base_url"],
                "model": meta["default_model"],
                "api_key_env": meta["api_key_env"],
                "auth_header": meta["auth_header"],
                "enabled": True,
                "capabilities": ["text"],
                "source": "cloud",
            }
        ],
    }


def _active_key_for_slot(slot: str) -> str:
    mapping = {
        "text": "active_text_profile_id",
        "vision": "active_vision_profile_id",
        "tts": "active_tts_profile_id",
        "image": "active_image_profile_id",
    }
    return mapping.get(slot, f"active_{slot}_profile_id")


def _profile_enabled(profile: dict[str, Any]) -> bool:
    return profile.get("enabled", True) is not False


def _profile_supports_slot(profile: dict[str, Any], slot: str) -> bool:
    capabilities = profile.get("capabilities", [])
    if isinstance(capabilities, list) and slot in capabilities:
        return True
    return str(profile.get("type", "")) == slot


def _record_profile_history(profiles_data: dict[str, Any], slot: str, profile_id: str, limit: int = 12) -> None:
    history = profiles_data.setdefault("profile_history", {})
    if not isinstance(history, dict):
        history = {}
        profiles_data["profile_history"] = history
    current = history.get(slot, [])
    if not isinstance(current, list):
        current = []
    clean = [str(item) for item in current if str(item) and str(item) != profile_id]
    history[slot] = [profile_id] + clean[: max(0, limit - 1)]

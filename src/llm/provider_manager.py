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
        active_id = self.profiles_data.get("active_text_profile_id", "deepseek_default")
        for p in profiles:
            if p.get("id") == active_id:
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

        try:
            if provider == "ollama":
                response = ollama_api.chat(
                    messages,
                    base_url=base_url,
                    model=model,
                    timeout=int(profile.get("timeout", 20)),
                )
            elif provider in ("claude", "anthropic"):
                response = anthropic_api.chat(
                    messages,
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    max_tokens=int(profile.get("max_tokens", 1024)),
                    timeout=int(profile.get("timeout", 30)),
                )
            elif provider == "deepseek":
                response = deepseek_api.chat(
                    messages,
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    timeout=int(profile.get("timeout", 20)),
                )
            else:
                # openai, openai_compatible, lm_studio, llama_cpp, custom
                response = openai_api.chat(
                    messages,
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
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
        except BoundaryError as e:
            self.last_error = f"boundary: {e}"
        except Exception as e:
            self.last_error = str(e)

        print(f"[Daniya] Chat response: provider={provider}, model={model}, source=local, fallback_used=True, error_summary=\"{self.last_error}\"")
        self.last_source = "local_fallback"
        return self.local_fallback(api_error=True), "local"

    def local_fallback(self, api_error: bool = False) -> str:
        chat_config = self.api_config.get("chat", {})
        if api_error:
            return str(chat_config.get("api_error_fallback_reply", "达妮娅刚刚走神了一下……但我还在哦。"))
        return str(chat_config.get("fallback_reply", "达妮娅现在还没有连上大脑，但我已经在这里啦！"))

    def test_profile_model(self, profile: dict[str, Any]) -> tuple[bool, str]:
        """向模型发送测试消息验证可用性。返回 (ok, message)。"""
        provider = profile.get("provider", "deepseek")
        model = profile.get("model", "")
        base_url = str(profile.get("base_url", ""))
        api_key = self._get_api_key(profile.get("api_key_env", ""))

        try:
            if provider == "ollama":
                ok = ollama_api.test_connection(base_url=base_url)
                return ok, "Ollama 服务连接成功" if ok else "Ollama 服务不可达"
            elif provider in ("claude", "anthropic"):
                ok = anthropic_api.chat(
                    [{"role": "user", "content": "Hi"}],
                    api_key=api_key, base_url=base_url, model=model,
                    max_tokens=5, timeout=8,
                )
                return True, "连接成功"
            elif provider == "deepseek":
                ok = deepseek_api.test_connection(
                    api_key=api_key, base_url=base_url, model=model, timeout=8,
                )
                return ok, "连接成功" if ok else "连接失败"
            else:
                ok = openai_api.test_connection(
                    api_key=api_key, base_url=base_url, model=model, timeout=8,
                )
                return ok, "连接成功" if ok else "连接失败"
        except Exception as e:
            return False, str(e)

    def switch_active_profile(self, new_profile_id: str) -> tuple[bool, str]:
        profiles = self.profiles_data.get("profiles", [])
        target = next((p for p in profiles if p.get("id") == new_profile_id), None)
        if not target:
            return False, f"未找到模型配置: {new_profile_id}"

        ok, msg = self.test_profile_model(target)
        if not ok:
            return False, f"模型测试未通过: {msg}"

        old_id = self.profiles_data.get("active_text_profile_id", "deepseek_default")
        self.profiles_data["active_text_profile_id"] = new_profile_id

        try:
            self.model_profiles_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.model_profiles_path.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.profiles_data, f, ensure_ascii=False, indent=2)
            tmp.replace(self.model_profiles_path)
            self.reload()
            return True, "切换成功"
        except Exception as e:
            self.profiles_data["active_text_profile_id"] = old_id
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


def _default_profiles() -> dict[str, Any]:
    return {
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
                "source": "cloud",
            }
        ],
    }

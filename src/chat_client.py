from __future__ import annotations

from typing import Any

import requests
from dotenv import dotenv_values

from .config_manager import ConfigManager
from .history_manager import HistoryManager
from .profile_manager import ProfileManager
from .utils import runtime_root


NO_KEY_FALLBACK = "达妮娅现在还没有连上大脑，但我已经在这里啦！"
API_ERROR_FALLBACK = "达妮娅刚刚走神了一下……但我还在哦。"


class ChatClient:
    def __init__(
        self,
        config_manager: ConfigManager,
        history_manager: HistoryManager,
        profile_manager: ProfileManager,
    ) -> None:
        self.config_manager = config_manager
        self.history_manager = history_manager
        self.profile_manager = profile_manager
        self.env_path = runtime_root() / ".env"
        self.reload()

    def reload(self) -> None:
        self.app_config = self.config_manager.load_app_config()
        self.system_prompt = self.config_manager.load_system_prompt()
        api_config = self.app_config.get("api", {})
        chat_config = self.app_config.get("chat", {})
        env = dotenv_values(self.env_path) if self.env_path.exists() else {}

        self.api_key = str(env.get("DEEPSEEK_API_KEY") or "").strip()
        self.base_url = str(env.get("DEEPSEEK_BASE_URL") or api_config.get("base_url", "https://api.deepseek.com")).strip()
        self.model = str(env.get("DEEPSEEK_MODEL") or api_config.get("model", "deepseek-chat")).strip()
        self.timeout = min(int(chat_config.get("timeout_seconds", 20)), 20)
        self.context_limit = int(chat_config.get("context_limit", 8))
        self.temperature = float(chat_config.get("temperature", 0.8))
        self.max_tokens = int(chat_config.get("max_tokens", 360))
        self.no_key_fallback = str(chat_config.get("fallback_reply", NO_KEY_FALLBACK))
        self.api_error_fallback = str(chat_config.get("api_error_fallback_reply", API_ERROR_FALLBACK))

        if self.env_path.exists():
            print(f"[Daniya] .env loaded: yes, key={mask_key(self.api_key)}, model={self.model}, base_url={self.base_url}")
        else:
            print("[Daniya] .env loaded: no, using local fallback mode")

    def reply(self, user_text: str) -> tuple[str, str]:
        if not self._has_api_key():
            print("[Daniya] chat source=local reason=missing_api_key")
            return self.local_reply(missing_key=True), "local"

        try:
            payload = {
                "model": self.model,
                "messages": self._messages(user_text),
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }
            response = requests.post(
                self._endpoint(),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            content = data["choices"][0]["message"]["content"]
            if not str(content).strip():
                print("[Daniya] API returned empty content; source=local")
                return self.local_reply(missing_key=False), "local"
            print("[Daniya] API request succeeded; source=api")
            return str(content).strip(), "api"
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            print(f"[Daniya] API request failed: HTTP {status}; source=local")
        except requests.RequestException as exc:
            print(f"[Daniya] API request failed: network {exc.__class__.__name__}; source=local")
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            print(f"[Daniya] API response parse failed: {exc.__class__.__name__}; source=local")
        return self.local_reply(missing_key=False), "local"

    def local_reply(self, missing_key: bool = True) -> str:
        return self.no_key_fallback if missing_key else self.api_error_fallback

    def _messages(self, user_text: str) -> list[dict[str, str]]:
        system_content = f"{self.profile_manager.prompt_prefix()}\n\n角色设定：\n{self.system_prompt}".strip()
        messages = [{"role": "system", "content": system_content}]
        messages.extend(self.history_manager.recent_messages(self.context_limit))
        messages.append({"role": "user", "content": user_text})
        return messages

    def _endpoint(self) -> str:
        return self.base_url.rstrip("/") + "/chat/completions"

    def _has_api_key(self) -> bool:
        return bool(self.api_key) and self.api_key != "your_api_key_here"


def mask_key(api_key: str) -> str:
    if not api_key:
        return "<empty>"
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}****{api_key[-4:]}"

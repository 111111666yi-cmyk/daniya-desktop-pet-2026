from __future__ import annotations

from typing import Any

from core.speech_filter import sanitize_user_addressing

from .config_manager import ConfigManager
from .history_manager import HistoryManager
from .profile_manager import ProfileManager
from .llm.provider_manager import ProviderManager


class ChatClient:
    """
    为了向下兼容 v0.415，ChatClient 现在作为一个适配器。
    它封装了底层的 ProviderManager。
    """
    
    def __init__(
        self,
        config_manager: ConfigManager,
        history_manager: HistoryManager,
        profile_manager: ProfileManager,
    ) -> None:
        self.config_manager = config_manager
        self.history_manager = history_manager
        self.profile_manager = profile_manager
        self.provider_manager = None
        self.reload()

    def reload(self) -> None:
        """从配置文件重新加载参数和 Provider"""
        self.app_config = self.config_manager.load_app_config()
        self.system_prompt = self.config_manager.load_system_prompt()
        from .settings_manager import SettingsManager
        settings_mgr = SettingsManager(self.config_manager)
        api_config = settings_mgr.load_api_config()
        
        # 兼容旧配置：合并根节点的聊天配置到 api_config 内
        chat_config = self.app_config.get("chat", {})
        if "chat" not in api_config:
            api_config["chat"] = chat_config
            
        self.context_limit = int(chat_config.get("context_limit", 8))
        self.local_mode = bool(api_config.get("local_mode", False))
        
        self.provider_manager = ProviderManager(
            api_config=api_config,
            system_prompt=self.system_prompt,
            prompt_prefix=self.profile_manager.prompt_prefix()
        )

    def reply(self, user_text: str) -> tuple[str, str]:
        """
        处理聊天请求。
        注意：在 v0.415 的新架构中，user_text 实际上是 PromptBuilder 生成的完整 prompt 字符串。
        """
        if self.local_mode:
            print("[Daniya] Chat response: provider=none, model=none, source=local, fallback_used=True, error_summary=\"local_mode_enabled\"")
            return sanitize_user_addressing(self.local_reply(missing_key=True)), "local"
            
        if not self.provider_manager:
            print("[Daniya] Chat response: provider=none, model=none, source=local, fallback_used=True, error_summary=\"provider_manager_missing\"")
            return sanitize_user_addressing(self.local_reply(missing_key=True)), "local"
            
        # 兼容旧代码：由于 DialogueEngine 的适配器只传了单个 prompt 字符串，
        # 我们用 history_manager 获取额外的历史记录（如果 DialogueEngine 自己没有做的话）
        # 不过在 v0.415，DialogueEngine 的 Prompt 已经包含了所有历史和状态。
        # 此处的 _messages 组装主要为了兼容可能没有过 PromptBuilder 的纯文本 fallback
        messages = self.provider_manager.prompt_to_messages(
            prompt=user_text,
            history_messages=self.history_manager.recent_messages(self.context_limit)
        )
        
        reply, source = self.provider_manager.chat(messages)
        return sanitize_user_addressing(reply), source

    def local_reply(self, missing_key: bool = True) -> str:
        """返回本地回退回复"""
        if self.provider_manager:
            return sanitize_user_addressing(self.provider_manager.local_fallback(api_error=not missing_key))
        return sanitize_user_addressing("达妮娅刚刚走神了一下……但我还在哦。")


def mask_key(api_key: str) -> str:
    if not api_key:
        return "<empty>"
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}****{api_key[-4:]}"

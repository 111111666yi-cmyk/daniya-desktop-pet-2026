import json
from pathlib import Path
from typing import Any

from .utils import ensure_dir, runtime_root


DEFAULT_CAPABILITIES = {
    "llm_providers": [
        "deepseek",
        "openai_compatible",
        "openai",
        "claude",
        "local_openai_compatible",
        "local_fallback"
    ],
    "tts_providers": [
        "cloud_tts",
        "local_tts",
        "none"
    ],
    "image_providers": [
        "text_to_image",
        "image_to_image",
        "none"
    ],
    "video_providers": [
        "image_to_video",
        "text_to_video",
        "none"
    ],
    "local_model_providers": [
        "ollama",
        "lm_studio",
        "llama_cpp_server",
        "openai_compatible_local",
        "gemma_local_placeholder",
        "custom_local"
    ]
}


class ProviderCapabilitySchema:
    """
    负责提供多模态能力配置的基础字典和选项。
    由于本阶段只做 UI 预留和入口占位，因此这些数据只作为静态配置提供给设置中心和新手向导。
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or runtime_root()
        self.config_dir = ensure_dir(self.root / "config")
        self.capabilities_file = self.config_dir / "provider_capabilities.json"
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.capabilities_file.exists():
            self._save(DEFAULT_CAPABILITIES)

    def _save(self, data: dict[str, list[str]]) -> None:
        tmp = self.capabilities_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.capabilities_file)

    def load_schema(self) -> dict[str, list[str]]:
        """获取全量的 capability schema"""
        try:
            return json.loads(self.capabilities_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return DEFAULT_CAPABILITIES

    def get_llm_providers(self) -> list[str]:
        return self.load_schema().get("llm_providers", DEFAULT_CAPABILITIES["llm_providers"])

    def get_tts_providers(self) -> list[str]:
        return self.load_schema().get("tts_providers", DEFAULT_CAPABILITIES["tts_providers"])

    def get_image_providers(self) -> list[str]:
        return self.load_schema().get("image_providers", DEFAULT_CAPABILITIES["image_providers"])

    def get_video_providers(self) -> list[str]:
        return self.load_schema().get("video_providers", DEFAULT_CAPABILITIES["video_providers"])

    def get_local_model_providers(self) -> list[str]:
        return self.load_schema().get("local_model_providers", DEFAULT_CAPABILITIES["local_model_providers"])

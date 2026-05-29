import json
from pathlib import Path
from typing import Any

from .utils import ensure_dir, runtime_root


DEFAULT_CATALOG = {
    "recommended_models": [
        {
            "id": "qwen2.5-7b",
            "name": "Qwen 2.5 7B Instruct",
            "provider": "ollama",
            "tags": ["recommended", "fast", "multilingual"]
        },
        {
            "id": "llama-3-8b",
            "name": "Llama 3 8B Instruct",
            "provider": "lm_studio",
            "tags": ["powerful", "english"]
        },
        {
            "id": "gemma-2-9b",
            "name": "Gemma 2 9B It",
            "provider": "llama.cpp",
            "tags": ["balanced", "google"]
        }
    ],
    "license_accepted": False
}


class ModelCatalog:
    """
    负责管理本地模型花名册及许可证状态 (v0.46 / v0.47 预留)。
    解析读取 config/local_model_config.json。
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or runtime_root()
        self.config_dir = ensure_dir(self.root / "config")
        self.config_file = self.config_dir / "local_model_config.json"
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.config_file.exists():
            self._save(DEFAULT_CATALOG)

    def _save(self, data: dict[str, Any]) -> None:
        tmp = self.config_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.config_file)

    def load_config(self) -> dict[str, Any]:
        try:
            return json.loads(self.config_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return DEFAULT_CATALOG

    def is_license_accepted(self) -> bool:
        return self.load_config().get("license_accepted", False)

    def accept_license(self) -> None:
        cfg = self.load_config()
        cfg["license_accepted"] = True
        self._save(cfg)

    def get_recommended_models(self) -> list[dict[str, Any]]:
        return self.load_config().get("recommended_models", [])

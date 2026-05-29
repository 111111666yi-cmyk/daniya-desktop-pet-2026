import json
from pathlib import Path
from typing import Any

from src.utils import runtime_root


class ModelCatalog:
    """
    模型目录类，负责加载和查询推荐的本地大语言模型。
    该目录与模型权重本身分离，不内置权重，仅提供指向官方地址、许可证、Ollama 下载名及硬件配置推荐的元数据。
    """
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or runtime_root()
        self.catalog_path = self.root / "config" / "model_catalog.json"
        self.catalog_data = self.load_catalog()

    def load_catalog(self) -> dict[str, Any]:
        if self.catalog_path.exists():
            try:
                with open(self.catalog_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        # 兜底
        return {"recommended_models": []}

    def get_recommended_models(self) -> list[dict[str, Any]]:
        return self.catalog_data.get("recommended_models", [])

    def get_model_by_id(self, model_id: str) -> dict[str, Any] | None:
        for m in self.get_recommended_models():
            if m.get("id") == model_id:
                return m
        return None

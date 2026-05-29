import json
from pathlib import Path
from typing import Any

from .utils import ensure_dir, runtime_root


class SetupStateManager:
    """
    负责管理首次启动 (First Run) 状态。
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or runtime_root()
        self.config_dir = ensure_dir(self.root / "config")
        self.setup_config_path = self.config_dir / "setup_config.json"

    def load_setup_config(self) -> dict[str, Any]:
        """读取当前的 setup_config.json，如果不存在则返回默认空字典。"""
        if not self.setup_config_path.exists():
            return {}
        try:
            return json.loads(self.setup_config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def save_setup_config(self, config: dict[str, Any]) -> None:
        """保存配置到 setup_config.json。"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.setup_config_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.setup_config_path)

    def is_first_run_complete(self) -> bool:
        """判断用户是否已经完成了首次启动向导。"""
        config = self.load_setup_config()
        return bool(config.get("first_run_setup", False))

    def mark_first_run_complete(self, run_mode: str, multimodal_enabled: dict[str, bool]) -> None:
        """
        保存完成状态，并记录用户的选择。
        :param run_mode: 运行模式，例如 api_cloud, local_model, local_fallback 等
        :param multimodal_enabled: 启用的多模态能力，例如 {"tts": True, "image": False}
        """
        config = self.load_setup_config()
        config["first_run_setup"] = True
        config["run_mode"] = run_mode
        config["multimodal_enabled"] = multimodal_enabled
        self.save_setup_config(config)

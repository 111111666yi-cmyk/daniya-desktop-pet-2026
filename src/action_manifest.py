import json
import logging
from pathlib import Path
from typing import Any

from .utils import resource_path

logger = logging.getLogger(__name__)

DEFAULT_MANIFEST: dict[str, Any] = {
    "actions": {
        "idle": {"frames": ["normal1.png"], "loop": True, "duration_ms": 700, "fallback": ["normal1.png"]},
        "talk": {"frames": ["normal1.png", "normal2.png"], "loop": True, "duration_ms": 180, "fallback": ["normal1.png", "normal2.png"]},
        "clicked": {"frames": ["normal2.png"], "loop": False, "duration_ms": 250, "fallback": ["normal2.png", "normal1.png"]},
        "drag": {"frames": ["normal2.png"], "loop": True, "duration_ms": 250, "fallback": ["normal2.png", "normal1.png"]},
        "sleep": {"frames": ["normal1.png"], "loop": True, "duration_ms": 900, "fallback": ["normal1.png"]},
        "happy": {"frames": ["normal2.png"], "loop": False, "duration_ms": 350, "fallback": ["normal2.png", "normal1.png"]},
        "remind": {"frames": ["normal2.png"], "loop": False, "duration_ms": 350, "fallback": ["normal2.png", "normal1.png"]}
    }
}

class ActionManifest:
    def __init__(self) -> None:
        self.data = DEFAULT_MANIFEST.copy()
        self.base_dir = resource_path("assets", "placeholder")
        self.load_manifest()
        
    def load_manifest(self) -> None:
        private_path = resource_path("assets", "private", "manifest.json")
        placeholder_path = resource_path("assets", "placeholder", "manifest.json")
        
        target_path = None
        if private_path.exists():
            target_path = private_path
            self.base_dir = resource_path("assets", "private")
        elif placeholder_path.exists():
            target_path = placeholder_path
            self.base_dir = resource_path("assets", "placeholder")
            
        if target_path:
            try:
                content = json.loads(target_path.read_text(encoding="utf-8"))
                if "actions" in content:
                    self.data = content
            except Exception as e:
                logger.error(f"Failed to load manifest {target_path}: {e}")
                
        self.validate_manifest()

    def validate_manifest(self) -> None:
        if "actions" not in self.data:
            self.data["actions"] = DEFAULT_MANIFEST["actions"]
            
        for action_name, action_config in self.data["actions"].items():
            if "frames" not in action_config:
                action_config["frames"] = []
            if "fallback" not in action_config:
                action_config["fallback"] = ["normal1.png"]
            if "loop" not in action_config:
                action_config["loop"] = False
            if "duration_ms" not in action_config:
                action_config["duration_ms"] = 500

    def get_action_config(self, action_name: str) -> dict[str, Any] | None:
        return self.data.get("actions", {}).get(action_name)

    def _verify_frames(self, frames: list[str]) -> list[str]:
        valid_frames = []
        for frame in frames:
            if (self.base_dir / frame).exists():
                valid_frames.append(frame)
        return valid_frames

    def get_frames(self, action_name: str) -> list[str]:
        config = self.get_action_config(action_name)
        if not config:
            return []
        frames = config.get("frames", [])
        valid_frames = self._verify_frames(frames)
        if not valid_frames:
            return self.get_fallback_frames(action_name)
        return valid_frames

    def get_fallback_frames(self, action_name: str) -> list[str]:
        config = self.get_action_config(action_name)
        if not config:
            # Absolute fallback
            return ["normal1.png"]
        
        fallback_frames = config.get("fallback", ["normal1.png"])
        valid_frames = self._verify_frames(fallback_frames)
        if not valid_frames:
            return ["normal1.png"]
        return valid_frames

    def available_actions(self) -> list[str]:
        return list(self.data.get("actions", {}).keys())

    def resolve_action(self, action_name: str) -> str:
        if action_name in self.available_actions():
            return action_name
        return "idle"

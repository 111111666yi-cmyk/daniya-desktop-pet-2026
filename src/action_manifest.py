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
        "remind": {"frames": ["normal2.png"], "loop": False, "duration_ms": 350, "fallback": ["normal2.png", "normal1.png"]},
        "walking": {"frames": ["normal1.png", "normal2.png"], "loop": True, "duration_ms": 150, "fallback": ["normal1.png", "normal2.png"]},
        "edge_peek_left": {"frames": ["normal1.png"], "loop": True, "duration_ms": 500, "fallback": ["normal1.png"]},
        "edge_peek_right": {"frames": ["normal1.png"], "loop": True, "duration_ms": 500, "fallback": ["normal1.png"]},
        "taskbar_sit": {"frames": ["normal1.png"], "loop": True, "duration_ms": 700, "fallback": ["normal1.png"]}
    }
}

class ActionManifest:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.data = DEFAULT_MANIFEST.copy()
        if base_dir is not None and isinstance(base_dir, (Path, str)):
            self.base_dir = Path(base_dir)
        else:
            self.base_dir = resource_path("assets", "placeholder")
        self.load_manifest(self.base_dir)

    def load_manifest(self, base_dir: Path | None = None) -> None:
        if base_dir is not None and isinstance(base_dir, (Path, str)):
            self.base_dir = Path(base_dir)

        content = None
        # 1. Try to load from active base_dir
        manifest_path = self.base_dir / "manifest.json"
        if manifest_path.exists():
            try:
                content = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.error(f"Failed to load manifest {manifest_path}: {e}")

        # 2. Try template manifest
        if not content or "actions" not in content:
            from .utils import runtime_root, bundled_root
            template_assets = runtime_root() / "characters" / "template" / "assets"
            if not template_assets.exists():
                template_assets = bundled_root() / "characters" / "template" / "assets"
            template_manifest = template_assets / "manifest.json"
            if template_manifest.exists():
                try:
                    content = json.loads(template_manifest.read_text(encoding="utf-8"))
                except Exception as e:
                    logger.error(f"Failed to load template manifest: {e}")

        # 3. Use default manifest if all else fails
        if content and "actions" in content:
            self.data = content
        else:
            self.data = DEFAULT_MANIFEST.copy()

        self.validate_manifest()

    def validate_manifest(self) -> None:
        if "actions" not in self.data or not isinstance(self.data["actions"], dict):
            self.data["actions"] = {}

        for action_name, default_config in DEFAULT_MANIFEST["actions"].items():
            if action_name not in self.data["actions"]:
                self.data["actions"][action_name] = default_config.copy()

        for action_name, action_config in self.data["actions"].items():
            if not isinstance(action_config, dict):
                continue
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

    def _find_fallback_image(self, frame: str) -> Path:
        from .utils import runtime_root, bundled_root
        template_assets = runtime_root() / "characters" / "template" / "assets"
        if not template_assets.exists():
            template_assets = bundled_root() / "characters" / "template" / "assets"

        placeholder_dir = runtime_root() / "assets" / "placeholder"
        if not placeholder_dir.exists():
            placeholder_dir = bundled_root() / "assets" / "placeholder"

        is_normal2 = "normal2" in frame or any(k in frame.lower() for k in ("clicked", "drag", "happy", "remind", "talk", "speaking"))
        fallback_name = "normal2.png" if is_normal2 else "normal1.png"

        # 1. base_dir / frame
        p = self.base_dir / frame
        if p.exists():
            return p

        # 2. template_assets / frame
        p = template_assets / frame
        if p.exists():
            return p

        # 3. template_assets / fallback_name
        p = template_assets / fallback_name
        if p.exists():
            return p

        # 4. placeholder_dir / frame
        p = placeholder_dir / frame
        if p.exists():
            return p

        # 5. placeholder_dir / fallback_name
        p = placeholder_dir / fallback_name
        if p.exists():
            return p

        # 6. placeholder_dir / "normal1.png"
        p = placeholder_dir / "normal1.png"
        if p.exists():
            return p

        return self.base_dir / frame

    def _verify_frames(self, frames: list[str]) -> list[str]:
        valid_frames = []
        for frame in frames:
            resolved = self._find_fallback_image(frame)
            if resolved.exists():
                valid_frames.append(str(resolved))
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
            placeholder = resource_path("assets", "placeholder", "normal1.png")
            return [str(placeholder)]

        fallback_frames = config.get("fallback", ["normal1.png"])
        valid_frames = self._verify_frames(fallback_frames)
        if not valid_frames:
            placeholder = resource_path("assets", "placeholder", "normal1.png")
            return [str(placeholder)]
        return valid_frames

    def available_actions(self) -> list[str]:
        return list(self.data.get("actions", {}).keys())

    def resolve_action(self, action_name: str) -> str:
        if action_name in self.available_actions():
            return action_name
        return "idle"

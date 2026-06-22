from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_ANCHOR_VALUES = {
    "root": [0.5, 0.88],
    "foot_left": [0.42, 0.98],
    "foot_right": [0.58, 0.98],
    "hips": [0.5, 0.66],
    "drag_handle": [0.5, 0.18],
}

DEFAULT_STATE_SPECS: dict[str, dict[str, Any]] = {
    "idle": {"clip": "idle_breath_loop", "loop": True, "min_hold_ms": 400, "priority": 10},
    "talk": {"clip": "talk_loop", "loop": True, "min_hold_ms": 250, "priority": 20},
    "talking": {"clip": "talk_loop", "loop": True, "min_hold_ms": 250, "priority": 20},
    "clicked": {"clip": "clicked_react", "loop": False, "min_hold_ms": 120, "priority": 40},
    "happy": {"clip": "happy_loop", "loop": False, "min_hold_ms": 180, "priority": 35},
    "thinking": {"clip": "thinking_loop", "loop": True, "min_hold_ms": 350, "priority": 20},
    "sleep": {"clip": "sleep_loop", "loop": True, "min_hold_ms": 900, "priority": 15},
    "sleeping": {"clip": "sleep_loop", "loop": True, "min_hold_ms": 900, "priority": 15},
    "walk_start": {"clip": "walk_start", "loop": False, "min_hold_ms": 0, "priority": 30},
    "walking": {"clip": "walk_loop", "loop": True, "min_hold_ms": 0, "priority": 30},
    "walk_stop": {"clip": "walk_stop", "loop": False, "min_hold_ms": 0, "priority": 30},
    "drag_pickup": {"clip": "drag_pickup", "loop": False, "min_hold_ms": 0, "priority": 80},
    "drag_hold": {"clip": "drag_hold_loop", "loop": True, "min_hold_ms": 0, "priority": 80},
    "drag_drop": {"clip": "drag_drop", "loop": False, "min_hold_ms": 0, "priority": 80},
    "dragging": {"clip": "drag_hold_loop", "loop": True, "min_hold_ms": 0, "priority": 80},
    "edge_peek_left": {"clip": "edge_peek_left", "loop": True, "min_hold_ms": 300, "priority": 25},
    "edge_peek_right": {"clip": "edge_peek_right", "loop": True, "min_hold_ms": 300, "priority": 25},
    "taskbar_sit": {"clip": "taskbar_sit_loop", "loop": True, "min_hold_ms": 700, "priority": 18},
    "remind": {"clip": "remind_loop", "loop": False, "min_hold_ms": 180, "priority": 32},
    "hover": {"clip": "idle_breath_loop", "loop": True, "min_hold_ms": 250, "priority": 12},
}

STATE_ALIASES: dict[str, tuple[str, ...]] = {
    "talk": ("talk", "talking", "speaking"),
    "talking": ("talking", "talk", "speaking"),
    "speaking": ("speaking", "talking", "talk"),
    "sleep": ("sleep", "sleeping"),
    "sleeping": ("sleeping", "sleep"),
    "drag_pickup": ("drag_pickup", "pickup", "drag"),
    "drag_hold": ("drag_hold", "dragging", "drag"),
    "drag_drop": ("drag_drop", "drop", "dragging"),
    "dragging": ("dragging", "drag_hold", "drag"),
}


@dataclass(frozen=True)
class AnchorTrack:
    root: tuple[float, float] = (0.5, 0.88)
    foot_left: tuple[float, float] = (0.42, 0.98)
    foot_right: tuple[float, float] = (0.58, 0.98)
    hips: tuple[float, float] = (0.5, 0.66)
    drag_handle: tuple[float, float] = (0.5, 0.18)

    @classmethod
    def from_data(cls, data: dict[str, Any] | None) -> "AnchorTrack":
        if not isinstance(data, dict):
            return cls()

        def _pair(name: str) -> tuple[float, float]:
            raw = data.get(name, DEFAULT_ANCHOR_VALUES[name])
            if isinstance(raw, (list, tuple)) and len(raw) == 2:
                try:
                    return float(raw[0]), float(raw[1])
                except (TypeError, ValueError):
                    return tuple(DEFAULT_ANCHOR_VALUES[name])  # type: ignore[return-value]
            return tuple(DEFAULT_ANCHOR_VALUES[name])  # type: ignore[return-value]

        return cls(
            root=_pair("root"),
            foot_left=_pair("foot_left"),
            foot_right=_pair("foot_right"),
            hips=_pair("hips"),
            drag_handle=_pair("drag_handle"),
        )


@dataclass(frozen=True)
class RendererBinding:
    sprite_clip: str | None = None
    live2d_model: str | None = None
    live2d_motion_group: str | None = None
    live2d_expression: str | None = None
    fallback_state: str | None = None

    @classmethod
    def from_data(cls, data: dict[str, Any] | None, *, sprite_clip: str | None = None) -> "RendererBinding":
        if not isinstance(data, dict):
            return cls(sprite_clip=sprite_clip)
        return cls(
            sprite_clip=str(data.get("sprite_clip", sprite_clip or "")) or sprite_clip,
            live2d_model=str(data.get("live2d_model", "")) or None,
            live2d_motion_group=str(data.get("live2d_motion_group", "")) or None,
            live2d_expression=str(data.get("live2d_expression", "")) or None,
            fallback_state=str(data.get("fallback_state", "")) or None,
        )


@dataclass(frozen=True)
class LocomotionProfile:
    cycle_distance_px: float = 64.0
    min_speed_px_per_s: float = 48.0
    default_speed_px_per_s: float = 72.0
    max_speed_px_per_s: float = 96.0
    start_distance_px: float = 18.0
    stop_distance_px: float = 18.0

    @classmethod
    def from_data(cls, data: dict[str, Any] | None) -> "LocomotionProfile":
        if not isinstance(data, dict):
            return cls()

        def _value(name: str, fallback: float) -> float:
            try:
                return float(data.get(name, fallback))
            except (TypeError, ValueError):
                return fallback

        return cls(
            cycle_distance_px=_value("cycle_distance_px", 64.0),
            min_speed_px_per_s=_value("min_speed_px_per_s", 48.0),
            default_speed_px_per_s=_value("default_speed_px_per_s", 72.0),
            max_speed_px_per_s=_value("max_speed_px_per_s", 96.0),
            start_distance_px=_value("start_distance_px", 18.0),
            stop_distance_px=_value("stop_distance_px", 18.0),
        )


@dataclass(frozen=True)
class MotionClipSpec:
    clip_id: str
    kind: str
    frames: tuple[str, ...]
    frame_duration_ms: int
    loop: bool
    anchor_track: AnchorTrack = field(default_factory=AnchorTrack)
    transition_in: tuple[str, ...] = ()
    transition_out: tuple[str, ...] = ()
    locomotion_profile: LocomotionProfile | None = None


@dataclass(frozen=True)
class MotionStateSpec:
    state_id: str
    clip: str
    loop: bool
    min_hold_ms: int
    priority: int
    interrupts: tuple[str, ...] = ()
    fallback_state: str = "idle"
    renderer_binding: RendererBinding = field(default_factory=RendererBinding)


@dataclass(frozen=True)
class MotionCatalog:
    base_dir: Path
    states: dict[str, MotionStateSpec]
    clips: dict[str, MotionClipSpec]
    bindings: dict[str, dict[str, Any]]

    def state_spec(self, state_name: str) -> MotionStateSpec | None:
        state = self._normalise_state(state_name)
        if state in self.states:
            return self.states[state]
        return self.states.get("idle")

    def clip_spec(self, clip_id: str) -> MotionClipSpec | None:
        return self.clips.get(clip_id)

    def clip_for_state(self, state_name: str) -> MotionClipSpec | None:
        spec = self.state_spec(state_name)
        if spec is None:
            return None
        return self.clip_spec(spec.clip)

    def frames_for_state(self, state_name: str) -> list[str]:
        clip = self.clip_for_state(state_name)
        if clip is None:
            return []
        return list(clip.frames)

    def action_config(self, state_name: str) -> dict[str, Any] | None:
        spec = self.state_spec(state_name)
        clip = self.clip_for_state(state_name)
        if spec is None or clip is None:
            return None
        config = {
            "frames": list(clip.frames),
            "loop": spec.loop if spec.clip != "walk_loop" else True,
            "duration_ms": clip.frame_duration_ms,
            "fallback": list(clip.frames) if clip.frames else ["normal1.png"],
            "transition_in": list(clip.transition_in),
            "transition_out": list(clip.transition_out),
            "min_hold_ms": spec.min_hold_ms,
            "priority": spec.priority,
            "interrupts": list(spec.interrupts),
            "fallback_state": spec.fallback_state,
            "renderer_binding": {
                "sprite_clip": spec.renderer_binding.sprite_clip,
                "live2d_model": spec.renderer_binding.live2d_model,
                "live2d_motion_group": spec.renderer_binding.live2d_motion_group,
                "live2d_expression": spec.renderer_binding.live2d_expression,
                "fallback_state": spec.renderer_binding.fallback_state,
            },
        }
        if clip.locomotion_profile is not None:
            config["locomotion_profile"] = {
                "cycle_distance_px": clip.locomotion_profile.cycle_distance_px,
                "min_speed_px_per_s": clip.locomotion_profile.min_speed_px_per_s,
                "default_speed_px_per_s": clip.locomotion_profile.default_speed_px_per_s,
                "max_speed_px_per_s": clip.locomotion_profile.max_speed_px_per_s,
                "start_distance_px": clip.locomotion_profile.start_distance_px,
                "stop_distance_px": clip.locomotion_profile.stop_distance_px,
            }
        return config

    def available_states(self) -> list[str]:
        return list(self.states.keys())

    def _normalise_state(self, state_name: str) -> str:
        if state_name in self.states:
            return state_name
        for canonical, aliases in STATE_ALIASES.items():
            if state_name == canonical or state_name in aliases:
                return canonical
        return state_name


def build_motion_catalog(base_dir: Path, data: dict[str, Any] | None) -> MotionCatalog:
    payload = data if isinstance(data, dict) else {}
    motion_data = payload.get("motion_catalog")
    bindings = _load_live2d_bindings(base_dir)
    if isinstance(motion_data, dict):
        return _catalog_from_motion_data(base_dir, motion_data, bindings)
    return _catalog_from_legacy_data(base_dir, payload, bindings)


def _catalog_from_motion_data(base_dir: Path, data: dict[str, Any], bindings: dict[str, dict[str, Any]]) -> MotionCatalog:
    raw_clips = data.get("clips", {})
    raw_states = data.get("states", {})
    clips: dict[str, MotionClipSpec] = {}
    states: dict[str, MotionStateSpec] = {}

    if isinstance(raw_clips, dict):
        for clip_id, raw_clip in raw_clips.items():
            if not isinstance(raw_clip, dict):
                continue
            frames = tuple(str(item) for item in raw_clip.get("frames", []) if str(item).strip())
            locomotion = LocomotionProfile.from_data(raw_clip.get("locomotion_profile")) if "locomotion_profile" in raw_clip else None
            try:
                frame_duration_ms = int(raw_clip.get("frame_duration_ms", 120))
            except (TypeError, ValueError):
                frame_duration_ms = 120
            clips[clip_id] = MotionClipSpec(
                clip_id=clip_id,
                kind=str(raw_clip.get("kind", "sprite_sequence")),
                frames=frames,
                frame_duration_ms=max(16, frame_duration_ms),
                loop=bool(raw_clip.get("loop", clip_id.endswith("_loop") or clip_id in {"walk_loop"})),
                anchor_track=AnchorTrack.from_data(raw_clip.get("anchor_track")),
                transition_in=tuple(str(item) for item in raw_clip.get("transition_in", []) if str(item).strip()),
                transition_out=tuple(str(item) for item in raw_clip.get("transition_out", []) if str(item).strip()),
                locomotion_profile=locomotion,
            )

    if isinstance(raw_states, dict):
        for state_id, raw_state in raw_states.items():
            if not isinstance(raw_state, dict):
                continue
            clip_id = str(raw_state.get("clip", "")).strip()
            if not clip_id:
                continue
            try:
                min_hold_ms = int(raw_state.get("min_hold_ms", 0))
            except (TypeError, ValueError):
                min_hold_ms = 0
            try:
                priority = int(raw_state.get("priority", 10))
            except (TypeError, ValueError):
                priority = 10
            state_binding = _merge_binding(bindings.get(state_id), raw_state.get("renderer_binding"), clip_id)
            states[state_id] = MotionStateSpec(
                state_id=state_id,
                clip=clip_id,
                loop=bool(raw_state.get("loop", clips.get(clip_id).loop if clip_id in clips else False)),
                min_hold_ms=max(0, min_hold_ms),
                priority=priority,
                interrupts=tuple(str(item) for item in raw_state.get("interrupts", []) if str(item).strip()),
                fallback_state=str(raw_state.get("fallback_state", "idle") or "idle"),
                renderer_binding=state_binding,
            )

    if "idle" not in states:
        return _catalog_from_legacy_data(base_dir, data, bindings)
    return MotionCatalog(base_dir=base_dir, states=states, clips=clips, bindings=bindings)


def _catalog_from_legacy_data(base_dir: Path, data: dict[str, Any], bindings: dict[str, dict[str, Any]]) -> MotionCatalog:
    animations = data.get("animations", {})
    actions = data.get("actions", {})
    animation_groups = data.get("animation_groups", {})

    def _legacy_frames(name: str) -> list[str]:
        for key in STATE_ALIASES.get(name, (name,)):
            group_frames = _frames_from_group(animation_groups, key)
            if group_frames:
                return group_frames
            if isinstance(animations, dict):
                raw = animations.get(key)
                if isinstance(raw, list):
                    vals = [str(item) for item in raw if str(item).strip()]
                    if vals:
                        return vals
                if isinstance(raw, str) and raw.strip():
                    return [raw]
            if isinstance(actions, dict):
                raw_action = actions.get(key)
                if isinstance(raw_action, dict):
                    frames = raw_action.get("frames", [])
                    if isinstance(frames, list):
                        vals = [str(item) for item in frames if str(item).strip()]
                        if vals:
                            return vals
        return []

    base_idle = _legacy_frames("idle") or ["normal1.png"]
    talk_frames = _expand_frames(_legacy_frames("talk") or ["normal1.png", "normal2.png"], 24)
    thinking_frames = _expand_frames(_legacy_frames("thinking") or _legacy_frames("talk") or ["normal1.png", "normal2.png"], 24)
    walk_source = _legacy_frames("walking") or ["normal1.png", "normal2.png"]
    walk_loop = _expand_frames(walk_source, 24)
    stand_frame = (_legacy_frames("taskbar_sit") or base_idle[:1] or ["normal1.png"])[0]
    walk_start = _make_walk_start(stand_frame, walk_loop, 10)
    walk_stop = _make_walk_stop(stand_frame, walk_loop, 8)
    drag_pickup = _expand_frames(_legacy_frames("drag_pickup") or _legacy_frames("drag") or ["normal2.png"], 24)
    drag_hold = _expand_frames(_legacy_frames("drag_hold") or _legacy_frames("dragging") or _legacy_frames("drag") or ["normal2.png"], 24)
    drag_drop = _expand_frames(_legacy_frames("drag_drop") or _legacy_frames("drag") or ["normal2.png"], 24)
    idle_loop = _expand_frames(base_idle, 24)
    sleep_loop = _expand_frames(_legacy_frames("sleep") or ["normal1.png"], 24)
    clicked_react = _expand_frames(_legacy_frames("clicked") or ["normal2.png"], 24)
    happy_loop = _expand_frames(_legacy_frames("happy") or ["normal2.png"], 24)
    remind_loop = _expand_frames(_legacy_frames("remind") or _legacy_frames("happy") or ["normal2.png"], 24)
    edge_left = _expand_frames(_legacy_frames("edge_peek_left") or base_idle[:1] or ["normal1.png"], 24)
    edge_right = _expand_frames(_legacy_frames("edge_peek_right") or base_idle[:1] or ["normal1.png"], 24)
    taskbar = _expand_frames(_legacy_frames("taskbar_sit") or base_idle[:1] or ["normal1.png"], 24)

    clips = {
        "idle_breath_loop": _clip("idle_breath_loop", idle_loop, 41, True),
        "talk_loop": _clip("talk_loop", talk_frames, 41, True),
        "thinking_loop": _clip("thinking_loop", thinking_frames, 41, True),
        "clicked_react": _clip("clicked_react", clicked_react, 41, False),
        "happy_loop": _clip("happy_loop", happy_loop, 41, False),
        "remind_loop": _clip("remind_loop", remind_loop, 41, False),
        "sleep_loop": _clip("sleep_loop", sleep_loop, 41, True),
        "walk_start": _clip("walk_start", walk_start, 41, False),
        "walk_loop": _clip("walk_loop", walk_loop, 41, True, locomotion=LocomotionProfile()),
        "walk_stop": _clip("walk_stop", walk_stop, 41, False),
        "drag_pickup": _clip("drag_pickup", drag_pickup, 41, False, anchor=AnchorTrack.from_data({"drag_handle": [0.5, 0.18]})),
        "drag_hold_loop": _clip("drag_hold_loop", drag_hold, 41, True, anchor=AnchorTrack.from_data({"drag_handle": [0.5, 0.18]})),
        "drag_drop": _clip("drag_drop", drag_drop, 41, False, anchor=AnchorTrack.from_data({"drag_handle": [0.5, 0.18]})),
        "edge_peek_left": _clip("edge_peek_left", edge_left, 41, True),
        "edge_peek_right": _clip("edge_peek_right", edge_right, 41, True),
        "taskbar_sit_loop": _clip("taskbar_sit_loop", taskbar, 41, True),
    }

    states: dict[str, MotionStateSpec] = {}
    for state_id, defaults in DEFAULT_STATE_SPECS.items():
        clip_id = defaults["clip"]
        state_binding = _merge_binding(bindings.get(state_id), None, clip_id)
        states[state_id] = MotionStateSpec(
            state_id=state_id,
            clip=clip_id,
            loop=bool(defaults["loop"]),
            min_hold_ms=int(defaults["min_hold_ms"]),
            priority=int(defaults["priority"]),
            interrupts=(),
            fallback_state="idle",
            renderer_binding=state_binding,
        )

    return MotionCatalog(base_dir=base_dir, states=states, clips=clips, bindings=bindings)


def _clip(
    clip_id: str,
    frames: list[str],
    frame_duration_ms: int,
    loop: bool,
    *,
    anchor: AnchorTrack | None = None,
    locomotion: LocomotionProfile | None = None,
) -> MotionClipSpec:
    return MotionClipSpec(
        clip_id=clip_id,
        kind="sprite_sequence",
        frames=tuple(frames),
        frame_duration_ms=frame_duration_ms,
        loop=loop,
        anchor_track=anchor or AnchorTrack(),
        transition_in=(),
        transition_out=(),
        locomotion_profile=locomotion,
    )


def _frames_from_group(groups: Any, key: str) -> list[str]:
    if not isinstance(groups, dict):
        return []
    candidates = groups.get(key)
    if not isinstance(candidates, list):
        return []
    for item in candidates:
        if not isinstance(item, dict) or item.get("enabled", True) is False:
            continue
        raw = item.get("frames", [])
        if isinstance(raw, list):
            vals = [str(entry) for entry in raw if str(entry).strip()]
            if vals:
                return vals
        elif isinstance(raw, str) and raw.strip():
            return [raw]
    return []


def _expand_frames(frames: list[str], target_count: int) -> list[str]:
    usable = [frame for frame in frames if frame]
    if not usable:
        usable = ["normal1.png"]
    if len(usable) >= target_count:
        return usable[:target_count]
    out: list[str] = []
    for idx in range(target_count):
        src_index = int(idx * len(usable) / target_count)
        out.append(usable[min(src_index, len(usable) - 1)])
    return out


def _make_walk_start(stand_frame: str, walk_frames: list[str], target_count: int) -> list[str]:
    frames = [stand_frame, stand_frame]
    frames.extend(walk_frames[: max(0, target_count - len(frames))])
    return _expand_frames(frames, target_count)


def _make_walk_stop(stand_frame: str, walk_frames: list[str], target_count: int) -> list[str]:
    tail = list(reversed(walk_frames[-max(1, target_count - 2):]))
    frames = tail + [stand_frame, stand_frame]
    return _expand_frames(frames, target_count)


def _merge_binding(
    file_binding: dict[str, Any] | None,
    inline_binding: dict[str, Any] | None,
    clip_id: str,
) -> RendererBinding:
    merged: dict[str, Any] = {}
    if isinstance(file_binding, dict):
        merged.update(file_binding)
    if isinstance(inline_binding, dict):
        merged.update(inline_binding)
    return RendererBinding.from_data(merged, sprite_clip=clip_id)


def _load_live2d_bindings(base_dir: Path) -> dict[str, dict[str, Any]]:
    live2d_root = base_dir.parent / "live2d"
    if not live2d_root.exists():
        return {}
    for model_dir in sorted(path for path in live2d_root.iterdir() if path.is_dir()):
        binding_path = model_dir / "bindings.json"
        if binding_path.exists():
            try:
                import json

                payload = json.loads(binding_path.read_text(encoding="utf-8-sig"))
            except Exception:
                continue
            if isinstance(payload, dict):
                states = payload.get("states", {})
                if isinstance(states, dict):
                    return {
                        key: value
                        for key, value in states.items()
                        if isinstance(value, dict)
                    }
    return {}

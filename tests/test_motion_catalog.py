from __future__ import annotations

from pathlib import Path

from src.motion_catalog import LocomotionProfile, build_motion_catalog


def test_build_motion_catalog_from_legacy_animations_expands_walk_cycle(tmp_path: Path) -> None:
    payload = {
        "animations": {
            "idle": ["idle_a.png", "idle_b.png"],
            "walking": ["walk_01.png", "walk_02.png", "walk_03.png"],
            "drag_hold": ["drag_01.png", "drag_02.png"],
        }
    }

    catalog = build_motion_catalog(tmp_path, payload)

    walk_clip = catalog.clip_for_state("walking")
    assert walk_clip is not None
    assert len(walk_clip.frames) == 24
    assert walk_clip.locomotion_profile is not None
    assert walk_clip.locomotion_profile.cycle_distance_px == 64.0

    drag_clip = catalog.clip_for_state("drag_pickup")
    assert drag_clip is not None
    assert len(drag_clip.frames) == 24


def test_build_motion_catalog_from_legacy_animations_prefers_thinking_frames(tmp_path: Path) -> None:
    payload = {
        "animations": {
            "talk": ["talk_01.png", "talk_02.png"],
            "thinking": ["think_01.png", "think_02.png", "think_03.png"],
        }
    }

    catalog = build_motion_catalog(tmp_path, payload)

    thinking_clip = catalog.clip_for_state("thinking")
    assert thinking_clip is not None
    assert thinking_clip.clip_id == "thinking_loop"
    assert len(thinking_clip.frames) == 24
    assert set(thinking_clip.frames) == {"think_01.png", "think_02.png", "think_03.png"}


def test_build_motion_catalog_from_legacy_animations_uses_dedicated_remind_clip(tmp_path: Path) -> None:
    payload = {
        "animations": {
            "happy": ["happy_01.png", "happy_02.png"],
            "remind": ["remind_01.png", "remind_02.png"],
        }
    }

    catalog = build_motion_catalog(tmp_path, payload)

    remind_state = catalog.state_spec("remind")
    remind_clip = catalog.clip_for_state("remind")
    assert remind_state is not None
    assert remind_state.clip == "remind_loop"
    assert remind_clip is not None
    assert remind_clip.clip_id == "remind_loop"
    assert len(remind_clip.frames) == 24
    assert set(remind_clip.frames) == {"remind_01.png", "remind_02.png"}


def test_build_motion_catalog_from_explicit_motion_data_preserves_renderer_binding(tmp_path: Path) -> None:
    payload = {
        "motion_catalog": {
            "clips": {
                "idle_breath_loop": {
                    "kind": "sprite_sequence",
                    "frames": ["idle_01.png", "idle_02.png"],
                    "frame_duration_ms": 100,
                    "loop": True,
                }
            },
            "states": {
                "idle": {
                    "clip": "idle_breath_loop",
                    "loop": True,
                    "min_hold_ms": 400,
                    "priority": 10,
                    "renderer_binding": {
                        "live2d_model": "preview_model",
                        "live2d_motion_group": "idle",
                        "live2d_expression": "neutral",
                        "fallback_state": "idle",
                    },
                }
            },
        }
    }

    catalog = build_motion_catalog(tmp_path, payload)
    state = catalog.state_spec("idle")
    assert state is not None
    assert state.renderer_binding.live2d_model == "preview_model"
    assert state.renderer_binding.live2d_motion_group == "idle"
    assert catalog.action_config("idle")["renderer_binding"]["fallback_state"] == "idle"

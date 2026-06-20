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
    assert len(drag_clip.frames) == 10


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

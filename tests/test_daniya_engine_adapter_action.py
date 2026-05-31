from src.daniya_engine_adapter import DaniyaEngineAdapter


class RecordingAnimationManager:
    def __init__(self, fail_actions=None):
        self.fail_actions = set(fail_actions or [])
        self.calls = []

    def set_state(self, action):
        self.calls.append(("set_state", action))
        if action in self.fail_actions:
            raise RuntimeError("missing action")


def test_adapter_returns_action_without_animation_manager():
    adapter = DaniyaEngineAdapter(model_client=lambda prompt: "哦。")
    result = adapter.handle_user_text("抱抱")
    assert result.action == "happy"
    assert result.fallback_chain[:3] == ["happy", "normal2", "idle"]


def test_adapter_dispatches_fallback_chain_to_animation_manager():
    manager = RecordingAnimationManager(fail_actions={"happy"})
    adapter = DaniyaEngineAdapter(model_client=lambda prompt: "哦。", animation_manager=manager)
    result = adapter.handle_user_text("抱抱")
    assert result.action == "happy"
    assert manager.calls[0] == ("set_state", "happy")
    assert manager.calls[1] == ("set_state", "normal2")


def test_adapter_physical_event_helper_routes_click():
    manager = RecordingAnimationManager()
    adapter = DaniyaEngineAdapter(model_client=lambda prompt: "哦。", animation_manager=manager)
    result = adapter.handle_physical_event("user_click")
    assert result.action == "clicked"
    assert ("set_state", "clicked") in manager.calls


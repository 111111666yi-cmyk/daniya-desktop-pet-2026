import random


class StateManager:
    """
    负责管理动作的生命周期与映射
    """

    STATE_TO_ACTION = {
        "idle": "idle",
        "talking": "talk",
        "thinking": "thinking",
        "clicked": "clicked",
        "dragging": "drag_hold",
        "drag_pickup": "drag_pickup",
        "drag_hold": "drag_hold",
        "drag_drop": "drag_drop",
        "sleeping": "sleep",
        "happy": "happy",
        "reminding": "remind",
        "walking": "walking",
        "walk_start": "walk_start",
        "walk_stop": "walk_stop",
        "edge_peek_left": "edge_peek_left",
        "edge_peek_right": "edge_peek_right",
        "taskbar_sit": "taskbar_sit",
    }

    V0415_FALLBACKS = {
        "soft_idle": "idle",
        "close_idle": "happy",
        "bubble": "happy",
        "look_away": "idle",
        "drag": "dragging",
        "talk": "talking",
        "sleep": "sleeping",
    }

    def __init__(self) -> None:
        self.current_state = "idle"

    def set_state(self, state: str) -> bool:
        """
        尝试设置新状态。如果被打断规则阻止，返回 False。
        """
        # 兼容 v0.415 扩展动作和简单的状态统一
        if state in self.V0415_FALLBACKS:
            state = self.V0415_FALLBACKS[state]

        # 降级不认识的状态到 idle
        if state not in self.STATE_TO_ACTION:
            state = "idle"

        if not self.can_interrupt(self.current_state, state):
            return False

        self.current_state = state
        return True

    def get_state(self) -> str:
        return self.current_state

    def state_to_action(self, state: str) -> str:
        return self.STATE_TO_ACTION.get(state, "idle")

    def return_to_idle(self) -> None:
        self.current_state = "idle"

    def can_interrupt(self, current_state: str, next_state: str) -> bool:
        # drag 能打断一切，除了 drag 自己
        if next_state in {"dragging", "drag_pickup", "drag_hold", "drag_drop"}:
            return True
        
        # 正在拖拽时，其他一切状态都不能打断，除了回到 idle
        if current_state in {"dragging", "drag_pickup", "drag_hold", "drag_drop"}:
            return next_state == "idle"

        # 如果正在说话，不允许普通动作打断，除非是更高级别交互（比如 clicked, happy）
        if current_state in {"talking", "thinking"}:
            if next_state in ["sleeping", "walking", "walk_start", "walk_stop", "edge_peek_left", "edge_peek_right", "taskbar_sit"]:
                return False
            return True

        # 如果处于 idle, sleeping 等，可以被任何动作打断
        return True

    def transition_weights(
        self,
        mood: str = "neutral",
        idle_seconds: float = 0,
        is_night: bool = False,
        intensity: str = "lively",
    ) -> dict[str, float]:
        w: dict[str, float] = {
            "idle": 0.35,
            "walking": 0.25,
            "sleep": 0.05,
            "bubble": 0.20,
            "happy": 0.05,
            "taskbar_sit": 0.10,
        }
        if intensity == "quiet":
            w["walking"] -= 0.10
            w["taskbar_sit"] = 0.0
            w["happy"] -= 0.03
            w["idle"] += 0.15
        elif intensity == "demo":
            w["walking"] += 0.10
            w["taskbar_sit"] += 0.10
            w["happy"] += 0.10
            w["idle"] -= 0.20
            w["bubble"] += 0.05
        if is_night:
            w["sleep"] += 0.50
            w["walking"] -= 0.15
            w["bubble"] -= 0.10
        if mood == "sleepy":
            w["sleep"] += 0.25
            w["walking"] -= 0.10
        elif mood == "happy":
            w["happy"] += 0.15
            w["walking"] += 0.10
            w["bubble"] += 0.10
        elif mood == "lonely":
            w["bubble"] += 0.20
            w["walking"] += 0.05
        elif mood == "focused":
            w["idle"] += 0.20
            w["walking"] -= 0.15
            w["bubble"] -= 0.15
        if idle_seconds > 600:
            w["sleep"] += 0.10
            w["bubble"] += 0.05
        return {k: max(0.0, v) for k, v in w.items()}

    def pick_idle_action(
        self,
        mood: str = "neutral",
        idle_seconds: float = 0,
        is_night: bool = False,
        intensity: str = "lively",
    ) -> str:
        weights = self.transition_weights(mood, idle_seconds, is_night, intensity)
        actions = list(weights.keys())
        values = list(weights.values())
        total = sum(values)
        if total <= 0:
            return "idle"
        pick = random.uniform(0, total)
        upto = 0.0
        for action, w in zip(actions, values):
            upto += w
            if pick <= upto:
                return action
        return "idle"

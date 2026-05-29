class StateManager:
    """
    负责管理动作的生命周期与映射
    """

    STATE_TO_ACTION = {
        "idle": "idle",
        "talking": "talk",
        "clicked": "clicked",
        "dragging": "drag",
        "sleeping": "sleep",
        "happy": "happy",
        "reminding": "remind",
        "walking": "walking",
        "edge_peek_left": "edge_peek_left",
        "edge_peek_right": "edge_peek_right",
    }

    V0415_FALLBACKS = {
        "soft_idle": "idle",
        "close_idle": "happy",
        "bubble": "happy",
        "look_away": "idle",
        "drag": "dragging",  # Route straight drag to dragging
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
        if next_state == "dragging":
            return True
        
        # 正在拖拽时，其他一切状态都不能打断，除了回到 idle
        if current_state == "dragging":
            return next_state == "idle"

        # 如果正在说话，不允许普通动作打断，除非是更高级别交互（比如 clicked, happy）
        if current_state == "talking":
            if next_state in ["sleeping", "walking", "edge_peek_left", "edge_peek_right"]:
                return False
            return True

        # 如果处于 idle, sleeping 等，可以被任何动作打断
        return True

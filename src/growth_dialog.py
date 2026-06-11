from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .growth_manager import GrowthResult

if TYPE_CHECKING:
    from .app import AppController


class GrowthDialog(QDialog):
    def __init__(self, controller: "AppController", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.manager = controller.growth_manager
        self.setWindowTitle("养成中心")
        self.resize(720, 620)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.Window
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
        )

        root = QVBoxLayout(self)
        description = QLabel(
            "纯本地养成：背包、硬币、成长和衣柜只保存在本机 data/growth_state.json，"
            "不会进入 Git、发布包或 Provider 请求。"
        )
        description.setWordWrap(True)
        root.addWidget(description)

        self.enabled = QCheckBox("启用本地养成")
        self.enabled.setChecked(self.manager.is_enabled())
        self.enabled.toggled.connect(self._toggle_enabled)
        root.addWidget(self.enabled)

        self.status = QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        self.daily_button = QPushButton("领取今日补给")
        self.daily_button.clicked.connect(
            lambda: self._run_action(self.manager.claim_daily)
        )
        self.content_layout.addWidget(self.daily_button)

        self.item_group = QGroupBox("背包与商店")
        self.item_layout = QVBoxLayout(self.item_group)
        self.content_layout.addWidget(self.item_group)

        self.outfit_group = QGroupBox("衣柜与亲密度解锁")
        self.outfit_layout = QVBoxLayout(self.outfit_group)
        self.content_layout.addWidget(self.outfit_group)
        self.content_layout.addStretch(1)

        footer = QHBoxLayout()
        reset = QPushButton("重置养成数据")
        reset.clicked.connect(self._confirm_reset)
        close = QPushButton("关闭")
        close.clicked.connect(self.accept)
        footer.addWidget(reset)
        footer.addStretch(1)
        footer.addWidget(close)
        root.addLayout(footer)

        self._refresh()

    def _toggle_enabled(self, enabled: bool) -> None:
        self.manager.set_enabled(enabled)
        self.controller.app_config.setdefault("growth", {})["enabled"] = enabled
        self._refresh("养成功能已启用。" if enabled else "养成功能已关闭，数据仍保留在本机。")

    def _run_action(self, action: Callable[[], GrowthResult]) -> None:
        result = action()
        if result.affinity_delta:
            upgrade = self.controller.affinity_manager.add_value(result.affinity_delta)
            self.controller.window.update_affinity(self.controller.affinity_manager.badge())
            self.controller._check_affinity_upgrade(upgrade)
        if result.ok:
            self.controller.window.animation_manager.trigger_happy()
            self.controller.window.speak(result.message)
        self._refresh(result.message)

    def _refresh(self, message: str = "") -> None:
        affinity = self.controller.affinity_manager.value()
        state = self.manager.snapshot(affinity)
        self.status.setText(
            f"{message + ' ' if message else ''}"
            f"当前：{'已启用' if self.manager.is_enabled() else '已关闭'}；"
            f"硬币 {state['coins']}；成长等级 {state['level']}；"
            f"经验 {state['experience']}/{state['next_level_experience']}；"
            f"好感度 {affinity}；当前服装 {self._outfit_name(state['equipped_outfit'])}。"
        )
        self._clear_layout(self.item_layout)
        inventory = state["inventory"]
        for item in self.manager.items():
            count = int(inventory.get(item["id"], 0))
            row = QHBoxLayout()
            text = QLabel(
                f"{item['name']}  |  持有 {count}  |  {item.get('price', 0)} 硬币  |  "
                f"成长 +{item.get('growth', 0)} / 好感 +{item.get('affinity', 0)}\n"
                f"{item.get('description', '')}"
            )
            text.setWordWrap(True)
            buy = QPushButton("购买")
            feed = QPushButton("喂食")
            buy.clicked.connect(
                lambda _checked=False, item_id=item["id"]: self._run_action(
                    lambda: self.manager.buy_item(item_id)
                )
            )
            feed.clicked.connect(
                lambda _checked=False, item_id=item["id"]: self._run_action(
                    lambda: self.manager.feed(item_id)
                )
            )
            buy.setEnabled(self.manager.is_enabled())
            feed.setEnabled(self.manager.is_enabled() and count > 0)
            row.addWidget(text, 1)
            row.addWidget(buy)
            row.addWidget(feed)
            self.item_layout.addLayout(row)

        self._clear_layout(self.outfit_layout)
        available = set(state["available_outfits"])
        owned = set(state["owned_outfits"])
        for outfit in self.manager.outfits():
            row = QHBoxLayout()
            outfit_id = outfit["id"]
            requirements = (
                f"等级 {outfit.get('required_level', 1)} / "
                f"好感 {outfit.get('required_affinity', 0)}"
            )
            state_text = (
                "已装备"
                if state["equipped_outfit"] == outfit_id
                else "已拥有"
                if outfit_id in owned
                else "可解锁"
                if outfit_id in available
                else "未达到条件"
            )
            text = QLabel(
                f"{outfit['name']}  |  {outfit.get('price', 0)} 硬币  |  "
                f"{requirements}  |  {state_text}\n{outfit.get('description', '')}"
            )
            text.setWordWrap(True)
            buy = QPushButton("解锁")
            equip = QPushButton("装备")
            buy.clicked.connect(
                lambda _checked=False, target=outfit_id: self._run_action(
                    lambda: self.manager.buy_outfit(
                        target, self.controller.affinity_manager.value()
                    )
                )
            )
            equip.clicked.connect(
                lambda _checked=False, target=outfit_id: self._run_action(
                    lambda: self.manager.equip_outfit(
                        target, self.controller.affinity_manager.value()
                    )
                )
            )
            buy.setEnabled(
                self.manager.is_enabled()
                and outfit_id in available
                and outfit_id not in owned
            )
            equip.setEnabled(
                self.manager.is_enabled()
                and outfit_id in owned
                and state["equipped_outfit"] != outfit_id
            )
            row.addWidget(text, 1)
            row.addWidget(buy)
            row.addWidget(equip)
            self.outfit_layout.addLayout(row)

        enabled = self.manager.is_enabled()
        self.daily_button.setEnabled(enabled)
        self.item_group.setEnabled(enabled)
        self.outfit_group.setEnabled(enabled)

    def _confirm_reset(self) -> None:
        answer = QMessageBox.question(
            self,
            "确认重置",
            "重置硬币、成长、背包和衣柜？此操作只影响本机养成数据。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.manager.reset_state()
        self._refresh("养成数据已恢复为初始状态。")

    def _outfit_name(self, outfit_id: str) -> str:
        for outfit in self.manager.outfits():
            if outfit["id"] == outfit_id:
                return str(outfit["name"])
        return outfit_id

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            child_layout = item.layout()
            if child_layout is not None:
                while child_layout.count():
                    child = child_layout.takeAt(0)
                    widget = child.widget()
                    if widget is not None:
                        widget.deleteLater()
                child_layout.deleteLater()
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

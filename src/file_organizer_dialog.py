from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .file_organizer import FileOrganizer, FileOrganizerPlan
from .utils import runtime_root


class FileOrganizerDialog(QDialog):
    def __init__(self, enabled: bool, parent=None) -> None:
        super().__init__(parent)
        self.enabled = bool(enabled)
        self.organizer = FileOrganizer(runtime_root() / "data" / "file_organizer")
        self.current_plan: FileOrganizerPlan | None = None

        self.setWindowTitle("文件整理助手（预览）")
        self.resize(900, 560)

        layout = QVBoxLayout(self)
        self.warning = QLabel(
            "默认只生成预览。请选择源目录和目标目录，确认预览后才能执行；不会删除或覆盖文件。"
        )
        self.warning.setWordWrap(True)
        layout.addWidget(self.warning)
        if not self.enabled:
            disabled = QLabel("当前开关为关闭：请先在设置中心启用「文件整理助手」，再生成预览或执行。")
            disabled.setWordWrap(True)
            disabled.setStyleSheet("color: #856404; background: #fff3cd; border: 1px solid #ffeeba; padding: 6px;")
            layout.addWidget(disabled)

        source_row = QHBoxLayout()
        self.source_input = QLineEdit()
        self.source_input.setReadOnly(True)
        source_btn = QPushButton("选择源目录")
        source_btn.clicked.connect(self._choose_source)
        source_row.addWidget(QLabel("源目录"))
        source_row.addWidget(self.source_input, 1)
        source_row.addWidget(source_btn)
        layout.addLayout(source_row)

        target_row = QHBoxLayout()
        self.target_input = QLineEdit()
        self.target_input.setReadOnly(True)
        target_btn = QPushButton("选择目标目录")
        target_btn.clicked.connect(self._choose_target)
        target_row.addWidget(QLabel("目标目录"))
        target_row.addWidget(self.target_input, 1)
        target_row.addWidget(target_btn)
        layout.addLayout(target_row)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["原文件", "类型", "目标分类", "目标路径", "状态", "原因"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        self.status = QLabel("尚未生成预览。")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        self.preview_btn = QPushButton("生成预览")
        self.preview_btn.clicked.connect(self._generate_preview)
        self.execute_btn = QPushButton("执行整理")
        self.execute_btn.setEnabled(False)
        self.execute_btn.clicked.connect(self._execute_plan)
        self.restore_btn = QPushButton("撤销上次整理")
        self.restore_btn.clicked.connect(self._restore_last)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(self.preview_btn)
        buttons.addWidget(self.execute_btn)
        buttons.addWidget(self.restore_btn)
        buttons.addStretch(1)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

    def _choose_source(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择源目录")
        if path:
            self.source_input.setText(path)
            self._clear_plan()

    def _choose_target(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择目标目录")
        if path:
            self.target_input.setText(path)
            self._clear_plan()

    def _generate_preview(self) -> None:
        if not self.enabled:
            self.status.setText("文件整理助手开关关闭，未扫描。")
            self.status.setStyleSheet("color: #856404;")
            return
        source = self.source_input.text().strip()
        target = self.target_input.text().strip()
        self.current_plan = self.organizer.generate_plan(source, target)
        self._render_plan(self.current_plan)

    def _execute_plan(self) -> None:
        if self.current_plan is None or not self.current_plan.ok or not self.current_plan.moves:
            return
        answer = QMessageBox.question(
            self,
            "确认整理",
            f"将移动 {len(self.current_plan.moves)} 个文件。此操作不删除、不覆盖文件，但会改变所选源目录内容。确定执行吗？",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        results = self.organizer.execute_plan(self.current_plan)
        moved = sum(1 for item in results if item.get("status") == "success")
        failed = sum(1 for item in results if item.get("status") == "failed")
        self.status.setText(f"执行完成：成功 {moved}，失败 {failed}。move_log 已写入运行时目录。")
        self.status.setStyleSheet("color: #155724;" if failed == 0 else "color: #856404;")
        self.execute_btn.setEnabled(False)

    def _restore_last(self) -> None:
        log_path = runtime_root() / "data" / "file_organizer" / "move_log.json"
        if not log_path.exists():
            self.status.setText("没有找到上次整理日志。")
            self.status.setStyleSheet("color: #856404;")
            return
        try:
            log_data = json.loads(log_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.status.setText("上次整理日志无法读取，未执行撤销。")
            self.status.setStyleSheet("color: #721c24;")
            return
        plan = self.organizer.generate_restore_plan_from_log(log_data if isinstance(log_data, list) else [])
        if not plan.moves:
            self.status.setText("上次整理日志没有可撤销项目。")
            self.status.setStyleSheet("color: #856404;")
            return
        answer = QMessageBox.question(self, "确认撤销", f"将尝试还原 {len(plan.moves)} 个文件，确定执行吗？")
        if answer != QMessageBox.StandardButton.Yes:
            return
        results = self.organizer.execute_plan(plan)
        restored = sum(1 for item in results if item.get("status") == "success")
        self.status.setText(f"撤销完成：成功 {restored}。")
        self.status.setStyleSheet("color: #155724;")

    def _render_plan(self, plan: FileOrganizerPlan) -> None:
        self.table.setRowCount(0)
        if not plan.ok:
            self.execute_btn.setEnabled(False)
            self.status.setText(f"无法生成预览：{plan.reason}")
            self.status.setStyleSheet("color: #721c24;")
            return
        rows = []
        for move in plan.moves:
            rows.append([move.src_path, Path(move.src_path).suffix.lower() or "other", move.category, move.dst_path, "move", ""])
        for path, reason in plan.skipped:
            rows.append([path, Path(path).suffix.lower() or "other", "", "", "skip", reason])
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for col_index, value in enumerate(row):
                self.table.setItem(row_index, col_index, QTableWidgetItem(str(value)))
        self.execute_btn.setEnabled(bool(plan.moves))
        self.status.setText(f"预览完成：可移动 {len(plan.moves)}，跳过 {len(plan.skipped)}。")
        self.status.setStyleSheet("color: #155724;")

    def _clear_plan(self) -> None:
        self.current_plan = None
        self.execute_btn.setEnabled(False)
        self.table.setRowCount(0)
        self.status.setText("目录已变更，请重新生成预览。")

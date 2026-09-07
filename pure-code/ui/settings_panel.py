"""
PureCode 设置与日志面板

右侧区域：导出设置（无规则文件处理方式）与处理日志显示。
仅视图与事件分发，不含业务逻辑。
"""

from typing import Callable

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from InstructionX_UIKit.components import Switch

# ===== 布局常量 =====
PANEL_MARGIN = 8
PANEL_SPACING = 6


class SettingsPanel(QWidget):
    """右侧设置区与处理日志区"""

    def __init__(self, tr: Callable[..., str], parent=None) -> None:
        """
        Args:
            tr: 取词函数 (group, key, **params) -> str
            parent: 父控件
        """
        super().__init__(parent)
        self._tr = tr
        self._title_label = QLabel(self)
        self._keep_label = QLabel(self)
        self._keep_switch = Switch(checked=True, parent=self)
        self._blank_label = QLabel(self)
        self._blank_switch = Switch(checked=True, parent=self)
        self._log_title = QLabel(self)
        self._log_view = QPlainTextEdit(self)
        self._build_ui()
        self.retranslate()

    def is_keep_unmatched(self) -> bool:
        """无匹配语言规则的文件是否原样保留（False 则导出时跳过）"""
        return self._keep_switch.isChecked()

    def is_remove_blank_lines(self) -> bool:
        """导出时是否移除代码中的全部空行"""
        return self._blank_switch.isChecked()

    def append_log(self, text: str) -> None:
        """追加一行处理日志"""
        self._log_view.appendPlainText(text)

    def clear_log(self) -> None:
        """清空处理日志"""
        self._log_view.clear()

    def retranslate(self) -> None:
        """语言切换：重取全部文案"""
        self._title_label.setText(self._tr("settings", "title"))
        self._keep_label.setText(self._tr("settings", "keep_unmatched"))
        self._blank_label.setText(self._tr("settings", "remove_blank_lines"))
        self._log_title.setText(self._tr("settings", "log_title"))

    def _build_ui(self) -> None:
        """组装设置区与日志区"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            PANEL_MARGIN, PANEL_MARGIN, PANEL_MARGIN, PANEL_MARGIN)
        layout.setSpacing(PANEL_SPACING)
        keep_row = QHBoxLayout()
        keep_row.addWidget(self._keep_label, 1)
        keep_row.addWidget(self._keep_switch)
        blank_row = QHBoxLayout()
        blank_row.addWidget(self._blank_label, 1)
        blank_row.addWidget(self._blank_switch)
        self._log_view.setReadOnly(True)
        layout.addWidget(self._title_label)
        layout.addLayout(keep_row)
        layout.addLayout(blank_row)
        layout.addWidget(self._log_title)
        layout.addWidget(self._log_view, 1)

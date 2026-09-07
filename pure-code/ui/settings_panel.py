"""
PureCode 设置与日志面板

右侧区域：导出设置（无规则文件处理方式）与处理日志显示。
仅视图与事件分发，不含业务逻辑。
"""

from typing import Callable

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from InstructionX_UIKit.components import ProgressBar, Switch

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
        self._progress_label = QLabel(self)
        self._progress_bar = ProgressBar(0, parent=self)
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

    def begin_progress(self) -> None:
        """开始导出：进度条归零并恢复正常状态色"""
        self._progress_bar.set_status("normal")
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)

    def set_progress(self, done: int, total: int) -> None:
        """刷新进度；total 变化时重设量程（处理阶段 → 写文档阶段切换）"""
        if total < 1:
            return
        if total != self._progress_bar.maximum():
            self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(min(done, total))

    def finish_progress(self, success: bool) -> None:
        """导出结束：成功则填满并置绿色，失败标红"""
        if not success:
            self._progress_bar.set_status("error")
            return
        self._progress_bar.setValue(self._progress_bar.maximum())
        self._progress_bar.set_status("success")

    def reset_progress(self) -> None:
        """重置进度条（重新选择项目时调用）"""
        self._progress_bar.set_status("normal")
        self._progress_bar.setValue(0)

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
        self._progress_label.setText(self._tr("settings", "progress_title"))
        self._log_title.setText(self._tr("settings", "log_title"))

    def _build_ui(self) -> None:
        """组装设置区、进度条与日志区"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            PANEL_MARGIN, PANEL_MARGIN, PANEL_MARGIN, PANEL_MARGIN)
        layout.setSpacing(PANEL_SPACING)
        progress_row = QHBoxLayout()
        progress_row.addWidget(self._progress_label)
        progress_row.addWidget(self._progress_bar, 1)
        self._log_view.setReadOnly(True)
        layout.addWidget(self._title_label)
        layout.addLayout(self._build_switch_row(self._keep_label, self._keep_switch))
        layout.addLayout(self._build_switch_row(self._blank_label, self._blank_switch))
        layout.addLayout(progress_row)
        layout.addWidget(self._log_title)
        layout.addWidget(self._log_view, 1)

    def _build_switch_row(self, label: QLabel, switch: Switch) -> QHBoxLayout:
        """组装单行设置项（标签 + 开关）"""
        row = QHBoxLayout()
        row.addWidget(label, 1)
        row.addWidget(switch)
        return row

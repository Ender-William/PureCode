"""
PureCode 文件类型粗选对话框

选择项目目录并完成扫描后弹出：列出检测到的全部扩展名（含文件计数）
复选框，默认全选；用户确认后按所选类型过滤加载文件树。
"""

from typing import Callable

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from InstructionX_UIKit.components import CheckBox, Dialog

# ===== 布局常量 =====
SCROLL_MIN_HEIGHT = 240


class FileTypeDialog(Dialog):
    """扩展名粗选对话框（复选框 + 计数，默认全选）"""

    def __init__(
        self,
        tr: Callable[..., str],
        extension_counts: dict[str, int],
        parent=None,
    ) -> None:
        """
        Args:
            tr: 取词函数 (group, key, **params) -> str
            extension_counts: 扩展名 → 文件数（"" 表示无扩展名）
            parent: 父控件
        """
        super().__init__(parent, title=tr("file_type", "title"))
        self._tr = tr
        self._boxes: dict[str, CheckBox] = {}
        self.set_content(self._build_content(extension_counts))

    def selected_extensions(self) -> set[str]:
        """
        用户勾选的扩展名集合

        Returns:
            扩展名集合（含 "" 表示无扩展名）
        """
        return {ext for ext, box in self._boxes.items() if box.isChecked()}

    def _build_content(self, extension_counts: dict[str, int]) -> QWidget:
        """组装说明、全选/清空按钮与复选框滚动区"""
        content = QWidget(self)
        layout = QVBoxLayout(content)
        hint = QLabel(self._tr("file_type", "hint"), content)
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addLayout(self._build_button_row(content))
        layout.addWidget(self._build_scroll(content, extension_counts), 1)
        return content

    def _build_button_row(self, parent: QWidget) -> QHBoxLayout:
        """全选/清空按钮行"""
        row = QHBoxLayout()
        select_all = QPushButton(self._tr("file_type", "select_all"), parent)
        clear_all = QPushButton(self._tr("file_type", "clear_all"), parent)
        select_all.clicked.connect(lambda: self._set_all(True))
        clear_all.clicked.connect(lambda: self._set_all(False))
        row.addWidget(select_all)
        row.addWidget(clear_all)
        row.addStretch(1)
        return row

    def _build_scroll(
        self, parent: QWidget, extension_counts: dict[str, int]
    ) -> QScrollArea:
        """复选框滚动区：按文件数降序、扩展名升序排列"""
        scroll = QScrollArea(parent)
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(SCROLL_MIN_HEIGHT)
        inner = QWidget(scroll)
        box_layout = QVBoxLayout(inner)
        ordered = sorted(extension_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        for extension, count in ordered:
            box = CheckBox(self._item_text(extension, count), checked=True, parent=inner)
            self._boxes[extension] = box
            box_layout.addWidget(box)
        box_layout.addStretch(1)
        scroll.setWidget(inner)
        return scroll

    def _item_text(self, extension: str, count: int) -> str:
        """复选框文案：扩展名（无扩展名显示占位文案）+ 文件计数"""
        label = extension if extension else self._tr("file_type", "no_extension")
        return self._tr("file_type", "item", ext=label, count=count)

    def _set_all(self, checked: bool) -> None:
        """全选/清空（槽函数，仅批量设置复选框状态）"""
        for box in self._boxes.values():
            box.setChecked(checked)

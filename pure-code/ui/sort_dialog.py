"""
PureCode 文件顺序调整对话框

以可拖拽列表展示当前选中文件的导出顺序：拖拽或上移/下移按钮调整，
支持一键恢复默认排序（深度优先、每层名称字母序）。仅视图与事件分发。
"""

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from InstructionX_UIKit.components import Dialog, ListWidget

# ===== 布局常量 =====
LIST_MIN_HEIGHT = 320
LIST_ITEM_HEIGHT = 28
DIALOG_MIN_WIDTH = 560


class SortDialog(Dialog):
    """文件顺序调整对话框（拖拽 InternalMove + 上移/下移 + 恢复默认）"""

    def __init__(
        self,
        tr: Callable[..., str],
        ordered_files: list[str],
        default_files: list[str],
        parent=None,
    ) -> None:
        """
        Args:
            tr: 取词函数 (group, key, **params) -> str
            ordered_files: 当前导出顺序的文件相对路径列表
            default_files: 默认顺序的文件相对路径列表（恢复默认时使用）
            parent: 父控件
        """
        super().__init__(parent, title=tr("sort", "title"))
        self._tr = tr
        self._default_files = list(default_files)
        self._list = ListWidget(item_height=LIST_ITEM_HEIGHT, parent=self)
        self.setMinimumWidth(DIALOG_MIN_WIDTH)
        self.set_content(self._build_content(ordered_files))

    def ordered_files(self) -> list[str]:
        """
        对话框当前列表顺序的文件相对路径

        Returns:
            自上而下的文件相对路径列表
        """
        return [self._list.item(row).text() for row in range(self._list.count())]

    def _build_content(self, ordered_files: list[str]) -> QWidget:
        """组装说明、按钮行与可拖拽列表"""
        content = QWidget(self)
        layout = QVBoxLayout(content)
        hint = QLabel(self._tr("sort", "hint"), content)
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addLayout(self._build_button_row(content))
        self._setup_list()
        self._fill(ordered_files)
        layout.addWidget(self._list, 1)
        return content

    def _setup_list(self) -> None:
        """配置列表：单选 + 内部拖拽移动"""
        self._list.setMinimumHeight(LIST_MIN_HEIGHT)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._list.setDefaultDropAction(Qt.DropAction.MoveAction)

    def _build_button_row(self, parent: QWidget) -> QHBoxLayout:
        """上移/下移/恢复默认按钮行"""
        row = QHBoxLayout()
        move_up = QPushButton(self._tr("sort", "move_up"), parent)
        move_down = QPushButton(self._tr("sort", "move_down"), parent)
        reset = QPushButton(self._tr("sort", "reset_default"), parent)
        move_up.clicked.connect(self._on_move_up)
        move_down.clicked.connect(self._on_move_down)
        reset.clicked.connect(self._on_reset_default)
        row.addWidget(move_up)
        row.addWidget(move_down)
        row.addWidget(reset)
        row.addStretch(1)
        return row

    def _fill(self, files: list[str]) -> None:
        """按给定顺序重建列表项"""
        self._list.clear()
        self._list.add_items(files)

    def _move_selected(self, delta: int) -> None:
        """将当前选中项上移/下移一位（越界时不动）"""
        row = self._list.currentRow()
        target = row + delta
        if row < 0 or not 0 <= target < self._list.count():
            return
        item = self._list.takeItem(row)
        self._list.insertItem(target, item)
        self._list.setCurrentRow(target)

    def _on_move_up(self) -> None:
        """上移选中项（槽函数，仅分发）"""
        self._move_selected(-1)

    def _on_move_down(self) -> None:
        """下移选中项（槽函数，仅分发）"""
        self._move_selected(1)

    def _on_reset_default(self) -> None:
        """恢复默认排序（槽函数，仅分发）"""
        self._fill(self._default_files)

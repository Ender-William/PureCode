"""
PureCode 文件树面板

以 UIKit Tree（复选框三态联动）按层级展示粗选后的文件，
提供勾选收集与选中统计。仅视图与事件分发，不含业务逻辑。
"""

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QVBoxLayout,
    QWidget,
)

from InstructionX_UIKit import set_property
from InstructionX_UIKit.components import Tree

# ===== 常量 =====
PATH_SEPARATOR = "/"


class FileTreePanel(QWidget):
    """左侧文件树面板：层级展示、复选框勾选、选中统计"""

    checked_changed = Signal()

    def __init__(self, tr: Callable[..., str], parent=None) -> None:
        """
        Args:
            tr: 取词函数 (group, key, **params) -> str
            parent: 父控件
        """
        super().__init__(parent)
        self._tr = tr
        self._tree = Tree(checkable=True, parent=self)
        self._stats = QLabel(self)
        set_property(self._stats, "role", "secondary")
        self._build_ui()
        self._tree.itemChanged.connect(self._on_item_changed)
        self.retranslate()

    def load_files(self, files: list[str]) -> None:
        """
        按相对路径列表重建文件树（默认全部勾选并全部展开）

        Args:
            files: 相对路径列表（posix 分隔符，已按默认顺序排列）
        """
        self._tree.blockSignals(True)
        self._tree.clear()
        nodes: dict[tuple, QTreeWidgetItem] = {}
        for relative in files:
            self._add_path(relative, nodes)
        self._set_all_checked()
        self._tree.expand_all()
        self._tree.blockSignals(False)
        self._update_stats()
        self.checked_changed.emit()

    def checked_files(self) -> list[str]:
        """
        收集全部勾选文件的相对路径（按树的显示顺序，即默认顺序）

        Returns:
            勾选的文件相对路径列表
        """
        checked: list[str] = []
        for item in self._file_items():
            if item.checkState(0) == Qt.CheckState.Checked:
                checked.append(item.data(0, Qt.ItemDataRole.UserRole))
        return checked

    def retranslate(self) -> None:
        """语言切换：重取统计文案"""
        self._update_stats()

    def _build_ui(self) -> None:
        """组装树与统计标签"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tree, 1)
        layout.addWidget(self._stats)

    def _add_path(self, relative: str, nodes: dict[tuple, QTreeWidgetItem]) -> None:
        """按路径分段逐级创建目录/文件节点（已存在则复用）"""
        parts = relative.split(PATH_SEPARATOR)
        parent = None
        for depth, name in enumerate(parts):
            key = tuple(parts[: depth + 1])
            if key not in nodes:
                item = self._tree.add_item(name, parent=parent)
                if depth == len(parts) - 1:
                    item.setData(0, Qt.ItemDataRole.UserRole, relative)
                nodes[key] = item
            parent = nodes[key]

    def _set_all_checked(self) -> None:
        """将全部节点置为勾选（父子三态由 Qt 自动保持一致）"""
        iterator = QTreeWidgetItemIterator(self._tree, QTreeWidgetItemIterator.All)
        while iterator.value():
            iterator.value().setCheckState(0, Qt.CheckState.Checked)
            iterator += 1

    def _file_items(self) -> list[QTreeWidgetItem]:
        """遍历全部文件节点（UserRole 挂载相对路径的叶子项）"""
        items: list[QTreeWidgetItem] = []
        iterator = QTreeWidgetItemIterator(self._tree, QTreeWidgetItemIterator.All)
        while iterator.value():
            item = iterator.value()
            if item.data(0, Qt.ItemDataRole.UserRole):
                items.append(item)
            iterator += 1
        return items

    def _on_item_changed(self, *_args) -> None:
        """勾选变化：刷新统计并通知外部（槽函数，仅分发）"""
        self._update_stats()
        self.checked_changed.emit()

    def _update_stats(self) -> None:
        """刷新选中统计；无文件时显示引导提示"""
        items = self._file_items()
        total = len(items)
        if total == 0:
            self._stats.setText(self._tr("tree", "empty_hint"))
            return
        checked = sum(
            1 for item in items
            if item.checkState(0) == Qt.CheckState.Checked
        )
        self._stats.setText(self._tr("tree", "stats", checked=checked, total=total))

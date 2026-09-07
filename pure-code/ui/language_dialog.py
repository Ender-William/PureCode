"""
PureCode 语言设置对话框

左右两列布局：左列顶部为「添加语言」按钮、下方为语言列表；
右列为所选语言的注释规则与文件扩展名表单（保存/删除/恢复内置默认）。
仅视图与事件分发；规则校验、合并与持久化经 RuleStore 完成。
"""

from enum import Enum, auto
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from InstructionX_UIKit import set_property
from InstructionX_UIKit.components import (
    Dialog,
    FormLayout,
    LineEdit,
    ListWidget,
    Message,
    Switch,
)

from ..function.models import (
    DEFAULT_ESCAPE_CHAR,
    FIELD_BLOCK_COMMENTS,
    FIELD_BUILTIN,
    FIELD_DOCSTRINGS,
    FIELD_ESCAPE_CHAR,
    FIELD_EXTENSIONS,
    FIELD_LINE_COMMENTS,
    FIELD_NAME,
    FIELD_NESTED_BLOCK,
    FIELD_STRING_DELIMITERS,
)
from ..function.rule_store import RuleStore
from ..function.rule_text_codec import (
    format_block_pairs,
    format_tokens,
    parse_block_pairs,
    parse_tokens,
)

# ===== 布局常量 =====
DIALOG_MIN_WIDTH = 760
DIALOG_MIN_HEIGHT = 480
LEFT_PANEL_WIDTH = 220

# ===== 表单占位示例（语法样例，非国际化文案）=====
PLACEHOLDER_EXTENSIONS = ".py .pyw"
PLACEHOLDER_LINE = "#"
PLACEHOLDER_BLOCK = "/* */"
PLACEHOLDER_DELIMITERS = "\"\"\" ''' \" '"
PLACEHOLDER_DOCSTRINGS = "\"\"\" '''"


class _EditorMode(Enum):
    """右列表单编辑模式"""

    IDLE = auto()           # 无选中：表单禁用
    EDIT_SELECTED = auto()  # 编辑列表中选中的语言
    ADD_NEW = auto()        # 新增语言（表单清空可编辑）


class LanguageDialog(Dialog):
    """语言设置对话框：管理内置与用户自定义语言的注释规则"""

    def __init__(
        self,
        tr: Callable[..., str],
        rule_store: RuleStore,
        parent=None,
    ) -> None:
        """
        Args:
            tr: 取词函数 (group, key, **params) -> str
            rule_store: 语言规则存储（读写生效规则的唯一入口）
            parent: 父控件
        """
        super().__init__(parent, title=tr("language", "title"))
        self._tr = tr
        self._store = rule_store
        self._mode = _EditorMode.IDLE
        self.setMinimumSize(DIALOG_MIN_WIDTH, DIALOG_MIN_HEIGHT)
        self.set_content(self._build_content())
        self._reload_list()
        self._apply_mode()

    # ===== 视图组装 =====

    def _build_content(self) -> QWidget:
        """组装左右两列"""
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._build_left_panel(splitter))
        splitter.addWidget(self._build_right_panel(splitter))
        splitter.setSizes([LEFT_PANEL_WIDTH, DIALOG_MIN_WIDTH - LEFT_PANEL_WIDTH])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        return splitter

    def _build_left_panel(self, parent: QWidget) -> QWidget:
        """左列：添加按钮 + 语言列表"""
        panel = QWidget(parent)
        layout = QVBoxLayout(panel)
        add_button = QPushButton(self._tr("language", "add"), panel)
        set_property(add_button, "variant", "primary")
        add_button.clicked.connect(self._on_add)
        self._list = ListWidget(parent=panel)
        self._list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(add_button)
        layout.addWidget(self._list, 1)
        return panel

    def _build_right_panel(self, parent: QWidget) -> QWidget:
        """右列：规则表单 + 操作按钮"""
        panel = QWidget(parent)
        layout = QVBoxLayout(panel)
        hint = QLabel(self._tr("language", "hint"), panel)
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addLayout(self._build_form(panel))
        layout.addLayout(self._build_form_buttons(panel))
        layout.addStretch(1)
        return panel

    def _build_form(self, parent: QWidget) -> FormLayout:
        """规则表单：名称/扩展名/注释符/字符串界定符/文档字符串/嵌套块注释"""
        form = FormLayout(parent)
        self._name_edit = LineEdit(parent=parent)
        self._extensions_edit = LineEdit(placeholder=PLACEHOLDER_EXTENSIONS, parent=parent)
        self._line_edit = LineEdit(placeholder=PLACEHOLDER_LINE, parent=parent)
        self._block_edit = LineEdit(placeholder=PLACEHOLDER_BLOCK, parent=parent)
        self._delimiters_edit = LineEdit(placeholder=PLACEHOLDER_DELIMITERS, parent=parent)
        self._docstrings_edit = LineEdit(placeholder=PLACEHOLDER_DOCSTRINGS, parent=parent)
        self._nested_switch = Switch(parent=parent)
        for key, widget in self._form_rows():
            form.add_row(self._tr("language", key), widget)
        return form

    def _form_rows(self) -> list[tuple[str, QWidget]]:
        """表单字段键与控件的对应表（查表替代重复代码）"""
        return [
            ("name", self._name_edit),
            ("extensions", self._extensions_edit),
            ("line_comments", self._line_edit),
            ("block_comments", self._block_edit),
            ("string_delimiters", self._delimiters_edit),
            ("docstrings", self._docstrings_edit),
            ("nested_block", self._nested_switch),
        ]

    def _build_form_buttons(self, parent: QWidget) -> QHBoxLayout:
        """保存/恢复默认/删除按钮行"""
        row = QHBoxLayout()
        self._save_button = QPushButton(self._tr("language", "save"), parent)
        self._restore_button = QPushButton(self._tr("language", "restore_default"), parent)
        self._delete_button = QPushButton(self._tr("language", "delete"), parent)
        set_property(self._save_button, "variant", "primary")
        set_property(self._delete_button, "variant", "danger")
        self._save_button.clicked.connect(self._on_save)
        self._restore_button.clicked.connect(self._on_restore)
        self._delete_button.clicked.connect(self._on_delete)
        row.addWidget(self._save_button)
        row.addWidget(self._restore_button)
        row.addWidget(self._delete_button)
        row.addStretch(1)
        return row

    # ===== 列表与表单联动 =====

    def _reload_list(self, select_name: "str | None" = None) -> None:
        """重建语言列表（内置/已修改标记后缀），按需恢复选中"""
        self._list.clear()
        for rule in self._store.effective_rules():
            item = QListWidgetItem(self._display_name(rule))
            item.setData(Qt.ItemDataRole.UserRole, rule[FIELD_NAME])
            self._list.addItem(item)
            if rule[FIELD_NAME] == select_name:
                self._list.setCurrentItem(item)

    def _display_name(self, rule: dict) -> str:
        """列表显示名：自定义语言直呼其名，内置语言附标记"""
        if not rule.get(FIELD_BUILTIN):
            return rule[FIELD_NAME]
        if self._store.is_overridden(rule[FIELD_NAME]):
            return rule[FIELD_NAME] + self._tr("language", "tag_overridden")
        return rule[FIELD_NAME] + self._tr("language", "tag_builtin")

    def _on_selection_changed(self, current, _previous) -> None:
        """列表选中变化（槽函数）：载入对应规则到表单"""
        if current is None:
            return
        name = current.data(Qt.ItemDataRole.UserRole)
        rule = self._find_rule(name)
        if rule is not None:
            self._mode = _EditorMode.EDIT_SELECTED
            self._load_form(rule)
            self._apply_mode()

    def _find_rule(self, name: str) -> "dict | None":
        """按名称查找生效规则"""
        for rule in self._store.effective_rules():
            if rule[FIELD_NAME] == name:
                return rule
        return None

    def _load_form(self, rule: dict) -> None:
        """将规则填充到表单（内置语言名称只读）"""
        self._name_edit.setText(rule[FIELD_NAME])
        self._name_edit.setReadOnly(bool(rule.get(FIELD_BUILTIN)))
        self._extensions_edit.setText(format_tokens(rule[FIELD_EXTENSIONS]))
        self._line_edit.setText(format_tokens(rule[FIELD_LINE_COMMENTS]))
        self._block_edit.setText(format_block_pairs(rule[FIELD_BLOCK_COMMENTS]))
        self._delimiters_edit.setText(format_tokens(rule[FIELD_STRING_DELIMITERS]))
        self._docstrings_edit.setText(format_tokens(rule.get(FIELD_DOCSTRINGS) or []))
        self._nested_switch.setChecked(bool(rule[FIELD_NESTED_BLOCK]))

    def _apply_mode(self) -> None:
        """按编辑模式刷新表单与按钮可用性"""
        editing = self._mode != _EditorMode.IDLE
        for _key, widget in self._form_rows():
            widget.setEnabled(editing)
        name = self._selected_name()
        builtin = self._store.is_builtin(name) if name else False
        overridden = self._store.is_overridden(name) if name else False
        self._save_button.setEnabled(editing)
        self._delete_button.setEnabled(
            self._mode == _EditorMode.EDIT_SELECTED and not builtin)
        self._restore_button.setEnabled(
            self._mode == _EditorMode.EDIT_SELECTED and overridden)

    def _selected_name(self) -> "str | None":
        """当前列表选中的语言名"""
        item = self._list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    # ===== 操作槽函数（仅分发，业务经 RuleStore） =====

    def _on_add(self) -> None:
        """添加语言（槽函数）：清空表单进入新增模式"""
        self._mode = _EditorMode.ADD_NEW
        self._list.clearSelection()
        self._clear_form()
        self._apply_mode()

    def _on_save(self) -> None:
        """保存（槽函数）：校验通过则写入 RuleStore 并刷新列表"""
        rule, error = self._collect_form()
        if error is not None:
            Message.warning(self, error)
            return
        self._save_rule(rule)

    def _on_delete(self) -> None:
        """删除（槽函数）：确认后删除自定义语言"""
        name = self._selected_name()
        if name:
            Dialog.confirm(self, self._tr("language", "confirm_delete_title"),
                           self._tr("language", "confirm_delete", name=name),
                           on_result=lambda ok: self._delete_rule(name, ok))

    def _on_restore(self) -> None:
        """恢复内置默认（槽函数）"""
        name = self._selected_name()
        if name:
            self._restore_rule(name)

    # ===== 表单收集与规则操作 =====

    def _collect_form(self) -> "tuple[dict | None, str | None]":
        """收集表单为规则 dict；块注释无法成对时返回错误文案"""
        pairs = parse_block_pairs(self._block_edit.text())
        if pairs is None:
            return None, self._tr("language", "pair_error")
        return {
            FIELD_NAME: self._name_edit.text(),
            FIELD_EXTENSIONS: parse_tokens(self._extensions_edit.text()),
            FIELD_LINE_COMMENTS: parse_tokens(self._line_edit.text()),
            FIELD_BLOCK_COMMENTS: pairs,
            FIELD_STRING_DELIMITERS: parse_tokens(self._delimiters_edit.text()),
            FIELD_DOCSTRINGS: parse_tokens(self._docstrings_edit.text()),
            FIELD_ESCAPE_CHAR: DEFAULT_ESCAPE_CHAR,
            FIELD_NESTED_BLOCK: self._nested_switch.isChecked(),
        }, None

    def _save_rule(self, rule: dict) -> None:
        """保存规则：校验失败弹提示，成功则刷新并选中"""
        errors = self._store.save_user_rule(rule)
        if errors:
            Message.warning(self, self._tr("language", "save_failed")
                            + "：" + "；".join(errors))
            return
        self._reload_list(select_name=rule[FIELD_NAME])
        self._apply_mode()
        Message.success(self, self._tr("language", "saved"))

    def _delete_rule(self, name: str, confirmed: bool) -> None:
        """确认后删除自定义语言并回到空闲态"""
        if not confirmed:
            return
        self._store.delete_language(name)
        self._mode = _EditorMode.IDLE
        self._reload_list()
        self._apply_mode()

    def _restore_rule(self, name: str) -> None:
        """恢复内置默认并重载表单"""
        self._store.restore_builtin(name)
        self._reload_list(select_name=name)
        rule = self._find_rule(name)
        if rule is not None:
            self._load_form(rule)
        self._apply_mode()
        Message.success(self, self._tr("language", "restored"))

    def _clear_form(self) -> None:
        """清空表单（新增模式），名称恢复可编辑"""
        self._name_edit.setText("")
        self._name_edit.setReadOnly(False)
        self._extensions_edit.setText("")
        self._line_edit.setText("")
        self._block_edit.setText("")
        self._delimiters_edit.setText("")
        self._docstrings_edit.setText("")
        self._nested_switch.setChecked(False)

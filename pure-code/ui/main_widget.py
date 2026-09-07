"""
PureCode 主界面

工具栏（选择目录/调整顺序/语言设置/开始导出）+ 左右分栏
（左：文件树；右：设置与日志）。仅做视图组装与事件分发：
业务逻辑委托 PureCodeService，耗时任务经框架后台任务系统执行，
工作线程回调一律经 run_in_ui_thread 封送回 UI 线程。
"""

from enum import Enum, auto
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid as _is_cpp_alive

from InstructionX_UIKit.components import Dialog, Message

from core.i18n import get_language_manager
from core.interfaces import PluginServices, TaskStatus
from utils.thread_utils import run_in_ui_thread

from ..service import PureCodeService
from .file_tree_panel import FileTreePanel
from .file_type_dialog import FileTypeDialog
from .language_dialog import LanguageDialog
from .settings_panel import SettingsPanel
from .sort_dialog import SortDialog

# ===== 布局常量 =====
TREE_PANEL_INITIAL_WIDTH = 320
TREE_PANEL_MIN_WIDTH = 240
RIGHT_PANEL_MIN_WIDTH = 360

# ===== 任务与文件名常量 =====
MODULE_NAME = "pure-code.main_widget"
EXPORT_NAME_TEMPLATE = "{name}_code.docx"
TASK_NAME_SCAN = "pure-code-scan"
TASK_NAME_EXPORT = "pure-code-export"


class _UiState(Enum):
    """主界面状态枚举"""

    IDLE = auto()       # 未选目录（或粗选取消）
    SCANNING = auto()   # 目录扫描中
    READY = auto()      # 文件树已就绪
    EXPORTING = auto()  # 导出任务执行中


# 状态机转换表：各工具栏动作在哪些状态下可用
_ACTION_STATES = {
    "select_dir": {_UiState.IDLE, _UiState.READY},
    "sort_files": {_UiState.READY},
    "language_settings": {
        _UiState.IDLE, _UiState.SCANNING, _UiState.READY, _UiState.EXPORTING,
    },
    "start_export": {_UiState.READY},
}


class PureCodeMainWidget(QWidget):
    """PureCode 主界面控件（状态机驱动工具栏动作可用性）"""

    def __init__(
        self,
        services: "PluginServices | None",
        service: PureCodeService,
        plugin_id: "str | None",
        parent=None,
    ) -> None:
        """
        Args:
            services: 框架注入的服务容器（任务管理/日志/取词），可为 None
            service: 插件服务门面（业务入口）
            plugin_id: 插件 UUID（后台任务注册与语言覆盖信号比对依据）
            parent: 父控件
        """
        super().__init__(parent)
        self._services = services
        self._service = service
        self._plugin_id = plugin_id
        self._i18n = services.localization if services else None
        self._logger = services.logger if services else None
        self._state = _UiState.IDLE
        self._project_root: "str | None" = None
        self._custom_order: "list[str] | None" = None
        self._actions: dict[str, QAction] = {}
        self._tree_panel = FileTreePanel(self._tr, self)
        self._settings_panel = SettingsPanel(self._tr, self)
        self._build_ui()
        self._connect_signals()
        self._retranslate_ui()
        self._apply_state()

    # ===== 视图组装 =====

    def _build_ui(self) -> None:
        """组装工具栏与左右分栏"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_toolbar())
        layout.addWidget(self._build_splitter(), 1)

    def _build_toolbar(self) -> QToolBar:
        """构建工具栏动作（文本由 _retranslate_ui 统一设置）"""
        toolbar = QToolBar(self)
        toolbar.setMovable(False)
        slots = {
            "select_dir": self._on_select_dir,
            "sort_files": self._on_sort_files,
            "language_settings": self._on_language_settings,
            "start_export": self._on_start_export,
        }
        for key, slot in slots.items():
            if key == "start_export":
                toolbar.addSeparator()
            action = QAction("", toolbar)
            action.triggered.connect(slot)
            toolbar.addAction(action)
            self._actions[key] = action
        return toolbar

    def _build_splitter(self) -> QSplitter:
        """左右分栏：左文件树（初始固定宽度、向左吸附），右设置与日志"""
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._tree_panel.setMinimumWidth(TREE_PANEL_MIN_WIDTH)
        self._settings_panel.setMinimumWidth(RIGHT_PANEL_MIN_WIDTH)
        splitter.addWidget(self._tree_panel)
        splitter.addWidget(self._settings_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([TREE_PANEL_INITIAL_WIDTH, RIGHT_PANEL_MIN_WIDTH])
        splitter.setCollapsible(0, False)
        return splitter

    def _connect_signals(self) -> None:
        """连接树勾选统计与框架语言切换信号"""
        self._tree_panel.checked_changed.connect(self._apply_state)
        language_manager = get_language_manager()
        language_manager.language_changed.connect(self._retranslate_ui)
        language_manager.plugin_language_changed.connect(
            self._on_plugin_language_changed)

    # ===== 工具栏槽函数（仅分发，业务在下方私有方法） =====

    def _on_select_dir(self) -> None:
        """选择项目目录"""
        directory = QFileDialog.getExistingDirectory(
            self, self._tr("toolbar", "select_dir"))
        if directory:
            self._start_scan(directory)

    def _on_sort_files(self) -> None:
        """调整文件顺序"""
        self._open_sort_dialog(self._ordered_checked_files())

    def _open_sort_dialog(self, current_files: list[str]) -> None:
        """打开排序对话框：以当前导出顺序展示，确认后保存自定义顺序"""
        if not current_files:
            Message.warning(self, self._tr("export", "no_selection"))
            return
        default_files = self._tree_panel.checked_files()
        dialog = SortDialog(self._tr, current_files, default_files, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._custom_order = dialog.ordered_files()
        self._settings_panel.append_log(
            self._tr("task", "order_applied", count=len(self._custom_order)))

    def _on_language_settings(self) -> None:
        """语言设置"""
        self._open_language_dialog()

    def _open_language_dialog(self) -> None:
        """打开语言设置对话框（规则读写经服务持有的 RuleStore）"""
        dialog = LanguageDialog(self._tr, self._service.get_rule_store(), self)
        dialog.exec()

    def _on_start_export(self) -> None:
        """开始导出"""
        self._start_export_flow(self._ordered_checked_files())

    # ===== 扫描流程 =====

    def _start_scan(self, directory: str) -> None:
        """进入扫描态并提交后台扫描任务"""
        self._set_state(_UiState.SCANNING)
        self._settings_panel.clear_log()
        self._settings_panel.append_log(self._tr("task", "scanning"))
        self._submit_task(TASK_NAME_SCAN, self._service.scan_project,
                          self._on_scan_finished, args=(directory,))

    def _on_scan_finished(self, _task_id, status, result, error) -> None:
        """扫描任务回调（工作线程）：封送至 UI 线程处理"""
        run_in_ui_thread(self._handle_scan_result, status, result, error)

    def _handle_scan_result(self, status, result, error) -> None:
        """扫描结果处理（UI 线程）"""
        if not _is_cpp_alive(self):
            return
        if status != TaskStatus.COMPLETED or result is None:
            self._set_state(_UiState.IDLE)
            self._report_scan_error(error)
            return
        self._after_scan(result)

    def _after_scan(self, scan) -> None:
        """扫描成功：空项目直接提示；否则弹文件类型粗选对话框"""
        if not scan.files:
            self._set_state(_UiState.IDLE)
            Dialog.info(self, self._tr("file_type", "title"),
                        self._tr("file_type", "empty"))
            return
        dialog = FileTypeDialog(self._tr, scan.extension_counts, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self._set_state(_UiState.IDLE)
            return
        self._load_project(scan, dialog.selected_extensions())

    def _load_project(self, scan, selected_extensions: set[str]) -> None:
        """按粗选类型过滤并加载文件树，进入就绪态"""
        files = self._service.filter_files(scan.files, selected_extensions)
        self._project_root = scan.root
        self._custom_order = None
        self._tree_panel.load_files(files)
        self._set_state(_UiState.READY)
        self._settings_panel.append_log(self._tr(
            "task", "scan_done", total=len(scan.files), loaded=len(files)))

    def _report_scan_error(self, error) -> None:
        """扫描失败：日志 + 弹窗双通道告知"""
        self._settings_panel.append_log(self._tr("task", "scan_failed", error=error))
        self._log("ERROR", f"目录扫描失败: {error}")
        Dialog.info(self, self._tr("task", "scan_failed_title"),
                    self._tr("task", "scan_failed", error=error))

    # ===== 导出流程 =====

    def _start_export_flow(self, files: list[str]) -> None:
        """导出入口校验：勾选为空提示，否则选择保存路径后开始"""
        if not files:
            Message.warning(self, self._tr("export", "no_selection"))
            return
        output_path = self._ask_output_path()
        if output_path:
            self._begin_export(files, output_path)

    def _ask_output_path(self) -> "str | None":
        """保存对话框：预填 {项目名}_code.docx"""
        project_name = Path(self._project_root).name
        default_name = EXPORT_NAME_TEMPLATE.format(name=project_name)
        path, _filter = QFileDialog.getSaveFileName(
            self, self._tr("export", "save_title"), default_name,
            self._tr("export", "file_filter"))
        return path or None

    def _begin_export(self, files: list[str], output_path: str) -> None:
        """进入导出态并提交后台导出任务"""
        self._set_state(_UiState.EXPORTING)
        self._settings_panel.append_log(self._tr("task", "exporting"))
        self._submit_task(
            TASK_NAME_EXPORT, self._service.run_export, self._on_export_finished,
            args=(self._project_root, files, output_path,
                  self._settings_panel.is_keep_unmatched(),
                  self._on_export_progress,
                  self._settings_panel.is_remove_blank_lines()))

    def _on_export_progress(self, current: str, done: int, total: int) -> None:
        """导出进度回调（工作线程）：逐文件日志封送至 UI 线程"""
        if current:
            run_in_ui_thread(self._append_progress_log, current, done, total)

    def _append_progress_log(self, current: str, done: int, total: int) -> None:
        """追加逐文件处理日志（UI 线程）"""
        if _is_cpp_alive(self):
            self._settings_panel.append_log(self._tr(
                "task", "progress_item", done=done, total=total, file=current))

    def _on_export_finished(self, _task_id, status, result, error) -> None:
        """导出任务回调（工作线程）：封送至 UI 线程处理"""
        run_in_ui_thread(self._handle_export_result, status, result, error)

    def _handle_export_result(self, status, result, error) -> None:
        """导出结果处理（UI 线程）"""
        if not _is_cpp_alive(self):
            return
        self._set_state(_UiState.READY)
        if status == TaskStatus.COMPLETED and result is not None:
            self._report_export_success(result)
            return
        self._report_export_failure(error)

    def _report_export_success(self, result: dict) -> None:
        """导出成功：记录跳过/无规则清单 + 完成日志 + 弹窗告知"""
        for skipped in result.get("skipped", []):
            self._settings_panel.append_log(
                self._tr("task", "skipped_item", file=skipped))
        for unmatched in result.get("unmatched", []):
            self._settings_panel.append_log(
                self._tr("task", "unmatched_item", file=unmatched))
        self._settings_panel.append_log(self._tr(
            "task", "export_done", count=result["file_count"],
            path=result["output_path"]))
        Dialog.info(self, self._tr("export", "done_title"), self._tr(
            "export", "done_msg", count=result["file_count"],
            path=result["output_path"]))

    def _report_export_failure(self, error) -> None:
        """导出失败：日志 + 弹窗双通道告知"""
        self._settings_panel.append_log(self._tr("task", "export_failed", error=error))
        self._log("ERROR", f"导出任务失败: {error}")
        Dialog.info(self, self._tr("export", "fail_title"),
                    self._tr("export", "fail_msg", error=error))

    def _ordered_checked_files(self) -> list[str]:
        """勾选文件按自定义顺序（若有）排列，未列入的按默认顺序追加"""
        checked = self._tree_panel.checked_files()
        if not self._custom_order:
            return checked
        ordered = [rel for rel in self._custom_order if rel in checked]
        ordered.extend(rel for rel in checked if rel not in set(ordered))
        return ordered

    # ===== 任务提交与状态机 =====

    def _submit_task(self, name: str, func, callback, args: tuple = ()) -> None:
        """提交后台任务；任务管理器不可用时降级为同步执行并记 WARNING"""
        manager = self._services.task_manager if self._services else None
        if manager is None:
            self._log("WARNING", "任务管理器不可用，任务降级为同步执行")
            self._run_sync(func, callback, args)
            return
        manager.register_async_task(self._plugin_id, name, func,
                                    callback=callback, args=args)

    def _run_sync(self, func, callback, args: tuple) -> None:
        """同步降级路径：包装为与后台任务一致的回调签名"""
        try:
            callback(None, TaskStatus.COMPLETED, func(*args), None)
        except Exception as exc:  # 降级路径须兜底，异常转入统一失败处理
            callback(None, TaskStatus.FAILED, None, exc)

    def _set_state(self, state: _UiState) -> None:
        """切换界面状态并刷新动作可用性"""
        self._state = state
        self._apply_state()

    def _apply_state(self) -> None:
        """按状态机转换表刷新工具栏动作可用性（导出另需勾选非空）"""
        for key, action in self._actions.items():
            enabled = self._state in _ACTION_STATES[key]
            if key == "start_export":
                enabled = enabled and bool(self._tree_panel.checked_files())
            action.setEnabled(enabled)

    # ===== 国际化与日志 =====

    def _retranslate_ui(self) -> None:
        """语言切换：重取工具栏与各面板文案"""
        for key, action in self._actions.items():
            action.setText(self._tr("toolbar", key))
        self._tree_panel.retranslate()
        self._settings_panel.retranslate()

    def _on_plugin_language_changed(self, plugin_id: str, _language: str) -> None:
        """本插件语言覆盖变化时重取文案（比对插件 UUID）"""
        if plugin_id == self._plugin_id:
            self._retranslate_ui()

    def _tr(self, group: str, key: str, **params) -> str:
        """取词辅助：门面缺失时降级返回键名"""
        if self._i18n is None:
            return key
        return self._i18n.tr(group, key, **params)

    def _log(self, level: str, message: str) -> None:
        """记录日志（logger 缺失时静默降级）"""
        if self._logger is not None:
            self._logger.log(level, MODULE_NAME, message)

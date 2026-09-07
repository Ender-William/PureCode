"""
PureCode 插件入口（胶水层）

仅负责协调 UI 与 Service，不包含业务逻辑：
- 接收框架注入的 PluginServices；
- 惰性创建插件主控件（框架控件缓存机制托管）。
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from core.interfaces import PluginServices
from core.plugin.plugin_interface import IPlugin


class PureCodePlugin(IPlugin):
    """
    PureCode 插件入口类

    职责：保存框架服务引用、创建主控件、响应加载/卸载生命周期。
    """

    def __init__(self, services: "PluginServices | None" = None) -> None:
        """
        初始化插件实例

        Args:
            services: 框架注入的服务容器（数据、日志、任务、取词等），可为 None
        """
        super().__init__()
        self._services = services
        self._i18n = services.localization if services else None

    @property
    def plugin_name(self) -> str:
        """插件显示名称（品牌名，不翻译）"""
        return "PureCode"

    def _create_widget(self, parent=None, data_provider=None) -> QWidget:
        """
        创建插件主控件

        骨架阶段为占位控件；主界面（main_widget）实现后替换。

        Args:
            parent: 父控件（框架工作区容器）
            data_provider: 框架传入的数据提供者（当前不使用，数据走 services）

        Returns:
            插件根 QWidget
        """
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        placeholder = QLabel(self._tr("main", "placeholder"), widget)
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(placeholder)
        return widget

    def on_plugin_loaded(self) -> None:
        """插件加载完成回调（此时 UI 尚未创建，禁止实例化 QWidget）"""

    def on_plugin_unloaded(self) -> None:
        """插件卸载回调：清理订阅与资源（当前无持有资源）"""

    def _tr(self, group: str, key: str, **params) -> str:
        """
        取词辅助：经注入的本地化门面取词，门面缺失时降级返回键名

        Args:
            group: 语言包分组名
            key: 词条键名
            **params: 命名占位符参数

        Returns:
            翻译文本
        """
        if self._i18n is None:
            return key
        return self._i18n.tr(group, key, **params)

"""
PureCode 插件入口（胶水层）

仅负责协调 UI 与 Service，不包含业务逻辑：
- 接收框架注入的 PluginServices；
- 惰性创建服务门面（需等待框架设置 plugin_id）；
- 创建插件主控件（框架控件缓存机制托管）。
"""

from PySide6.QtWidgets import QWidget

from core.interfaces import PluginServices
from core.plugin.plugin_interface import IPlugin

from .service import PureCodeService
from .ui.main_widget import PureCodeMainWidget


class PureCodePlugin(IPlugin):
    """
    PureCode 插件入口类

    职责：保存框架服务引用、创建主控件、响应加载/卸载生命周期。
    """

    def __init__(self, services: "PluginServices | None" = None) -> None:
        """
        Args:
            services: 框架注入的服务容器（数据、日志、任务、取词等），可为 None
        """
        super().__init__()
        self._services = services
        self._service: "PureCodeService | None" = None

    @property
    def plugin_name(self) -> str:
        """插件显示名称（品牌名，不翻译）"""
        return "PureCode"

    def _create_widget(self, parent=None, data_provider=None) -> QWidget:
        """
        创建插件主控件

        Args:
            parent: 父控件（框架工作区容器）
            data_provider: 框架传入的数据提供者（不使用，数据走 services）

        Returns:
            插件根 QWidget
        """
        self._ensure_service()
        return PureCodeMainWidget(
            self._services, self._service, self.plugin_id, parent)

    def on_plugin_loaded(self) -> None:
        """插件加载完成回调（此时 UI 尚未创建，禁止实例化 QWidget）"""

    def on_plugin_unloaded(self) -> None:
        """插件卸载回调（无 DataProvider 订阅与自持资源，任务由框架统一管理）"""

    def _ensure_service(self) -> None:
        """惰性创建服务门面（需 plugin_id，须在框架完成加载后）"""
        if self._service is None:
            data_provider = self._services.data_provider if self._services else None
            self._service = PureCodeService(self.plugin_id, data_provider)

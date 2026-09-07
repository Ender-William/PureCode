"""
PureCode 插件服务层（对外接口门面）

对框架/其他插件/MCP 暴露导出 API，对插件 UI 提供业务入口。
本层只做编排与委托，业务实现位于 function/ 各模块。
"""

from pathlib import Path

from utils.logging_tools import LoggerManager

from .function.export_pipeline import ExportPipeline, ProgressCallback
from .function.project_scanner import ProjectScanner, ScanResult
from .function.rule_store import RuleStore

MODULE_NAME = "pure-code.service"


class PureCodeService:
    """
    PureCode 服务门面

    组合 RuleStore / ProjectScanner / ExportPipeline 为统一入口。
    框架自动注册时按候选签名 (plugin_id, data_provider) 实例化；
    插件 UI 侧可经同名签名手动创建共享同一规则存储。
    """

    def __init__(self, plugin_id: "str | None" = None, data_provider=None) -> None:
        """
        Args:
            plugin_id: 插件 UUID（DataProvider 命名空间隔离依据）
            data_provider: 框架数据提供者，可为 None（规则覆盖降级为内存态）
        """
        logger = LoggerManager()
        plugin_dir = Path(__file__).resolve().parent
        self._rule_store = RuleStore(plugin_dir, data_provider, plugin_id, logger)
        self._scanner = ProjectScanner(logger)
        self._pipeline = ExportPipeline(self._rule_store, logger=logger)
        self._logger = logger

    # ===== 对外 API（与 information.py 的 service_api 保持同步）=====

    def export_code_document(
        self,
        project_dir: str,
        output_path: str,
        extensions: "list[str] | None" = None,
    ) -> dict:
        """
        扫描项目目录并按默认顺序导出代码 Word 文档（去注释）

        Args:
            project_dir: 项目根目录绝对路径
            output_path: 输出 docx 文件路径
            extensions: 限定导出的扩展名列表（None 表示全部类型）

        Returns:
            结果 dict：output_path / file_count / skipped / unmatched

        Raises:
            NotADirectoryError: project_dir 无效
            OSError: 输出路径不可写
        """
        scan = self._scanner.scan(project_dir)
        files = scan.files
        if extensions is not None:
            files = self._scanner.filter_by_extensions(files, set(extensions))
        return self._pipeline.run(project_dir, files, output_path)

    def list_supported_languages(self) -> list[dict]:
        """
        列出当前生效的语言注释规则（内置 ∪ 用户覆盖）

        Returns:
            规则 dict 列表（字段见 function/models.py，含 builtin 标记）
        """
        return self._rule_store.effective_rules()

    # ===== 插件内部入口（UI 层经 entrance 调用）=====

    def scan_project(self, project_dir: "str | Path") -> ScanResult:
        """扫描项目目录（扩展名统计 + 默认顺序文件列表）"""
        return self._scanner.scan(project_dir)

    def filter_files(self, files: list[str], extensions: set[str]) -> list[str]:
        """按粗选扩展名过滤文件列表（保持顺序）"""
        return self._scanner.filter_by_extensions(files, extensions)

    def run_export(
        self,
        root: "str | Path",
        ordered_files: list[str],
        output_path: "str | Path",
        keep_unmatched: bool = True,
        progress: "ProgressCallback | None" = None,
    ) -> dict:
        """按指定文件顺序执行导出流水线（UI 后台任务入口）"""
        return self._pipeline.run(root, ordered_files, output_path, keep_unmatched, progress)

    def get_rule_store(self) -> RuleStore:
        """获取语言规则存储（语言设置界面读写规则的入口）"""
        return self._rule_store

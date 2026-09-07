"""
PureCode 项目目录扫描

递归扫描用户选择的项目目录：统计全部文件扩展名（供文件类型粗选）、
产出默认顺序的文件相对路径列表（深度优先、每层按名称字母序）。
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from utils.i_logger import ILogger

# ===== 常量 =====
MODULE_NAME = "pure-code.project_scanner"
NO_EXTENSION = ""

# 扫描时默认跳过的目录名：版本控制、依赖目录与常见缓存/构建产物，
# 避免 node_modules/.git 等噪声文件淹没文件树（软著材料只关心自有源码）
SKIP_DIR_NAMES = frozenset({
    ".git", ".svn", ".hg",
    "node_modules", "__pycache__", ".venv", "venv",
    ".idea", ".vscode",
    "dist", "build", "out", "target", "bin", "obj",
})


@dataclass
class ScanResult:
    """
    目录扫描结果（纯数据）

    Attributes:
        root: 项目根目录绝对路径
        files: 全部文件的相对路径列表（posix 分隔符，默认顺序）
        extension_counts: 扩展名 → 文件数（无扩展名以 "" 为键）
    """

    root: str
    files: list[str] = field(default_factory=list)
    extension_counts: dict[str, int] = field(default_factory=dict)


class ProjectScanner:
    """
    项目目录扫描器

    仅读取目录结构与文件元信息，不读取/修改任何文件内容。
    """

    def __init__(self, logger: "ILogger | None" = None) -> None:
        """
        Args:
            logger: 框架日志器，可为 None（静默降级）
        """
        self._logger = logger

    def scan(self, root: "str | Path") -> ScanResult:
        """
        扫描项目目录

        Args:
            root: 项目根目录

        Returns:
            ScanResult（files 按默认顺序：深度优先、每层名称字母序）

        Raises:
            NotADirectoryError: root 不是有效目录
        """
        root_path = Path(root)
        if not root_path.is_dir():
            raise NotADirectoryError(f"无效的项目目录: {root}")
        result = ScanResult(root=str(root_path))
        self._walk(root_path, result)
        self._log_info(f"扫描完成: {root_path}，共 {len(result.files)} 个文件")
        return result

    def filter_by_extensions(
        self, files: list[str], selected_extensions: set[str]
    ) -> list[str]:
        """
        按粗选扩展名过滤文件列表（保持原有顺序）

        Args:
            files: 文件相对路径列表
            selected_extensions: 选中的扩展名集合（含 "" 表示无扩展名）

        Returns:
            过滤后的相对路径列表
        """
        return [
            rel for rel in files
            if Path(rel).suffix.lower() in selected_extensions
        ]

    def _walk(self, root_path: Path, result: ScanResult) -> None:
        """os.walk 自顶向下遍历，目录与文件名就地排序形成默认顺序"""
        for dir_path, dir_names, file_names in os.walk(
            root_path, onerror=self._on_walk_error
        ):
            dir_names[:] = sorted(
                (name for name in dir_names if name not in SKIP_DIR_NAMES),
                key=str.lower,
            )
            for file_name in sorted(file_names, key=str.lower):
                absolute = Path(dir_path) / file_name
                relative = absolute.relative_to(root_path).as_posix()
                result.files.append(relative)
                extension = absolute.suffix.lower()
                result.extension_counts[extension] = (
                    result.extension_counts.get(extension, 0) + 1
                )

    def _on_walk_error(self, error: OSError) -> None:
        """os.walk 错误回调：目录不可读等异常跳过并记 WARNING，不中断扫描"""
        self._log_warning(f"目录访问失败已跳过: {error}")

    def _log_info(self, message: str) -> None:
        """记录 INFO 日志（logger 缺失时静默降级）"""
        if self._logger is not None:
            self._logger.info(MODULE_NAME, message)

    def _log_warning(self, message: str) -> None:
        """记录 WARNING 日志（logger 缺失时静默降级）"""
        if self._logger is not None:
            self._logger.warning(MODULE_NAME, message)

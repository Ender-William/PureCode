"""
PureCode 导出流水线

编排「读文件 → 编码回退解码 → 按规则去注释 →（可选）移除空行 →
组装文件块 → 写 docx」全过程。纯业务层，不依赖 PySide6；
进度经回调上报，线程封送由调用方负责。
"""

from pathlib import Path
from typing import Callable

from utils.i_logger import ILogger

from .comment_stripper import CommentStripper
from .document_exporter import DocxExporter, FileBlock
from .rule_store import RuleStore

# ===== 常量 =====
MODULE_NAME = "pure-code.export_pipeline"
# 文件解码回退链：Windows 中文项目常见 GBK 系编码，utf-8 失败后回退 gb18030
ENCODING_FALLBACK_CHAIN = ("utf-8", "gb18030")
# 进度回调签名: (当前文件相对路径, 已完成数, 总数)
ProgressCallback = Callable[[str, int, int], None]


def _drop_blank_lines(code: str) -> str:
    """移除文本中的全部空行（仅含空白字符的行视为空行）"""
    return "\n".join(line for line in code.split("\n") if line.strip())


class ExportPipeline:
    """
    导出流水线

    对有序文件相对路径列表依次处理并生成 docx；单文件失败（读取/编码）
    跳过并记日志，不中断整体导出；全程只读源文件，不做任何写回。
    """

    def __init__(
        self,
        rule_store: RuleStore,
        stripper: "CommentStripper | None" = None,
        exporter: "DocxExporter | None" = None,
        logger: "ILogger | None" = None,
    ) -> None:
        """
        Args:
            rule_store: 语言规则存储（按扩展名取生效规则）
            stripper: 去注释引擎，None 时内部创建
            exporter: docx 导出器，None 时内部创建
            logger: 框架日志器，可为 None（静默降级）
        """
        self._rule_store = rule_store
        self._stripper = stripper or CommentStripper()
        self._exporter = exporter or DocxExporter()
        self._logger = logger

    def run(
        self,
        root: "str | Path",
        ordered_files: list[str],
        output_path: "str | Path",
        keep_unmatched: bool = True,
        progress: "ProgressCallback | None" = None,
        remove_blank_lines: bool = False,
    ) -> dict:
        """
        执行导出流水线

        Args:
            root: 项目根目录
            ordered_files: 有序文件相对路径列表（导出顺序即列表顺序）
            output_path: 输出 docx 路径
            keep_unmatched: 无匹配语言规则的文件是否原样保留（False 则跳过）
            progress: 进度回调（在工作线程中被调用，UI 更新须自行封送）
            remove_blank_lines: 是否移除代码中的全部空行（默认保留原始空行）

        Returns:
            结果 dict：output_path / file_count / skipped（失败列表）/
            unmatched（无规则文件列表）

        Raises:
            OSError: 输出路径不可写（整体失败）
        """
        blocks, skipped, unmatched = self._collect_blocks(
            Path(root), ordered_files, keep_unmatched, progress)
        if remove_blank_lines:
            blocks = [
                FileBlock(block.relative_path, _drop_blank_lines(block.code))
                for block in blocks
            ]
        # 处理阶段收尾（进度条满），随后进入写文档阶段（current 为空串标识）
        self._report_progress(progress, "", len(ordered_files), len(ordered_files))
        self._exporter.write(
            output_path, Path(root).name, blocks,
            progress=self._write_progress_hook(progress))
        self._report_progress(progress, "", len(blocks), len(blocks))
        return {
            "output_path": str(output_path),
            "file_count": len(blocks),
            "skipped": skipped,
            "unmatched": unmatched,
        }

    def _collect_blocks(
        self,
        root_path: Path,
        ordered_files: list[str],
        keep_unmatched: bool,
        progress: "ProgressCallback | None",
    ) -> tuple[list[FileBlock], list[str], list[str]]:
        """逐文件处理并汇总文件块与失败/无规则清单"""
        blocks: list[FileBlock] = []
        skipped: list[str] = []
        unmatched: list[str] = []
        total = len(ordered_files)
        for index, relative in enumerate(ordered_files):
            self._report_progress(progress, relative, index, total)
            block = self._process_file(
                root_path, relative, keep_unmatched, skipped, unmatched)
            if block is not None:
                blocks.append(block)
        return blocks, skipped, unmatched

    def _process_file(
        self,
        root_path: Path,
        relative: str,
        keep_unmatched: bool,
        skipped: list[str],
        unmatched: list[str],
    ) -> "FileBlock | None":
        """处理单文件：读取 → 解码 → 去注释/原样保留，失败记入清单"""
        try:
            raw = (root_path / relative).read_bytes()
        except OSError as exc:
            self._log_warning(f"文件读取失败已跳过: {relative}（{exc}）")
            skipped.append(relative)
            return None
        source = self._decode(raw, relative)
        if source is None:
            skipped.append(relative)
            return None
        return self._build_block(relative, source, keep_unmatched, unmatched)

    def _build_block(
        self,
        relative: str,
        source: str,
        keep_unmatched: bool,
        unmatched: list[str],
    ) -> "FileBlock | None":
        """按语言规则构建文件块；无规则文件按 keep_unmatched 决定去留"""
        rule = self._rule_store.rule_for_extension(Path(relative).suffix)
        if rule is not None:
            return FileBlock(relative, self._stripper.strip(source, rule))
        unmatched.append(relative)
        self._log_warning(
            f"无匹配语言规则: {relative}（{'原样保留' if keep_unmatched else '已跳过'}）")
        return FileBlock(relative, source) if keep_unmatched else None

    def _decode(self, raw: bytes, relative: str) -> "str | None":
        """按回退链解码文件字节并统一换行符为 \n，全部失败返回 None 并记 WARNING"""
        for encoding in ENCODING_FALLBACK_CHAIN:
            try:
                # Windows 源文件多为 CRLF：解码后统一归一为 \n，
                # 否则无规则文件原样保留路径残留的 \r 会被 python-docx
                # 转换为 <w:br/>，导致 Word 中每行多出断行
                return raw.decode(encoding).replace("\r\n", "\n").replace("\r", "\n")
            except UnicodeDecodeError:
                continue
        self._log_warning(f"文件编码无法识别已跳过: {relative}")
        return None

    def _write_progress_hook(
        self, progress: "ProgressCallback | None"
    ) -> "Callable[[int, int], None] | None":
        """把写入阶段的 (块索引, 总数) 回调适配为统一进度回调（current 空串标识写文档阶段）"""
        if progress is None:
            return None

        def _hook(index: int, total: int) -> None:
            self._report_progress(progress, "", index, total)

        return _hook

    def _report_progress(
        self, progress: "ProgressCallback | None", current: str, done: int, total: int
    ) -> None:
        """上报进度（回调异常不影响导出主流程）"""
        if progress is None:
            return
        try:
            progress(current, done, total)
        except Exception as exc:  # 回调属调用方代码，隔离其异常
            self._log_warning(f"进度回调执行异常: {exc}")

    def _log_warning(self, message: str) -> None:
        """记录 WARNING 日志（logger 缺失时静默降级）"""
        if self._logger is not None:
            self._logger.warning(MODULE_NAME, message)

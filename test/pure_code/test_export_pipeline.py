"""PureCode 导出流水线集成测试（function/export_pipeline.py）

使用插件真实内置规则（config/default_rules.json），DataProvider 缺省降级为
内存态（RuleStore 不持久化用户覆盖，不影响导出链路验证）。
"""

from pathlib import Path

import pytest
from docx import Document

from pure_code.function.export_pipeline import ExportPipeline
from pure_code.function.rule_store import RuleStore

PLUGIN_DIR = Path(__file__).resolve().parents[2] / "pure-code"
PROJECT_NAME = "demo_proj"


def _read_doc_texts(path: Path) -> list[str]:
    """读取 docx 全部段落文本（含标题，按文档顺序）"""
    return [p.text for p in Document(path).paragraphs]


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    """构造待导出项目：UTF-8 源码、GBK 源码、无规则文件与损坏文件"""
    root = tmp_path / PROJECT_NAME
    (root / "src").mkdir(parents=True)
    (root / "main.py").write_text(
        '# 头部注释\nx = 1  # 行尾\n\ns = "# 保留"\n', encoding="utf-8")
    (root / "src" / "util.py").write_bytes("中文 = 1  # 中文注释\n".encode("gbk"))
    (root / "data.zzz").write_text("无规则文件原样保留", encoding="utf-8")
    (root / "broken.py").write_bytes(b"\xff\xff\xff")
    return root


@pytest.fixture()
def pipeline() -> ExportPipeline:
    """基于真实内置规则的导出流水线（内存态规则存储）"""
    return ExportPipeline(RuleStore(PLUGIN_DIR))


class TestExportPipeline:
    """导出流水线端到端行为"""

    def test_end_to_end(self, pipeline, project_root, tmp_path):
        ordered = ["main.py", "src/util.py", "data.zzz", "broken.py", "ghost.py"]
        output = tmp_path / "out.docx"
        result = pipeline.run(project_root, ordered, output)
        assert result["file_count"] == 3
        assert result["unmatched"] == ["data.zzz"]
        assert result["skipped"] == ["broken.py", "ghost.py"]
        texts = _read_doc_texts(output)
        assert texts[0] == PROJECT_NAME
        main_index = texts.index("main.py")
        assert texts[main_index + 1: main_index + 4] == ["x = 1", "", 's = "# 保留"']
        util_index = texts.index("src/util.py")
        assert texts[util_index + 1] == "中文 = 1"
        data_index = texts.index("data.zzz")
        assert texts[data_index + 1] == "无规则文件原样保留"

    def test_keep_unmatched_false_excludes_file(self, pipeline, project_root, tmp_path):
        output = tmp_path / "out.docx"
        result = pipeline.run(
            project_root, ["main.py", "data.zzz"], output, keep_unmatched=False)
        assert result["file_count"] == 1
        assert result["unmatched"] == ["data.zzz"]
        assert "data.zzz" not in _read_doc_texts(output)

    def test_progress_callback_invoked(self, pipeline, project_root, tmp_path):
        calls: list[tuple] = []
        pipeline.run(
            project_root, ["main.py", "data.zzz"], tmp_path / "out.docx",
            progress=lambda *args: calls.append(args))
        assert calls[0] == ("main.py", 0, 2)
        assert calls[-1] == ("", 2, 2)

    def test_progress_callback_error_isolated(self, pipeline, project_root, tmp_path):
        def _bad_progress(*_args):
            raise RuntimeError("回调异常不应中断导出")

        output = tmp_path / "out.docx"
        result = pipeline.run(project_root, ["main.py"], output, progress=_bad_progress)
        assert result["file_count"] == 1
        assert output.exists()

    def test_output_unwritable_raises(self, pipeline, project_root, tmp_path):
        with pytest.raises(OSError):
            pipeline.run(
                project_root, ["main.py"], tmp_path / "不存在的目录" / "out.docx")

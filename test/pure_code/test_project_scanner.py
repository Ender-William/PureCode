"""PureCode 目录扫描器单元测试（function/project_scanner.py）"""

from pathlib import Path

import pytest

from pure_code.function.project_scanner import ProjectScanner


def _touch(path: Path) -> None:
    """创建包含占位内容的文件（含父目录）"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")


class TestScan:
    """目录扫描：默认顺序、扩展名统计与跳过清单"""

    def test_default_order_depth_first_alpha(self, tmp_path: Path):
        _touch(tmp_path / "b.py")
        _touch(tmp_path / "A.py")
        _touch(tmp_path / "sub" / "c.py")
        _touch(tmp_path / "sub" / "a.txt")
        result = ProjectScanner().scan(tmp_path)
        assert result.files == ["A.py", "b.py", "sub/a.txt", "sub/c.py"]

    def test_extension_counts(self, tmp_path: Path):
        _touch(tmp_path / "a.py")
        _touch(tmp_path / "b.PY")
        _touch(tmp_path / "c.txt")
        _touch(tmp_path / "README")
        result = ProjectScanner().scan(tmp_path)
        assert result.extension_counts == {".py": 2, ".txt": 1, "": 1}

    def test_skip_dirs_excluded(self, tmp_path: Path):
        _touch(tmp_path / ".git" / "x.py")
        _touch(tmp_path / "node_modules" / "y.py")
        _touch(tmp_path / "__pycache__" / "z.py")
        _touch(tmp_path / "keep.py")
        result = ProjectScanner().scan(tmp_path)
        assert result.files == ["keep.py"]

    def test_empty_directory(self, tmp_path: Path):
        result = ProjectScanner().scan(tmp_path)
        assert result.files == []
        assert result.extension_counts == {}

    def test_file_path_raises(self, tmp_path: Path):
        target = tmp_path / "a.py"
        _touch(target)
        with pytest.raises(NotADirectoryError):
            ProjectScanner().scan(target)

    def test_missing_path_raises(self, tmp_path: Path):
        with pytest.raises(NotADirectoryError):
            ProjectScanner().scan(tmp_path / "不存在")


class TestFilterByExtensions:
    """文件类型粗选过滤"""

    def test_filter_keeps_order_and_case_insensitive(self):
        files = ["a.py", "b.txt", "c", "D.PY"]
        scanner = ProjectScanner()
        assert scanner.filter_by_extensions(files, {".py"}) == ["a.py", "D.PY"]

    def test_filter_no_extension(self):
        files = ["a.py", "README"]
        scanner = ProjectScanner()
        assert scanner.filter_by_extensions(files, {""}) == ["README"]

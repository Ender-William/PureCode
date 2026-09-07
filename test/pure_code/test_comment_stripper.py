"""PureCode 去注释引擎单元测试（function/comment_stripper.py）"""

from pure_code.function.comment_stripper import CommentStripper
from pure_code.function.models import normalize_rule


def _python_rule() -> dict:
    """Python 风格规则：# 单行注释 + 三种字符串界定符"""
    return normalize_rule({
        "name": "Python",
        "extensions": ["py"],
        "line_comments": ["#"],
        "string_delimiters": ['"""', '"', "'"],
    })


def _c_rule(nested: bool = False) -> dict:
    """C 风格规则：// 单行 + /* */ 块注释，可开关嵌套"""
    return normalize_rule({
        "name": "C",
        "extensions": ["c"],
        "line_comments": ["//"],
        "block_comments": [["/*", "*/"]],
        "string_delimiters": ['"'],
        "nested_block": nested,
    })


class TestLineComments:
    """单行注释剥离与行语义"""

    def test_trailing_and_full_line_comments(self):
        source = "# 头部注释\nx = 1  # 行尾注释\n\n# 独占一行\ny = 2\n"
        assert CommentStripper().strip(source, _python_rule()) == "x = 1\n\ny = 2"

    def test_comment_marker_inside_string_preserved(self):
        source = 'url = "http://a#b"  # 真正的注释\n'
        assert CommentStripper().strip(source, _python_rule()) == 'url = "http://a#b"'

    def test_docstring_preserved_as_string(self):
        source = '"""模块 docstring # 不是注释"""\nx = 1\n'
        expected = '"""模块 docstring # 不是注释"""\nx = 1'
        assert CommentStripper().strip(source, _python_rule()) == expected

    def test_escaped_quote_inside_string(self):
        source = 's = "a\\" # 仍在字符串内" # 真注释\n'
        expected = 's = "a\\" # 仍在字符串内"'
        assert CommentStripper().strip(source, _python_rule()) == expected

    def test_crlf_normalized_to_lf(self):
        source = "a = 1  # c\r\nb = 2\r\n"
        assert CommentStripper().strip(source, _python_rule()) == "a = 1\nb = 2"

    def test_no_trailing_newline(self):
        assert CommentStripper().strip("x = 1", _python_rule()) == "x = 1"

    def test_empty_source(self):
        assert CommentStripper().strip("", _python_rule()) == ""


class TestBlockComments:
    """块注释剥离、嵌套与字符串优先级"""

    def test_block_comment_spanning_lines(self):
        source = "/* 块注释\n   跨行 */\nint a;\n"
        assert CommentStripper().strip(source, _c_rule()) == "int a;"

    def test_inline_block_comment_keeps_code(self):
        source = "int a; /* 注释 */ int b;\n"
        assert CommentStripper().strip(source, _c_rule()) == "int a;  int b;"

    def test_comment_tokens_inside_string_preserved(self):
        source = 'char *s = "a//b /* c */";\n'
        assert CommentStripper().strip(source, _c_rule()) == 'char *s = "a//b /* c */";'

    def test_nested_block_comment(self):
        source = "a /* x /* y */ z */ b\n"
        assert CommentStripper().strip(source, _c_rule(nested=True)) == "a  b"

    def test_non_nested_block_ends_at_first_close(self):
        source = "a /* x /* y */ z */ b\n"
        assert CommentStripper().strip(source, _c_rule()) == "a  z */ b"

    def test_unterminated_block_drops_tail(self):
        source = "a = 1; /* 未闭合\nb = 2;"
        assert CommentStripper().strip(source, _c_rule()) == "a = 1;"

    def test_unterminated_string_kept(self):
        assert CommentStripper().strip('s = "abc', _c_rule()) == 's = "abc'

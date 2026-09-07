"""PureCode 规则数据模型单元测试（function/models.py）"""

from pure_code.function.models import (
    DEFAULT_ESCAPE_CHAR,
    normalize_extension,
    normalize_rule,
    validate_rule,
)


def _valid_rule() -> dict:
    """构造一条可通过校验的最小规则（仅单行注释）"""
    return {
        "name": "Demo",
        "extensions": ["py"],
        "line_comments": ["#"],
    }


class TestNormalizeExtension:
    """扩展名规范化"""

    def test_lowercase(self):
        assert normalize_extension("PY") == ".py"

    def test_adds_leading_dot(self):
        assert normalize_extension("py") == ".py"

    def test_strips_whitespace(self):
        assert normalize_extension("  .Txt ") == ".txt"


class TestValidateRule:
    """规则校验：正常路径与各类非法输入"""

    def test_valid_minimal_rule(self):
        assert validate_rule(_valid_rule()) == []

    def test_valid_block_only_rule(self):
        rule = {
            "name": "C",
            "extensions": [".c"],
            "block_comments": [["/*", "*/"]],
        }
        assert validate_rule(rule) == []

    def test_non_dict_rejected(self):
        assert validate_rule("not-a-dict") == ["规则必须是字典对象"]

    def test_empty_name_rejected(self):
        rule = _valid_rule()
        rule["name"] = "   "
        assert "语言名称不能为空" in validate_rule(rule)

    def test_empty_extensions_rejected(self):
        rule = _valid_rule()
        rule["extensions"] = []
        assert "扩展名列表不能为空" in validate_rule(rule)

    def test_non_string_extension_rejected(self):
        rule = _valid_rule()
        rule["extensions"] = [".py", 42]
        assert "扩展名必须为非空字符串" in validate_rule(rule)

    def test_no_comment_tokens_rejected(self):
        rule = {"name": "X", "extensions": [".x"]}
        assert "单行注释符与块注释符至少配置一项" in validate_rule(rule)

    def test_invalid_block_pair_rejected(self):
        rule = _valid_rule()
        rule["block_comments"] = [["/*"]]
        assert "块注释符必须为由起止两个非空字符串组成的对" in validate_rule(rule)

    def test_empty_string_delimiter_rejected(self):
        rule = _valid_rule()
        rule["string_delimiters"] = ['"', ""]
        assert "字符串界定符必须为非空字符串" in validate_rule(rule)

    def test_empty_escape_char_rejected(self):
        rule = _valid_rule()
        rule["escape_char"] = "  "
        assert "转义符必须为非空字符串" in validate_rule(rule)


class TestNormalizeRule:
    """规则规范化：字段裁剪、默认值与扩展名处理"""

    def test_unknown_fields_dropped(self):
        rule = {**_valid_rule(), "extra_field": "应被丢弃"}
        normalized = normalize_rule(rule)
        assert "extra_field" not in normalized

    def test_extensions_normalized_deduped_sorted(self):
        rule = _valid_rule()
        rule["extensions"] = ["PY", ".py", "Txt"]
        normalized = normalize_rule(rule)
        assert normalized["extensions"] == [".py", ".txt"]

    def test_defaults_filled(self):
        normalized = normalize_rule(_valid_rule())
        assert normalized["escape_char"] == DEFAULT_ESCAPE_CHAR
        assert normalized["nested_block"] is False
        assert normalized["block_comments"] == []

    def test_name_stripped(self):
        rule = _valid_rule()
        rule["name"] = "  Demo  "
        assert normalize_rule(rule)["name"] == "Demo"

    def test_input_not_mutated(self):
        rule = _valid_rule()
        rule["extensions"] = ["PY"]
        normalize_rule(rule)
        assert rule["extensions"] == ["PY"]

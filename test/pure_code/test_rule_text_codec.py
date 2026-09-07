"""PureCode 规则文本编解码单元测试（function/rule_text_codec.py）"""

from pure_code.function.rule_text_codec import (
    format_block_pairs,
    format_tokens,
    parse_block_pairs,
    parse_tokens,
)


class TestTokens:
    """记号列表与空格分隔文本的双向转换"""

    def test_format_tokens(self):
        assert format_tokens(["//", "#"]) == "// #"

    def test_parse_tokens(self):
        assert parse_tokens("//  #") == ["//", "#"]

    def test_parse_tokens_drops_blank_segments(self):
        assert parse_tokens("  //   #  ") == ["//", "#"]

    def test_roundtrip(self):
        tokens = ["'''", '"""', "'"]
        assert parse_tokens(format_tokens(tokens)) == tokens


class TestBlockPairs:
    """块注释起止对的编解码"""

    def test_format_block_pairs(self):
        assert format_block_pairs([["/*", "*/"], ["<!--", "-->"]]) == "/* */ <!-- -->"

    def test_parse_block_pairs(self):
        assert parse_block_pairs("/* */ <!-- -->") == [["/*", "*/"], ["<!--", "-->"]]

    def test_parse_odd_tokens_returns_none(self):
        assert parse_block_pairs("/* */ <!--") is None

    def test_parse_empty_text(self):
        assert parse_block_pairs("") == []

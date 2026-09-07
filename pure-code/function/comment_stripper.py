"""
PureCode 去注释引擎

规则驱动的单遍扫描状态机：由 LanguageRule 数据（见 function/models.py）
完全决定词法行为，不硬编码任何具体语言——新增语言只需新增规则数据。

设计要点：
- 状态四态：NORMAL / IN_STRING / IN_LINE_COMMENT / IN_BLOCK_COMMENT；
- 同位置记号冲突时按「行首文档字符串 → 字符串界定符 → 单行注释 →
  块注释」优先级匹配，同类多记号按最长匹配优先（引擎内部固定策略，
  由规则数据预编译排序）；
- 行首文档字符串启发式：docstrings 字段中的界定符仅在当前行已扫描
  部分为纯空白（行首/仅缩进）时按块注释剥离；赋值或参数位置出现的
  同一界定符仍按字符串处理（词法上二者无法严格区分，此为折中）；
- 字符串字面量内容（含换行）原样保留，防止误删字符串内的注释符；
- 块注释内换行保留行边界（注释产生的空行随后按行语义丢弃）；
- 行语义：剥离后整行为空且该行曾含注释 → 丢弃整行；原始空行保留；
  行尾注释剥离后去除尾部空白。
"""

from enum import Enum, auto

from .models import (
    FIELD_BLOCK_COMMENTS,
    FIELD_DOCSTRINGS,
    FIELD_ESCAPE_CHAR,
    FIELD_LINE_COMMENTS,
    FIELD_NESTED_BLOCK,
    FIELD_STRING_DELIMITERS,
)


class _State(Enum):
    """扫描状态枚举"""

    NORMAL = auto()
    IN_STRING = auto()
    IN_LINE_COMMENT = auto()
    IN_BLOCK_COMMENT = auto()


class _StripSession:
    """
    单文件剥离会话（内部实现）

    持有规则编译产物与扫描状态，经状态→处理方法的分发表驱动扫描，
    避免 if-elif 长链与布尔标志堆砌。
    """

    def __init__(self, rule: dict) -> None:
        """
        编译规则为按长度降序的记号表（最长匹配优先）

        Args:
            rule: 生效语言规则（须已通过 models.validate_rule）
        """
        self._string_delims = sorted(
            rule[FIELD_STRING_DELIMITERS], key=len, reverse=True)
        self._docstring_delims = sorted(
            rule.get(FIELD_DOCSTRINGS) or [], key=len, reverse=True)
        self._line_tokens = sorted(
            rule[FIELD_LINE_COMMENTS], key=len, reverse=True)
        self._block_pairs = sorted(
            rule[FIELD_BLOCK_COMMENTS], key=lambda pair: len(pair[0]), reverse=True)
        self._escape = rule[FIELD_ESCAPE_CHAR]
        self._nested = bool(rule[FIELD_NESTED_BLOCK])
        self._state = _State.NORMAL
        self._string_end = ""
        self._block_start = ""
        self._block_end = ""
        self._block_depth = 0
        self._line_buf: list[str] = []
        self._out_lines: list[str] = []
        self._had_comment = False
        self._source = ""

    def run(self, source: str) -> str:
        """
        执行剥离扫描

        Args:
            source: 源码文本

        Returns:
            剥离注释后的文本（行尾统一为 \n）
        """
        self._source = source
        handlers = {
            _State.NORMAL: self._step_normal,
            _State.IN_STRING: self._step_in_string,
            _State.IN_LINE_COMMENT: self._step_in_line_comment,
            _State.IN_BLOCK_COMMENT: self._step_in_block_comment,
        }
        index = 0
        while index < len(source):
            index = handlers[self._state](index)
        if self._line_buf or self._had_comment:
            self._flush_line()
        return "\n".join(self._out_lines)

    def _step_normal(self, index: int) -> int:
        """NORMAL 态：识别字符串/注释入口，其余字符原样输出"""
        if self._source[index] == "\n":
            self._flush_line()
            return index + 1
        entry_matchers = (
            self._try_enter_docstring,
            self._try_enter_string,
            self._try_enter_line_comment,
            self._try_enter_block_comment,
        )
        for matcher in entry_matchers:
            next_index = matcher(index)
            if next_index is not None:
                return next_index
        self._emit(self._source[index])
        return index + 1

    def _try_enter_docstring(self, index: int) -> "int | None":
        """行首启发式：当前行仅空白时，文档字符串界定符按块注释剥离"""
        delimiter = self._match_token(self._docstring_delims, index)
        if not delimiter or not self._line_so_far_blank():
            return None
        return self._enter_block_comment(index, delimiter, delimiter)

    def _try_enter_string(self, index: int) -> "int | None":
        """命中字符串界定符则进入字符串态（内容原样保留）"""
        delimiter = self._match_token(self._string_delims, index)
        if not delimiter:
            return None
        self._emit(delimiter)
        self._state = _State.IN_STRING
        self._string_end = delimiter
        return index + len(delimiter)

    def _try_enter_line_comment(self, index: int) -> "int | None":
        """命中单行注释符则进入行注释态"""
        token = self._match_token(self._line_tokens, index)
        if not token:
            return None
        self._had_comment = True
        self._state = _State.IN_LINE_COMMENT
        return index + len(token)

    def _try_enter_block_comment(self, index: int) -> "int | None":
        """命中块注释起始符则进入块注释态"""
        pair = self._match_block_start(index)
        if not pair:
            return None
        return self._enter_block_comment(index, pair[0], pair[1])

    def _enter_block_comment(self, index: int, start: str, end: str) -> int:
        """进入块注释态并返回起始符之后的索引"""
        self._had_comment = True
        self._state = _State.IN_BLOCK_COMMENT
        self._block_start, self._block_end = start, end
        self._block_depth = 1
        return index + len(start)

    def _line_so_far_blank(self) -> bool:
        """判断当前行已扫描部分是否为纯空白（行首启发式依据）"""
        return not "".join(self._line_buf).strip()

    def _step_in_string(self, index: int) -> int:
        """IN_STRING 态：字符串内容原样保留，处理转义与闭合定界符"""
        if self._escape and self._source.startswith(self._escape, index):
            end = min(index + len(self._escape) + 1, len(self._source))
            self._emit(self._source[index:end])  # 转义符与转义字符原样保留
            return end
        if self._source.startswith(self._string_end, index):
            self._emit(self._string_end)
            self._state = _State.NORMAL
            return index + len(self._string_end)
        self._emit(self._source[index])
        return index + 1

    def _step_in_line_comment(self, index: int) -> int:
        """IN_LINE_COMMENT 态：吞掉注释内容，遇换行结束并冲刷该行"""
        if self._source[index] == "\n":
            self._flush_line()
            self._state = _State.NORMAL
        return index + 1

    def _step_in_block_comment(self, index: int) -> int:
        """IN_BLOCK_COMMENT 态：吞掉注释内容，支持嵌套计数，保留换行行边界"""
        # 块注释可跨行：持续标记当前行含注释，保证注释致空的行被丢弃
        self._had_comment = True
        if self._source[index] == "\n":
            self._flush_line()
            return index + 1
        # 起止符相同（文档字符串）时禁止嵌套计数，否则起始符会被误计为嵌套
        # 导致永远无法闭合
        if (self._nested and self._block_start != self._block_end
                and self._source.startswith(self._block_start, index)):
            self._block_depth += 1
            return index + len(self._block_start)
        if self._source.startswith(self._block_end, index):
            self._block_depth -= 1
            if self._block_depth == 0:
                self._state = _State.NORMAL
            return index + len(self._block_end)
        return index + 1

    def _match_token(self, tokens: list[str], index: int) -> "str | None":
        """在指定位置按最长匹配优先命中记号表中的任一记号为字符串界定符/单行注释符"""
        for token in tokens:
            if self._source.startswith(token, index):
                return token
        return None

    def _match_block_start(self, index: int) -> "list | None":
        """在指定位置命中块注释起始符，返回对应起止对"""
        for pair in self._block_pairs:
            if self._source.startswith(pair[0], index):
                return pair
        return None

    def _emit(self, text: str) -> None:
        """向当前行缓冲追加输出文本"""
        self._line_buf.append(text)

    def _flush_line(self) -> None:
        """
        冲刷当前行：内容非空则保留（去尾部空白）；注释致空的行丢弃；
        原始空行原样保留
        """
        text = "".join(self._line_buf)
        if text.strip():
            self._out_lines.append(text.rstrip())
        elif not self._had_comment:
            self._out_lines.append("")
        self._line_buf = []
        self._had_comment = False


class CommentStripper:
    """
    去注释引擎门面

    对每个源文件创建一次扫描会话执行剥离；纯内存处理，不修改原文件。
    无匹配规则的文件由调用方决定原样保留或跳过（引擎不处理）。
    """

    def strip(self, source: str, rule: dict) -> str:
        """
        按语言规则剥离源码注释

        Args:
            source: 源码文本
            rule: 生效语言规则（字段见 function/models.py）

        Returns:
            剥离注释后的文本
        """
        return _StripSession(rule).run(source)

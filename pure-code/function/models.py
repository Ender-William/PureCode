"""
PureCode 语言注释规则数据模型

LanguageRule 以纯 dict 表示（保证 JSON 可序列化，便于 DataProvider 持久化
与 config/default_rules.json 发布）。本模块提供字段常量、规则校验与
规范化能力，供规则存储、去注释引擎与语言设置界面共用。
"""

from typing import Any

# ===== 规则字段名常量 =====
FIELD_NAME = "name"
FIELD_EXTENSIONS = "extensions"
FIELD_LINE_COMMENTS = "line_comments"
FIELD_BLOCK_COMMENTS = "block_comments"
FIELD_STRING_DELIMITERS = "string_delimiters"
FIELD_DOCSTRINGS = "docstrings"
FIELD_ESCAPE_CHAR = "escape_char"
FIELD_NESTED_BLOCK = "nested_block"
FIELD_BUILTIN = "builtin"

# ===== 默认值与结构常量 =====
DEFAULT_ESCAPE_CHAR = "\\"
BLOCK_COMMENT_PAIR_SIZE = 2


def validate_rule(rule: Any) -> list[str]:
    """
    校验语言规则的完整性与合法性

    Args:
        rule: 待校验的规则数据（期望 dict）

    Returns:
        中文错误信息列表，空列表表示校验通过
    """
    if not isinstance(rule, dict):
        return ["规则必须是字典对象"]
    errors: list[str] = []
    if not _is_non_empty_str(rule.get(FIELD_NAME)):
        errors.append("语言名称不能为空")
    errors.extend(_validate_extensions(rule.get(FIELD_EXTENSIONS)))
    errors.extend(_validate_comment_tokens(rule))
    errors.extend(_validate_string_fields(rule))
    return errors


def normalize_rule(rule: dict) -> dict:
    """
    规范化规则：仅保留已知字段、补默认值、扩展名统一小写并补前导点

    Args:
        rule: 已通过 validate_rule 校验的规则

    Returns:
        规范化后的新规则 dict（不修改入参）
    """
    extensions = [normalize_extension(ext) for ext in rule[FIELD_EXTENSIONS]]
    return {
        FIELD_NAME: str(rule[FIELD_NAME]).strip(),
        FIELD_EXTENSIONS: sorted(set(extensions)),
        FIELD_LINE_COMMENTS: list(rule.get(FIELD_LINE_COMMENTS) or []),
        FIELD_BLOCK_COMMENTS: [list(pair) for pair in rule.get(FIELD_BLOCK_COMMENTS) or []],
        FIELD_STRING_DELIMITERS: list(rule.get(FIELD_STRING_DELIMITERS) or []),
        FIELD_DOCSTRINGS: list(rule.get(FIELD_DOCSTRINGS) or []),
        FIELD_ESCAPE_CHAR: rule.get(FIELD_ESCAPE_CHAR) or DEFAULT_ESCAPE_CHAR,
        FIELD_NESTED_BLOCK: bool(rule.get(FIELD_NESTED_BLOCK, False)),
    }


def normalize_extension(extension: str) -> str:
    """
    规范化扩展名：转小写并确保以点开头

    Args:
        extension: 原始扩展名（如 "PY"、"py"、".py"）

    Returns:
        规范化扩展名（如 ".py"）
    """
    ext = extension.strip().lower()
    return ext if ext.startswith(".") else f".{ext}"


def _is_non_empty_str(value: Any) -> bool:
    """判断值是否为非空字符串（strip 后非空）"""
    return isinstance(value, str) and bool(value.strip())


def _validate_extensions(value: Any) -> list[str]:
    """校验扩展名字段：必须为非空字符串组成的非空列表"""
    if not isinstance(value, list) or not value:
        return ["扩展名列表不能为空"]
    if not all(_is_non_empty_str(item) for item in value):
        return ["扩展名必须为非空字符串"]
    return []


def _validate_comment_tokens(rule: dict) -> list[str]:
    """校验注释符字段：单行/块注释至少配置一项，块注释须为起止对"""
    lines = rule.get(FIELD_LINE_COMMENTS) or []
    blocks = rule.get(FIELD_BLOCK_COMMENTS) or []
    if not isinstance(lines, list) or not isinstance(blocks, list):
        return ["注释符配置必须为列表"]
    if not lines and not blocks:
        return ["单行注释符与块注释符至少配置一项"]
    errors: list[str] = []
    if not all(_is_non_empty_str(token) for token in lines):
        errors.append("单行注释符必须为非空字符串")
    if not all(_is_valid_block_pair(pair) for pair in blocks):
        errors.append("块注释符必须为由起止两个非空字符串组成的对")
    return errors


def _is_valid_block_pair(pair: Any) -> bool:
    """校验单个块注释起止对"""
    return (
        isinstance(pair, (list, tuple))
        and len(pair) == BLOCK_COMMENT_PAIR_SIZE
        and all(_is_non_empty_str(token) for token in pair)
    )


def _validate_string_fields(rule: dict) -> list[str]:
    """校验字符串界定符、文档字符串界定符与转义符字段"""
    errors = _validate_token_list(rule.get(FIELD_STRING_DELIMITERS), "字符串界定符")
    errors.extend(_validate_token_list(rule.get(FIELD_DOCSTRINGS), "文档字符串界定符"))
    escape = rule.get(FIELD_ESCAPE_CHAR, DEFAULT_ESCAPE_CHAR)
    if not _is_non_empty_str(escape):
        errors.append("转义符必须为非空字符串")
    return errors


def _validate_token_list(value: Any, label: str) -> list[str]:
    """校验可选记号列表字段：缺省合法；存在时须为非空字符串列表"""
    if value is None:
        return []
    if not isinstance(value, list):
        return [f"{label}必须为列表"]
    if not all(_is_non_empty_str(item) for item in value):
        return [f"{label}必须为非空字符串"]
    return []

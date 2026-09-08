"""
PureCode 语言规则文本编解码

语言设置表单中「空格分隔」文本与规则列表字段之间的双向转换。
纯函数模块，与视图解耦，便于独立测试。
"""


def format_tokens(tokens: list[str]) -> str:
    """
    记号列表 → 空格分隔文本

    Args:
        tokens: 记号列表（如单行注释符、扩展名）

    Returns:
        空格分隔的文本
    """
    return " ".join(tokens)


def parse_tokens(text: str) -> list[str]:
    """
    空格分隔文本 → 记号列表（空白片段自动剔除）

    Args:
        text: 用户输入文本

    Returns:
        记号列表
    """
    return [part for part in text.split() if part]


def format_block_pairs(pairs: list[list[str]]) -> str:
    """
    块注释起止对列表 → 空格分隔文本（起 止 起 止 …）

    Args:
        pairs: 起止对列表，如 [["/*", "*/"]]

    Returns:
        空格分隔文本，如 "/* */"
    """
    return " ".join(f"{start} {end}" for start, end in pairs)


def parse_block_pairs(text: str) -> "list[list[str]] | None":
    """
    空格分隔文本 → 块注释起止对列表

    Args:
        text: 用户输入文本（记号两两成对）

    Returns:
        起止对列表；记号总数为奇数（无法成对）时返回 None
    """
    tokens = parse_tokens(text)
    if len(tokens) % 2 != 0:
        return None
    return [[tokens[i], tokens[i + 1]] for i in range(0, len(tokens), 2)]

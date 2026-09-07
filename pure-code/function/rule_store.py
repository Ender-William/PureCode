"""
PureCode 语言注释规则存储

负责内置规则加载（插件 config/default_rules.json，随插件发布只读）、
用户自定义规则持久化（框架 DataProvider PRIVATE 命名空间）以及二者合并
（同名规则用户覆盖优先）。
"""

import json
from pathlib import Path

from core.data.data_provider import DataProviderError
from core.interfaces import DataNamespace, IDataProvider
from utils.i_logger import ILogger

from .models import (
    FIELD_BUILTIN,
    FIELD_EXTENSIONS,
    FIELD_NAME,
    normalize_extension,
    normalize_rule,
    validate_rule,
)

# ===== 常量 =====
DEFAULT_RULES_RELATIVE_PATH = Path("config") / "default_rules.json"
USER_OVERRIDES_KEY = "language_rule_overrides"
MODULE_NAME = "pure-code.rule_store"


class RuleStore:
    """
    语言注释规则注册表

    内置规则随插件发布只读；用户可新增语言或覆盖内置语言，
    覆盖数据经 DataProvider 持久化（插件卸载时可随数据清除）。
    DataProvider 不可用时降级为仅内存态并记日志，不影响主流程。
    """

    def __init__(
        self,
        plugin_dir: Path,
        data_provider: "IDataProvider | None" = None,
        plugin_id: "str | None" = None,
        logger: "ILogger | None" = None,
    ) -> None:
        """
        初始化规则存储并加载内置规则与用户覆盖

        Args:
            plugin_dir: 插件目录路径（定位 config/default_rules.json）
            data_provider: 框架数据提供者，可为 None（降级为内存态）
            plugin_id: 插件 UUID（DataProvider 命名空间隔离依据）
            logger: 框架日志器，可为 None
        """
        self._plugin_dir = Path(plugin_dir)
        self._data_provider = data_provider
        self._plugin_id = plugin_id
        self._logger = logger
        self._builtin_rules: list[dict] = self._load_builtin_rules()
        self._user_overrides: list[dict] = self._load_user_overrides()

    def effective_rules(self) -> list[dict]:
        """
        合并内置规则与用户覆盖（同名用户优先），标注 builtin 来源标记

        Returns:
            生效规则副本列表（修改返回值不影响存储内部状态）
        """
        merged: dict[str, dict] = {}
        for rule in self._builtin_rules:
            merged[rule[FIELD_NAME]] = {**rule, FIELD_BUILTIN: True}
        for rule in self._user_overrides:
            is_builtin = rule[FIELD_NAME] in merged
            merged[rule[FIELD_NAME]] = {**rule, FIELD_BUILTIN: is_builtin}
        return list(merged.values())

    def rule_for_extension(self, extension: str) -> "dict | None":
        """
        按扩展名查找生效规则（大小写不敏感、可省略前导点）

        Args:
            extension: 文件扩展名，如 "py" 或 ".PY"

        Returns:
            命中的规则 dict（含 builtin 标记），未命中返回 None
        """
        ext = normalize_extension(extension)
        for rule in self.effective_rules():
            if ext in rule[FIELD_EXTENSIONS]:
                return rule
        return None

    def save_user_rule(self, rule: dict) -> list[str]:
        """
        新增或覆盖语言规则并持久化（同名覆盖内置规则即为「用户覆盖」）

        Args:
            rule: 规则数据（未校验亦可，内部先校验再规范化）

        Returns:
            中文校验错误列表，空列表表示保存成功
        """
        errors = validate_rule(rule)
        if errors:
            return errors
        normalized = normalize_rule(rule)
        self._user_overrides = [
            item for item in self._user_overrides
            if item[FIELD_NAME] != normalized[FIELD_NAME]
        ]
        self._user_overrides.append(normalized)
        self._persist_overrides()
        return []

    def delete_language(self, name: str) -> bool:
        """
        删除用户新增的自定义语言（内置语言不可删除，应使用 restore_builtin）

        Args:
            name: 语言名称

        Returns:
            是否删除成功
        """
        if self.is_builtin(name):
            return False
        return self._remove_override(name)

    def restore_builtin(self, name: str) -> bool:
        """
        恢复内置语言默认规则（删除该语言的用户覆盖）

        Args:
            name: 内置语言名称

        Returns:
            是否恢复成功（语言非内置或本就无法覆盖时返回 False）
        """
        if not self.is_builtin(name):
            return False
        return self._remove_override(name)

    def is_builtin(self, name: str) -> bool:
        """判断指定名称是否为内置语言"""
        return any(rule[FIELD_NAME] == name for rule in self._builtin_rules)

    def is_overridden(self, name: str) -> bool:
        """判断指定语言当前是否被用户规则覆盖"""
        return any(rule[FIELD_NAME] == name for rule in self._user_overrides)

    def _remove_override(self, name: str) -> bool:
        """从用户覆盖中移除指定名称并持久化，返回是否有变更"""
        before = len(self._user_overrides)
        self._user_overrides = [
            item for item in self._user_overrides if item[FIELD_NAME] != name
        ]
        if len(self._user_overrides) == before:
            return False
        self._persist_overrides()
        return True

    def _load_builtin_rules(self) -> list[dict]:
        """加载并规范化内置规则文件，文件缺失/损坏时降级为空并记日志"""
        path = self._plugin_dir / DEFAULT_RULES_RELATIVE_PATH
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._log_error(f"内置语言规则加载失败: {path}（{exc}）")
            return []
        rules = raw.get("rules") if isinstance(raw, dict) else None
        return self._normalize_rule_list(rules if isinstance(rules, list) else [], "内置")

    def _load_user_overrides(self) -> list[dict]:
        """从 DataProvider 读取用户覆盖规则，不可用时降级为空并记日志"""
        if self._data_provider is None or not self._plugin_id:
            return []
        try:
            raw = self._data_provider.get_plugin_data(
                self._plugin_id, USER_OVERRIDES_KEY, DataNamespace.PRIVATE, default=[]
            )
        except DataProviderError as exc:
            self._log_error(f"用户语言规则读取失败: {exc}")
            return []
        return self._normalize_rule_list(raw if isinstance(raw, list) else [], "用户")

    def _normalize_rule_list(self, raw_rules: list, source: str) -> list[dict]:
        """校验并规范化规则列表，非法条目跳过并记 WARNING"""
        normalized: list[dict] = []
        for item in raw_rules:
            errors = validate_rule(item)
            if errors:
                name = item.get(FIELD_NAME) if isinstance(item, dict) else item
                self._log_warning(f"{source}规则「{name}」非法已跳过: {'；'.join(errors)}")
                continue
            normalized.append(normalize_rule(item))
        return normalized

    def _persist_overrides(self) -> None:
        """持久化用户覆盖规则，DataProvider 不可用时仅保留内存态并记日志"""
        if self._data_provider is None or not self._plugin_id:
            self._log_warning("DataProvider 不可用，用户语言规则仅保留在内存")
            return
        try:
            self._data_provider.set_plugin_data(
                self._plugin_id,
                USER_OVERRIDES_KEY,
                self._user_overrides,
                DataNamespace.PRIVATE,
                notify=False,
            )
        except DataProviderError as exc:
            self._log_error(f"用户语言规则保存失败: {exc}")

    def _log_warning(self, message: str) -> None:
        """记录 WARNING 日志（logger 缺失时静默降级）"""
        if self._logger is not None:
            self._logger.warning(MODULE_NAME, message)

    def _log_error(self, message: str) -> None:
        """记录 ERROR 日志（logger 缺失时静默降级）"""
        if self._logger is not None:
            self._logger.error(MODULE_NAME, message)

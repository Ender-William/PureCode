"""PureCode 规则存储单元测试（function/rule_store.py）"""

import json
from pathlib import Path

import pytest

from core.data import DataProvider
from pure_code.function.rule_store import RuleStore

PLUGIN_ID = "test-pure-code-uuid"

BUILTIN_PAYLOAD = {
    "rules": [
        {
            "name": "Python",
            "extensions": ["py", "pyw"],
            "line_comments": ["#"],
            "string_delimiters": ['"""', '"', "'"],
        },
        {
            "name": "C",
            "extensions": ["c", "h"],
            "line_comments": ["//"],
            "block_comments": [["/*", "*/"]],
            "string_delimiters": ['"'],
        },
    ]
}


def _go_rule() -> dict:
    """构造一条用户新增语言规则"""
    return {
        "name": "Go",
        "extensions": ["go"],
        "line_comments": ["//"],
        "block_comments": [["/*", "*/"]],
        "string_delimiters": ['"', "`"],
    }


@pytest.fixture()
def plugin_dir(tmp_path: Path) -> Path:
    """构造含内置规则的临时插件目录"""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "default_rules.json").write_text(
        json.dumps(BUILTIN_PAYLOAD), encoding="utf-8")
    return tmp_path


@pytest.fixture()
def data_provider(tmp_path: Path):
    """临时目录的 DataProvider 实例（测试前后重置单例）"""
    DataProvider._instance = None
    provider = DataProvider(data_dir=str(tmp_path / "db"), data_filename="test.json")
    yield provider
    DataProvider._instance = None


class TestBuiltinRules:
    """内置规则加载与查询"""

    def test_builtin_loaded_and_marked(self, plugin_dir):
        store = RuleStore(plugin_dir)
        names = {rule["name"] for rule in store.effective_rules()}
        assert names == {"Python", "C"}
        assert all(rule["builtin"] for rule in store.effective_rules())

    def test_rule_for_extension_case_insensitive(self, plugin_dir):
        store = RuleStore(plugin_dir)
        assert store.rule_for_extension("PY")["name"] == "Python"
        assert store.rule_for_extension(".H")["name"] == "C"
        assert store.rule_for_extension("java") is None

    def test_missing_builtin_file_degrades(self, tmp_path):
        store = RuleStore(tmp_path)
        assert store.effective_rules() == []

    def test_invalid_builtin_entry_skipped(self, tmp_path):
        payload = {"rules": [BUILTIN_PAYLOAD["rules"][0], {"name": "坏规则"}]}
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "default_rules.json").write_text(
            json.dumps(payload), encoding="utf-8")
        store = RuleStore(tmp_path)
        assert [rule["name"] for rule in store.effective_rules()] == ["Python"]


class TestUserOverrides:
    """用户规则的新增、覆盖、删除与恢复"""

    def test_save_new_language(self, plugin_dir, data_provider):
        store = RuleStore(plugin_dir, data_provider, PLUGIN_ID)
        assert store.save_user_rule(_go_rule()) == []
        assert store.rule_for_extension(".go")["builtin"] is False
        assert store.is_builtin("Go") is False
        assert store.is_overridden("Go") is True

    def test_save_invalid_rule_not_saved(self, plugin_dir, data_provider):
        store = RuleStore(plugin_dir, data_provider, PLUGIN_ID)
        bad_rule = {"name": "", "extensions": [".x"], "line_comments": ["#"]}
        assert store.save_user_rule(bad_rule) != []
        assert store.rule_for_extension(".x") is None

    def test_override_builtin_wins(self, plugin_dir, data_provider):
        store = RuleStore(plugin_dir, data_provider, PLUGIN_ID)
        override = {"name": "Python", "extensions": ["py"], "line_comments": ["##"]}
        assert store.save_user_rule(override) == []
        effective = store.rule_for_extension(".py")
        assert effective["line_comments"] == ["##"]
        assert effective["builtin"] is True
        assert store.is_overridden("Python") is True

    def test_overrides_persist_across_instances(self, plugin_dir, tmp_path):
        DataProvider._instance = None
        provider = DataProvider(data_dir=str(tmp_path / "db"), data_filename="test.json")
        RuleStore(plugin_dir, provider, PLUGIN_ID).save_user_rule(_go_rule())
        DataProvider._instance = None
        provider2 = DataProvider(data_dir=str(tmp_path / "db"), data_filename="test.json")
        store2 = RuleStore(plugin_dir, provider2, PLUGIN_ID)
        assert store2.is_overridden("Go") is True
        assert store2.rule_for_extension(".go") is not None
        DataProvider._instance = None

    def test_delete_custom_language(self, plugin_dir, data_provider):
        store = RuleStore(plugin_dir, data_provider, PLUGIN_ID)
        store.save_user_rule(_go_rule())
        assert store.delete_language("Go") is True
        assert store.rule_for_extension(".go") is None
        assert store.delete_language("Go") is False

    def test_delete_builtin_rejected(self, plugin_dir, data_provider):
        store = RuleStore(plugin_dir, data_provider, PLUGIN_ID)
        assert store.delete_language("Python") is False
        assert store.rule_for_extension(".py") is not None

    def test_restore_builtin(self, plugin_dir, data_provider):
        store = RuleStore(plugin_dir, data_provider, PLUGIN_ID)
        override = {"name": "Python", "extensions": ["py"], "line_comments": ["##"]}
        store.save_user_rule(override)
        assert store.restore_builtin("Python") is True
        assert store.rule_for_extension(".py")["line_comments"] == ["#"]
        assert store.restore_builtin("Python") is False
        assert store.restore_builtin("不存在的语言") is False


class TestDegradedMode:
    """DataProvider 不可用时的内存态降级"""

    def test_memory_only_mode(self, plugin_dir):
        store = RuleStore(plugin_dir, None, PLUGIN_ID)
        assert store.save_user_rule(_go_rule()) == []
        assert store.rule_for_extension(".go")["name"] == "Go"

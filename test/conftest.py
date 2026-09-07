"""PureCode 插件测试基础设施：路径引导与插件包别名加载"""

import importlib.util
import sys
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
PLUGIN_REPO_ROOT = TEST_DIR.parent
FRAMEWORK_ROOT = PLUGIN_REPO_ROOT.parent
PLUGIN_DIR = PLUGIN_REPO_ROOT / "pure-code"
PLUGIN_PACKAGE_ALIAS = "pure_code"

# 插件 function 层依赖框架接口（core.interfaces / core.data / utils），
# 需将框架根目录加入模块搜索路径
if str(FRAMEWORK_ROOT) not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_ROOT))


def _load_plugin_package() -> None:
    """将 pure-code 目录（连字符不可直接 import）加载为 pure_code 包"""
    if PLUGIN_PACKAGE_ALIAS in sys.modules:
        return
    spec = importlib.util.spec_from_file_location(
        PLUGIN_PACKAGE_ALIAS,
        PLUGIN_DIR / "__init__.py",
        submodule_search_locations=[str(PLUGIN_DIR)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[PLUGIN_PACKAGE_ALIAS] = module
    spec.loader.exec_module(module)


_load_plugin_package()

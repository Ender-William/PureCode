"""
PureCode 插件元数据

定义插件的版本、开发者、对外 API 等元数据信息，供框架加载与展示。
"""

from typing import Any, Dict

from core.interfaces import IPluginInfo
from core.plugin.plugin_icon import PluginIcon
from core.plugin.plugin_version import PluginVersion


class PureCodePluginInfo(IPluginInfo):
    """
    PureCode 插件元数据实现

    仅承载元数据，不包含任何运行时配置与业务逻辑。
    """

    @property
    def version(self) -> PluginVersion:
        """插件版本号（开发期自测使用 alpha 类型）"""
        return PluginVersion.from_string("alpha.0.1.0")

    @property
    def developer(self) -> str:
        """开发者名称"""
        return "William_Kuang"

    @property
    def developer_email(self) -> str:
        """开发者邮箱"""
        return "fuwa165@126.com"

    @property
    def developer_website(self) -> str:
        """开发者网站（暂无）"""
        return ""

    @property
    def is_free(self) -> bool:
        """是否免费"""
        return True

    @property
    def description(self) -> str:
        """插件详细描述"""
        return (
            "PureCode 面向软件著作权申请材料准备场景：选择项目目录后自动识别文件格式，"
            "基于可扩展的语言注释规则去除代码注释（不修改原文件），"
            "经文件树精细勾选与独立排序窗口编排文件顺序，最终导出标准 docx 文档。"
        )

    @property
    def service_api(self) -> Dict[str, Any]:
        """Service API 文档（与 service.py 的 PureCodeService 保持同步）"""
        return {
            "export_code_document": {
                "description": "扫描项目目录并导出代码 Word 文档（去除注释，按默认顺序）",
                "parameters": {
                    "project_dir": {
                        "type": "string",
                        "description": "项目根目录绝对路径",
                        "required": True,
                    },
                    "output_path": {
                        "type": "string",
                        "description": "输出 docx 文件路径",
                        "required": True,
                    },
                    "extensions": {
                        "type": "array",
                        "description": "限定导出的扩展名列表（如 [\".py\"]），缺省为全部类型",
                        "required": False,
                        "default": None,
                    },
                },
                "returns": {
                    "type": "object",
                    "description": "{output_path, file_count, skipped, unmatched}",
                },
            },
            "list_supported_languages": {
                "description": "列出当前生效的语言注释规则（内置 ∪ 用户覆盖）",
                "parameters": {},
                "returns": {
                    "type": "array",
                    "description": "语言规则列表（含 name/extensions/注释符/builtin 标记）",
                },
            },
        }

    @property
    def skill_icon(self) -> PluginIcon:
        """技能面板图标（相对插件目录的图标文件）"""
        return PluginIcon.from_file("icons/icon.png")

    @property
    def skill_description(self) -> str:
        """技能面板简短描述"""
        return "去注释并导出代码 Word 文档"

    @property
    def plugin_type_id(self) -> str:
        """插件类型标识符（稳定不变，与目录名一致）"""
        return "pure-code"

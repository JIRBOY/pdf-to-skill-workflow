"""数据模型 — 知识库的结构化表示。"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class KnowledgeType(str, Enum):
    """知识点类型。"""
    API = "api"              # API 方法/函数
    CLASS = "class"          # 类/结构体
    ENUM = "enum"            # 枚举值
    CONSTANT = "constant"    # 常量
    ERROR_CODE = "error"     # 错误码
    CONFIG = "config"        # 配置项
    EXAMPLE = "example"      # 代码示例
    CONCEPT = "concept"      # 概念说明
    PATTERN = "pattern"      # 设计模式/最佳实践
    PROTOCOL = "protocol"    # 协议结构/命令


class DomainType(str, Enum):
    """文档领域类型 — 用于选择提取 prompt 策略。"""
    API_DOC = "api_doc"           # SDK/API 参考文档
    PROTOCOL = "protocol"         # 协议规范
    FRAMEWORK = "framework"       # 框架文档
    DATABASE = "database"         # 数据库文档
    INTERNAL = "internal"         # 内部文档
    GENERAL = "general"           # 通用/无法分类


@dataclass
class Document:
    """源文档元信息。"""
    id: Optional[int] = None
    name: str = ""           # 文档简称，如 "TwinCAT-ADS-Python"
    version: str = ""        # 文档版本，如 "4.0"
    source_path: str = ""    # 原始 PDF 路径
    file_hash: str = ""      # PDF 文件的 SHA256（用于去重/检测更新）
    imported_at: str = ""    # 导入时间 ISO 格式
    total_pages: int = 0
    domain: str = "general"  # 领域类型


@dataclass
class Chapter:
    """章节层级。"""
    id: Optional[int] = None
    document_id: int = 0
    title: str = ""
    path: str = ""           # 章节路径，如 "2.3.1"
    page_start: int = 0
    page_end: int = 0


@dataclass
class KnowledgePoint:
    """单个知识点。"""
    id: Optional[int] = None
    document_id: int = 0
    chapter_id: int = 0
    kb_type: str = "concept"
    title: str = ""           # 知识点标题/名称
    content: str = ""         # 详细描述
    code_example: str = ""    # 代码示例（如有）
    signature: str = ""       # API 签名（如 func(arg1, arg2) -> ret）
    parameters: str = ""      # 参数说明 JSON
    return_type: str = ""     # 返回类型
    tags: list[str] = field(default_factory=list)
    page_ref: int = 0         # 原始页码

"""知识点提取 — 按领域使用专用 prompt 策略。"""

import json
from pathlib import Path
from typing import Optional

from rich.console import Console

from .models import Chapter, DomainType

console = Console()

# Prompt 模板目录（和此文件同级的 prompts/ 目录）
_PROMPTS_DIR = Path(__file__).parent / "prompts"

# 领域类型 → prompt 文件名映射
_PROMPT_FILES = {
    DomainType.API_DOC: "api_doc.md",
    DomainType.PROTOCOL: "protocol.md",
    DomainType.FRAMEWORK: "framework.md",
    DomainType.DATABASE: "database.md",
    DomainType.INTERNAL: "internal.md",
    DomainType.GENERAL: "general.md",
}

# 延迟加载缓存
_prompt_cache: dict[DomainType, str] = {}


def _load_prompt(domain: DomainType) -> str:
    """从文件加载 prompt 模板（带缓存）。"""
    if domain in _prompt_cache:
        return _prompt_cache[domain]

    filename = _PROMPT_FILES.get(domain, "general.md")
    filepath = _PROMPTS_DIR / filename

    if filepath.exists():
        template = filepath.read_text(encoding="utf-8")
    else:
        # 回退到内置默认
        template = "你是技术文档分析专家。提取所有编程相关知识。\n\n【输出格式】JSON 对象，用 `---` 分隔\n{{\"type\": \"...\", \"title\": \"...\", \"content\": \"...\", \"signature\": \"...\", \"code_example\": \"...\", \"tags\": [\"tag1\"]}}\n\n以下是文档内容：\n\n{content}"

    _prompt_cache[domain] = template
    return template


def detect_domain(content: str) -> DomainType:
    """根据文档内容自动检测领域类型。"""
    content_lower = content.lower()

    # 协议特征词
    protocol_signals = ["packet structure", "command id", "error code", "port mapping",
                        "byte order", "handshake", "protocol version", "ads port",
                        "a ms", "ams/netid", "modbus", "opc ua"]
    if sum(1 for s in protocol_signals if s in content_lower) >= 2:
        return DomainType.PROTOCOL

    # API/SDK 特征
    api_signals = ["method signature", "returns", "parameter", "api reference",
                   "client.create", "client.get", "def ", "func ", "public class"]
    if sum(1 for s in api_signals if s in content_lower) >= 2:
        return DomainType.API_DOC

    # 框架特征
    framework_signals = ["component", "lifecycle", "middleware", "route",
                         "hook", "plugin", "configuration"]
    if sum(1 for s in framework_signals if s in content_lower) >= 2:
        return DomainType.FRAMEWORK

    # 数据库特征
    db_signals = ["sql", "query", "index", "table", "datatype", "constraint",
                  "transaction", "postgresql", "mysql"]
    if sum(1 for s in db_signals if s in content_lower) >= 2:
        return DomainType.DATABASE

    return DomainType.GENERAL


def parse_extracted_json(text: str) -> list[dict]:
    """从提取输出文本中解析 JSON 知识点。"""
    items = []
    blocks = text.split("---")

    for block in blocks:
        block = block.strip()
        if not block:
            continue
        # 提取 JSON 对象（可能在文本中）
        try:
            # 尝试直接解析
            obj = json.loads(block)
            if isinstance(obj, dict):
                items.append(obj)
                continue
        except json.JSONDecodeError:
            pass

        # 尝试在文本中找 JSON
        start = block.find("{")
        end = block.rfind("}")
        if start >= 0 and end > start:
            try:
                obj = json.loads(block[start:end+1])
                if isinstance(obj, dict):
                    items.append(obj)
            except json.JSONDecodeError:
                console.print(f"  [yellow]解析 JSON 失败，跳过该块[/yellow]")

    return items


def extract_knowledge_points(content: str, domain: DomainType, use_agent: bool = False) -> list[dict]:
    """
    对文档内容提取知识点。

    Args:
        content: Markdown 文档内容
        domain: 领域类型
        use_agent: 是否使用 Agent（LLM API）提取，False 则使用规则提取

    Returns:
        知识点列表（JSON dict 格式）
    """
    prompt_template = _load_prompt(domain)
    prompt = prompt_template.format(content=content)

    if use_agent:
        # Agent 提取由 CLI 层调度
        console.print("  [dim]使用 Agent 提取知识点（需外部调度）...[/dim]")
        return _extract_with_agent(prompt)

    # 降级：简单规则提取
    console.print("  [yellow]使用规则提取（质量有限，建议启用 Agent 模式）[/yellow]")
    return _extract_with_rules(content)


def _can_use_agent() -> bool:
    """检查是否有 Claude Agent 可用的环境。"""
    # 在 Claude Code 环境中，Agent 工具由 Claude Code 本身提供
    # 这里我们返回 False，让 CLI 层决定是否调用 Agent
    return False


def _extract_with_agent(prompt: str) -> list[dict]:
    """通过 Claude Code Agent 工具提取知识点。"""
    # 这个方法应该在 CLI 层通过 Agent tool 调用
    # 这里保留接口，实际由 cli.py 实现
    return []


def _extract_with_rules(content: str) -> list[dict]:
    """简单规则提取（降级方案）。"""
    items = []
    lines = content.split("\n")

    current_heading = ""
    for line in lines:
        stripped = line.strip()

        # 跟踪当前章节
        if stripped.startswith("#"):
            current_heading = stripped.lstrip("# ").strip()

        # 检测代码块
        if stripped.startswith("```"):
            continue

        # 检测函数签名模式（简化）
        import re
        func_patterns = [
            r"^(def|function|func|public|private|protected)\s+(\w+)",
            r"^(\w+)\s*\([^)]*\)\s*(->|:|=)",
            r"^(async\s+)?def\s+(\w+)\s*\(",
        ]
        for pat in func_patterns:
            m = re.match(pat, stripped)
            if m:
                items.append({
                    "type": "api",
                    "title": stripped[:100],
                    "content": f"来自章节: {current_heading}",
                    "signature": stripped,
                    "code_example": "",
                    "tags": [current_heading] if current_heading else [],
                })
                break

    return items


def extract_chapters_from_markdown(content: str, doc_id: int) -> list[Chapter]:
    """从 Markdown 内容中提取章节结构。"""
    chapters = []
    lines = content.split("\n")
    current_chapter = None
    page_start = 1

    for line_num, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#"):
            # 保存上一章
            if current_chapter:
                current_chapter.page_end = page_start
                chapters.append(current_chapter)

            level = len(stripped) - len(stripped.lstrip("#"))
            title = stripped.lstrip("# ").strip()
            # 提取页码引用
            page_ref = _extract_page_ref(content, line_num)

            current_chapter = Chapter(
                document_id=doc_id,
                title=title,
                path=f"{'.'.join(['1'] * level)}",
                page_start=page_ref or page_start,
                page_end=page_ref or page_start,
            )
            page_start = page_ref or page_start

    if current_chapter:
        current_chapter.page_end = current_chapter.page_start
        chapters.append(current_chapter)

    return chapters


def _extract_page_ref(content: str, line_num: int) -> int:
    """从行号附近提取页码引用（如果有的话）。"""
    # 查找 "Page X" 或 "page X" 模式
    import re
    start = max(0, line_num - 5)
    end = min(len(content.split("\n")), line_num + 5)
    context = "\n".join(content.split("\n")[start:end])
    m = re.search(r"Page\s+(\d+)", context, re.IGNORECASE)
    return int(m.group(1)) if m else 0

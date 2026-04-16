"""索引器 — 将提取的知识点写入 SQLite，构建 FTS5 索引。"""

from rich.console import Console

from .db import Database
from .extractor import extract_chapters_from_markdown, extract_knowledge_points, parse_extracted_json
from .models import Document, DomainType

console = Console()


def index_document(db: Database, doc: Document, markdown_content: str, domain: DomainType, use_agent: bool = False) -> int:
    """
    完整索引流程：章节提取 → 知识点提取 → 批量写入。

    Args:
        db: 数据库实例
        doc: 文档元信息
        markdown_content: PDF 转换后的 Markdown 内容
        domain: 领域类型
        use_agent: 是否启用 Agent 提取

    Returns:
        索引的知识点数量
    """
    # 1. 保存文档元信息
    doc_id = db.add_document(doc)
    console.print(f"  [green]文档已注册: {doc.name} v{doc.version} (id={doc_id})[/green]")

    # 2. 提取章节
    chapters = extract_chapters_from_markdown(markdown_content, doc_id)
    for ch in chapters:
        db.add_chapter(ch)
    console.print(f"  [dim]提取了 {len(chapters)} 个章节[/dim]")

    # 3. 提取知识点
    raw_points = extract_knowledge_points(markdown_content, domain, use_agent=use_agent)
    if not raw_points:
        console.print("  [yellow]未提取到知识点，请检查文档内容或尝试其他领域类型[/yellow]")
        return 0

    console.print(f"  [dim]提取了 {len(raw_points)} 个原始知识点，正在写入数据库 ...[/dim]")

    # 4. 写入知识点
    from .models import KnowledgePoint
    kps = []
    for point in raw_points:
        kp = KnowledgePoint(
            document_id=doc_id,
            chapter_id=0,  # 后续可关联
            kb_type=point.get("type", "concept"),
            title=point.get("title", "")[:200],
            content=point.get("content", ""),
            code_example=point.get("code_example", ""),
            signature=point.get("signature", ""),
            parameters=point.get("parameters", ""),
            return_type=point.get("return_type", ""),
            page_ref=point.get("page_ref", 0),
        )
        kps.append(kp)

    count = db.add_knowledge_batch(kps)

    # 5. 写入标签
    for kp, point in zip(kps, raw_points):
        tags = point.get("tags", [])
        if tags and kp.id:
            db.add_tags(kp.id, tags)

    console.print(f"  [green]已索引 {count} 个知识点[/green]")
    return count

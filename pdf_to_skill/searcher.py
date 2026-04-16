"""查询接口 — FTS5 检索 + Agent 精炼 + 网络搜索辅助。"""

import json
from typing import Optional

from rich.console import Console

from .db import Database
from .models import KnowledgePoint

console = Console()


class Searcher:
    """知识库查询接口。"""

    def __init__(self, db: Database, enhanced: bool = False):
        self.db = db
        self.enhanced = enhanced

    def search(self, query: str, limit: int = 10, kb_type: Optional[str] = None) -> list[KnowledgePoint]:
        """
        搜索知识点。

        轻量模式：直接 FTS5 查询。
        增强模式：FTS5 初筛 → Agent 语义精炼 → 返回最相关结果。
        """
        # 1. FTS5 全文搜索
        results = self._fts5_search(query, limit=50)  # 初筛多一些

        # 按类型过滤
        if kb_type:
            results = [kp for kp in results if kp.kb_type == kb_type]

        if not results:
            console.print("  [yellow]未找到相关知识点，尝试扩展搜索 ...[/yellow]")
            results = self._fts5_search_fallback(query, limit=20)

        # 2. 增强模式：Agent 精炼
        if self.enhanced and len(results) > 5:
            results = self._agent_refine(query, results, top_k=limit)

        # 3. 网络搜索辅助（增强模式）
        if self.enhanced:
            web_results = self._web_search_supplement(query)
            if web_results:
                console.print(f"  [dim]网络搜索补充: {len(web_results)} 条[/dim]")

        return results[:limit]

    def _fts5_search(self, query: str, limit: int = 10) -> list[KnowledgePoint]:
        """FTS5 全文检索。"""
        # 将查询词转为 FTS5 语法（短语匹配 + 扩展）
        terms = query.split()
        if len(terms) == 1:
            fts_query = query
        else:
            # 多词：至少匹配其中一个
            fts_query = " OR ".join(terms)

        rows = self.db.conn.execute(
            """SELECT k.*, rank FROM knowledge_fts f
               JOIN knowledge k ON k.id = f.rowid
               WHERE knowledge_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (fts_query, limit),
        ).fetchall()

        return [self._row_to_kp(r) for r in rows]

    def _fts5_search_fallback(self, query: str, limit: int = 10) -> list[KnowledgePoint]:
        """降级搜索：LIKE 匹配（当 FTS5 无结果时）。"""
        pattern = f"%{query}%"
        rows = self.db.conn.execute(
            """SELECT * FROM knowledge
               WHERE title LIKE ? OR content LIKE ? OR signature LIKE ?
               LIMIT ?""",
            (pattern, pattern, pattern, limit),
        ).fetchall()
        return [self._row_to_kp(r) for r in rows]

    def _agent_refine(self, query: str, candidates: list[KnowledgePoint], top_k: int = 10) -> list[KnowledgePoint]:
        """
        Agent 语义精炼：给 Claude 候选集，让它选出最相关的 top_k。

        使用 Anthropic API 直接调用，不走 Agent tool（因为这里本身就是 Claude 在执行）。
        """
        if not _has_anthropic():
            return candidates[:top_k]

        try:
            return self._refine_with_api(query, candidates, top_k)
        except Exception as e:
            console.print(f"  [yellow]Agent 精炼失败: {e}，返回原始结果[/yellow]")
            return candidates[:top_k]

    def _refine_with_api(self, query: str, candidates: list[KnowledgePoint], top_k: int) -> list[KnowledgePoint]:
        """用 Anthropic API 做语义精炼。"""
        from anthropic import Anthropic

        # 构建候选集摘要
        candidate_text = "\n".join([
            f"[{i}] [{kp.kb_type}] {kp.title}\n{kp.content[:200]}"
            for i, kp in enumerate(candidates)
        ])

        client = Anthropic()
        resp = client.messages.create(
            model="claude-sonnet-4-6-20250514",
            max_tokens=500,
            system="你是一个技术文档检索助手。从候选知识点中选出与用户查询最相关的 top 条目。只返回 JSON 数组，包含选中条目的索引。",
            messages=[{
                "role": "user",
                "content": f"""用户查询: {query}

候选知识点:
{candidate_text}

请选出最相关的 top {top_k} 条（或更少），返回 JSON 数组，如: [0, 2, 5]"""
            }],
        )

        # 解析结果
        import re
        text = resp.content[0].text
        match = re.search(r'\[.*?\]', text)
        if match:
            indices = json.loads(match.group())
            return [candidates[i] for i in indices if i < len(candidates)]

        return candidates[:top_k]

    def _web_search_supplement(self, query: str) -> list[str]:
        """
        网络搜索辅助：当知识库中没有相关内容时，通过网络搜索补充。

        需要 httpx 依赖。
        """
        if not _has_httpx():
            return []

        # 这里可以通过外部搜索 API（如 DuckDuckGo、Google 等）获取结果
        # 暂时返回空，后续可扩展
        return []

    def _row_to_kp(self, row) -> KnowledgePoint:
        """从数据库行构建 KnowledgePoint，包含 tags。"""
        kp = KnowledgePoint(
            id=row[0], document_id=row[1], chapter_id=row[2], kb_type=row[3],
            title=row[4], content=row[5], code_example=row[6],
            signature=row[7], parameters=row[8], return_type=row[9], page_ref=row[10],
        )
        tag_rows = self.db.conn.execute(
            "SELECT t.name FROM tags t JOIN knowledge_tags kt ON t.id=kt.tag_id WHERE kt.knowledge_id=?",
            (kp.id,),
        ).fetchall()
        kp.tags = [r[0] for r in tag_rows]
        return kp

    def format_results(self, results: list[KnowledgePoint], query: str) -> str:
        """格式化搜索结果，便于 AI 理解和使用。"""
        if not results:
            return f"查询 '{query}' 未找到相关知识点。"

        parts = [f"查询 '{query}' 找到 {len(results)} 条结果:\n"]

        for i, kp in enumerate(results, 1):
            parts.append(f"### {i}. [{kp.kb_type}] {kp.title}")
            if kp.signature:
                parts.append(f"**签名:** `{kp.signature}`")
            if kp.content:
                parts.append(kp.content)
            if kp.code_example:
                parts.append(f"**示例:**\n```python\n{kp.code_example}\n```")
            if kp.tags:
                parts.append(f"**标签:** {', '.join(kp.tags)}")
            parts.append("")

        return "\n".join(parts)


def _has_anthropic() -> bool:
    try:
        import anthropic
        return True
    except ImportError:
        return False


def _has_httpx() -> bool:
    try:
        import httpx
        return True
    except ImportError:
        return False

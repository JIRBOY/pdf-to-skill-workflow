"""数据库管理 — SQLite schema、FTS5 索引、CRUD 操作。"""

import sqlite3
from pathlib import Path
from typing import Optional

from .models import Chapter, Document, KnowledgePoint

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    version TEXT DEFAULT '',
    source_path TEXT DEFAULT '',
    file_hash TEXT DEFAULT '',
    imported_at TEXT DEFAULT (datetime('now')),
    total_pages INTEGER DEFAULT 0,
    domain TEXT DEFAULT 'general'
);

CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    path TEXT DEFAULT '',
    page_start INTEGER DEFAULT 0,
    page_end INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chapter_id INTEGER DEFAULT 0 REFERENCES chapters(id),
    kb_type TEXT DEFAULT 'concept',
    title TEXT NOT NULL,
    content TEXT DEFAULT '',
    code_example TEXT DEFAULT '',
    signature TEXT DEFAULT '',
    parameters TEXT DEFAULT '',
    return_type TEXT DEFAULT '',
    page_ref INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS knowledge_tags (
    knowledge_id INTEGER REFERENCES knowledge(id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (knowledge_id, tag_id)
);

-- FTS5 全文索引（对 knowledge 表的 title + content + signature 建索引）
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
    title, content, signature, code_example,
    content='knowledge',
    content_rowid='id',
    tokenize='unicode61'
);

-- 触发器：knowledge 插入/更新/删除时同步 FTS5
CREATE TRIGGER IF NOT EXISTS knowledge_ai AFTER INSERT ON knowledge BEGIN
    INSERT INTO knowledge_fts(rowid, title, content, signature, code_example)
    VALUES (new.id, new.title, new.content, new.signature, new.code_example);
END;

CREATE TRIGGER IF NOT EXISTS knowledge_au AFTER UPDATE ON knowledge BEGIN
    INSERT INTO knowledge_fts(knowledge_fts, rowid, title, content, signature, code_example)
    VALUES ('delete', old.id, old.title, old.content, old.signature, old.code_example);
    INSERT INTO knowledge_fts(rowid, title, content, signature, code_example)
    VALUES (new.id, new.title, new.content, new.signature, new.code_example);
END;

CREATE TRIGGER IF NOT EXISTS knowledge_ad AFTER DELETE ON knowledge BEGIN
    INSERT INTO knowledge_fts(knowledge_fts, rowid, title, content, signature, code_example)
    VALUES ('delete', old.id, old.title, old.content, old.signature, old.code_example);
END;
"""


class Database:
    """SQLite 数据库操作封装。"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    def close(self):
        self.conn.close()

    # --- Document ---

    def add_document(self, doc: Document) -> int:
        cur = self.conn.execute(
            "INSERT INTO documents (name, version, source_path, file_hash, total_pages, domain) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (doc.name, doc.version, doc.source_path, doc.file_hash, doc.total_pages, doc.domain),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_document(self, doc_id: int) -> Optional[Document]:
        row = self.conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
        if not row:
            return None
        return Document(
            id=row[0], name=row[1], version=row[2], source_path=row[3],
            file_hash=row[4], imported_at=row[5], total_pages=row[6], domain=row[7],
        )

    def find_document_by_hash(self, file_hash: str) -> Optional[Document]:
        row = self.conn.execute(
            "SELECT * FROM documents WHERE file_hash=?", (file_hash,)
        ).fetchone()
        if not row:
            return None
        return Document(
            id=row[0], name=row[1], version=row[2], source_path=row[3],
            file_hash=row[4], imported_at=row[5], total_pages=row[6], domain=row[7],
        )

    def find_document_by_name(self, name: str) -> Optional[Document]:
        row = self.conn.execute(
            "SELECT * FROM documents WHERE name=?", (name,)
        ).fetchone()
        if not row:
            return None
        return Document(
            id=row[0], name=row[1], version=row[2], source_path=row[3],
            file_hash=row[4], imported_at=row[5], total_pages=row[6], domain=row[7],
        )

    def list_documents(self) -> list[Document]:
        rows = self.conn.execute("SELECT * FROM documents ORDER BY imported_at DESC").fetchall()
        return [
            Document(
                id=r[0], name=r[1], version=r[2], source_path=r[3],
                file_hash=r[4], imported_at=r[5], total_pages=r[6], domain=r[7],
            )
            for r in rows
        ]

    def delete_document(self, doc_id: int):
        """删除文档及其所有关联数据（cascade）。"""
        self.conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        self.conn.commit()

    def get_document_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

    # --- Chapter ---

    def add_chapter(self, chapter: Chapter) -> int:
        cur = self.conn.execute(
            "INSERT INTO chapters (document_id, title, path, page_start, page_end) VALUES (?, ?, ?, ?, ?)",
            (chapter.document_id, chapter.title, chapter.path, chapter.page_start, chapter.page_end),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_chapters(self, document_id: int) -> list[Chapter]:
        rows = self.conn.execute(
            "SELECT * FROM chapters WHERE document_id=? ORDER BY path", (document_id,)
        ).fetchall()
        return [
            Chapter(id=r[0], document_id=r[1], title=r[2], path=r[3], page_start=r[4], page_end=r[5])
            for r in rows
        ]

    # --- Knowledge ---

    def add_knowledge(self, kp: KnowledgePoint) -> int:
        cur = self.conn.execute(
            "INSERT INTO knowledge (document_id, chapter_id, kb_type, title, content, "
            "code_example, signature, parameters, return_type, page_ref) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (kp.document_id, kp.chapter_id, kp.kb_type, kp.title, kp.content,
             kp.code_example, kp.signature, kp.parameters, kp.return_type, kp.page_ref),
        )
        self.conn.commit()
        return cur.lastrowid

    def add_knowledge_batch(self, kps: list[KnowledgePoint]) -> int:
        """批量插入知识点（事务）。"""
        count = 0
        for kp in kps:
            self.conn.execute(
                "INSERT INTO knowledge (document_id, chapter_id, kb_type, title, content, "
                "code_example, signature, parameters, return_type, page_ref) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (kp.document_id, kp.chapter_id, kp.kb_type, kp.title, kp.content,
                 kp.code_example, kp.signature, kp.parameters, kp.return_type, kp.page_ref),
            )
            count += 1
        self.conn.commit()
        return count

    def get_knowledge(self, kp_id: int) -> Optional[KnowledgePoint]:
        row = self.conn.execute("SELECT * FROM knowledge WHERE id=?", (kp_id,)).fetchone()
        if not row:
            return None
        return self._row_to_kp(row)

    def get_knowledge_by_doc(self, document_id: int, kb_type: Optional[str] = None) -> list[KnowledgePoint]:
        if kb_type:
            rows = self.conn.execute(
                "SELECT * FROM knowledge WHERE document_id=? AND kb_type=? ORDER BY id",
                (document_id, kb_type),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM knowledge WHERE document_id=? ORDER BY id", (document_id,)
            ).fetchall()
        return [self._row_to_kp(r) for r in rows]

    def _row_to_kp(self, row) -> KnowledgePoint:
        kp = KnowledgePoint(
            id=row[0], document_id=row[1], chapter_id=row[2], kb_type=row[3],
            title=row[4], content=row[5], code_example=row[6],
            signature=row[7], parameters=row[8], return_type=row[9], page_ref=row[10],
        )
        # 加载 tags
        tag_rows = self.conn.execute(
            "SELECT t.name FROM tags t JOIN knowledge_tags kt ON t.id=kt.tag_id WHERE kt.knowledge_id=?",
            (kp.id,),
        ).fetchall()
        kp.tags = [r[0] for r in tag_rows]
        return kp

    # --- Tags ---

    def add_tags(self, knowledge_id: int, tag_names: list[str]):
        for name in tag_names:
            cur = self.conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
            tag_id = self.conn.execute("SELECT id FROM tags WHERE name=?", (name,)).fetchone()[0]
            self.conn.execute(
                "INSERT OR IGNORE INTO knowledge_tags (knowledge_id, tag_id) VALUES (?, ?)",
                (knowledge_id, tag_id),
            )
        self.conn.commit()

    # --- Stats ---

    def get_db_size(self) -> int:
        """数据库文件大小（字节）。"""
        import os
        return os.path.getsize(self.db_path)

    def get_stats(self) -> dict:
        docs = self.get_document_count()
        kps = self.conn.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
        tags = self.conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
        size = self.get_db_size()
        return {"documents": docs, "knowledge_points": kps, "tags": tags, "size_bytes": size}

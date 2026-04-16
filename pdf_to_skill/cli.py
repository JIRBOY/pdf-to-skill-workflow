"""CLI 入口 — import / query / update / delete / stats / git-backup。"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# Windows 控制台 UTF-8 编码
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .config import Config
from .db import Database
from .dependencies import (
    check_all_for_import,
    check_all_for_query,
)
from .converter import pdf_to_markdown, split_markdown, save_source
from .extractor import detect_domain
from .indexer import index_document
from .searcher import Searcher
from .models import Document, DomainType

console = Console()


def main():
    parser = argparse.ArgumentParser(
        prog="pdf-to-skill",
        description="将技术文档 PDF 转化为可检索的知识库技能",
    )
    parser.add_argument("--db", help="数据库路径 (默认: ./kb/skills.db)")
    parser.add_argument("--workdir", help="工作目录 (默认: 当前目录)")

    sub = parser.add_subparsers(dest="command", required=True)

    # import
    p_import = sub.add_parser("import", help="导入 PDF 文档到知识库")
    p_import.add_argument("pdf", help="PDF 文件路径")
    p_import.add_argument("--name", required=True, help="文档简称")
    p_import.add_argument("--version", default="1.0.0", help="文档版本")
    p_import.add_argument("--domain", choices=[d.value for d in DomainType],
                          help="文档领域类型 (自动检测)")
    p_import.add_argument("--no-agent", action="store_true", help="不使用 Agent 提取")
    p_import.add_argument("--enhance", action="store_true", help="启用增强模式提取")

    # query
    p_query = sub.add_parser("query", help="查询知识库")
    p_query.add_argument("query", help="搜索关键词")
    p_query.add_argument("--type", dest="kb_type", help="按类型过滤 (api/class/enum/error等)")
    p_query.add_argument("--limit", type=int, default=10, help="返回数量 (默认 10)")
    p_query.add_argument("--enhance", action="store_true", help="增强模式 (Agent 精炼)")
    p_query.add_argument("--json", action="store_true", dest="as_json", help="JSON 格式输出")

    # list
    sub.add_parser("list", help="列出已导入的文档")

    # stats
    sub.add_parser("stats", help="知识库统计信息")

    # delete
    p_delete = sub.add_parser("delete", help="删除文档及其数据")
    p_delete.add_argument("name", help="文档名称")

    # update
    p_update = sub.add_parser("update", help="更新文档（git 备份旧版本后重新导入）")
    p_update.add_argument("pdf", help="新版 PDF 路径")
    p_update.add_argument("--name", required=True, help="文档名称")
    p_update.add_argument("--version", help="新版本号")
    p_update.add_argument("--domain", choices=[d.value for d in DomainType])

    args = parser.parse_args()

    # 初始化配置
    config = Config()
    if args.workdir:
        config = Config(workdir=Path(args.workdir))
    if args.db:
        config.db_path = Path(args.db)
    config.ensure_dirs()

    # 分发命令
    if args.command == "import":
        cmd_import(args, config)
    elif args.command == "query":
        cmd_query(args, config)
    elif args.command == "list":
        cmd_list(config)
    elif args.command == "stats":
        cmd_stats(config)
    elif args.command == "delete":
        cmd_delete(args, config)
    elif args.command == "update":
        cmd_update(args, config)


# ──────────────────────────────────────────────
# 命令实现
# ──────────────────────────────────────────────

def cmd_import(args, config: Config):
    """导入 PDF 文档。"""
    console.print(Panel(f"导入 PDF: {args.pdf}", title="PDF 导入", border_style="blue"))

    # 检查依赖
    if not check_all_for_import():
        console.print("  [red]依赖检查失败，无法导入[/red]")
        sys.exit(1)

    # 如果已有同名文档，阻止导入（不允许一个技能文件夹有多个版本）
    db = Database(config.db_path)
    existing = db.find_document_by_name(args.name)
    if existing:
        console.print(f"  [red]已存在同名文档: {args.name} v{existing.version}[/red]")
        console.print("  使用 update 命令更新，或 delete 命令删除后重新导入。")
        db.close()
        sys.exit(1)

    # 如果已有相同 hash，说明是同一文件
    _, file_hash = pdf_to_markdown(args.pdf, config) if False else (None, None)  # 先不转换
    # 计算 hash
    import hashlib
    with open(args.pdf, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
    if db.find_document_by_hash(file_hash):
        console.print("  [yellow]此 PDF 已导入过（文件 hash 相同）[/yellow]")
        db.close()
        sys.exit(1)

    # 转换 PDF
    console.print("\n[dim]步骤 1/4: 转换 PDF → Markdown[/dim]")
    md_content, _ = pdf_to_markdown(args.pdf, config)
    console.print(f"  [dim]转换完成: {len(md_content)} 字符[/dim]")

    # 保存原始文件
    console.print("\n[dim]步骤 2/4: 保存原始文件[/dim]")
    save_source(args.pdf, config, args.name)

    # 检测领域类型
    domain_str = args.domain
    if not domain_str:
        domain = detect_domain(md_content)
        console.print(f"  [dim]自动检测领域类型: {domain.value}[/dim]")
    else:
        domain = DomainType(domain_str)

    # 创建文档元信息
    import fitz
    try:
        doc = fitz.open(args.pdf)
        total_pages = len(doc)
        doc.close()
    except:
        total_pages = 0

    doc = Document(
        name=args.name,
        version=args.version,
        source_path=args.pdf,
        file_hash=file_hash,
        total_pages=total_pages,
        domain=domain.value,
        imported_at=datetime.now().isoformat(),
    )

    # 索引
    console.print(f"\n[dim]步骤 3/4: 提取并索引知识点 (领域: {domain.value})[/dim]")
    kp_count = index_document(db, doc, md_content, domain, use_agent=not args.no_agent)

    # 统计
    console.print(f"\n[dim]步骤 4/4: 完成[/dim]")
    stats = db.get_stats()
    console.print(Panel(
        f"文档: {stats['documents']}\n知识点: {stats['knowledge_points']}\n"
        f"数据库大小: {stats['size_bytes'] / 1024:.1f} KB",
        title="知识库状态",
        border_style="green",
    ))

    db.close()


def cmd_query(args, config: Config):
    """查询知识库。"""
    db = Database(config.db_path)

    # 自动检测模式
    db_size = db.get_db_size()
    mode = "enhanced" if db_size >= config.enhanced_mode_threshold else "light"

    # 如果用户指定了 --enhance 但数据库不够大，提示
    if args.enhance and mode == "light":
        console.print("  [yellow]数据库较小 (<10MB)，使用轻量查询即可。忽略 --enhance 标志。[/yellow]")
        args.enhance = False

    # 检查依赖
    if not check_all_for_query(enhanced=args.enhance):
        console.print("  [red]依赖检查失败[/red]")
        db.close()
        sys.exit(1)

    searcher = Searcher(db, enhanced=args.enhance)
    results = searcher.search(args.query, limit=args.limit, kb_type=args.kb_type)

    if args.as_json:
        output = []
        for kp in results:
            output.append({
                "id": kp.id,
                "type": kp.kb_type,
                "title": kp.title,
                "content": kp.content,
                "signature": kp.signature,
                "code_example": kp.code_example,
                "tags": kp.tags,
            })
        console.print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        formatted = searcher.format_results(results, args.query)
        console.print(formatted)

    db.close()


def cmd_list(config: Config):
    """列出已导入的文档。"""
    db = Database(config.db_path)
    docs = db.list_documents()

    if not docs:
        console.print("  [dim]知识库为空。使用 import 命令导入文档。[/dim]")
        db.close()
        return

    table = Table(title="已导入的文档")
    table.add_column("ID", style="dim")
    table.add_column("名称")
    table.add_column("版本")
    table.add_column("领域")
    table.add_column("页码")
    table.add_column("导入时间")

    for doc in docs:
        table.add_row(
            str(doc.id), doc.name, doc.version, doc.domain,
            str(doc.total_pages), doc.imported_at[:19],
        )

    console.print(table)
    db.close()


def cmd_stats(config: Config):
    """知识库统计。"""
    db = Database(config.db_path)
    stats = db.get_stats()
    size_mb = stats["size_bytes"] / (1024 * 1024)
    mode = "增强" if stats["size_bytes"] >= config.enhanced_mode_threshold else "轻量"

    table = Table(title=f"知识库统计 (模式: {mode})")
    table.add_column("指标")
    table.add_column("值")

    table.add_row("文档数量", str(stats["documents"]))
    table.add_row("知识点数量", str(stats["knowledge_points"]))
    table.add_row("标签数量", str(stats["tags"]))
    table.add_row("数据库大小", f"{size_mb:.2f} MB")
    table.add_row("当前模式", mode)

    console.print(table)
    db.close()


def cmd_delete(args, config: Config):
    """删除文档。"""
    db = Database(config.db_path)
    doc = db.find_document_by_name(args.name)
    if not doc:
        console.print(f"  [red]未找到文档: {args.name}[/red]")
        db.close()
        sys.exit(1)

    from rich.prompt import Confirm
    if not Confirm.ask(f"确定删除文档 '{args.name}' 及其所有数据？"):
        console.print("  [dim]已取消[/dim]")
        db.close()
        return

    # Git 备份
    _git_backup(config, f"delete: {args.name} v{doc.version}")

    db.delete_document(doc.id)
    console.print(f"  [green]已删除文档: {args.name}[/green]")
    db.close()


def cmd_update(args, config: Config):
    """更新文档（git 备份旧版本后重新导入）。"""
    db = Database(config.db_path)
    doc = db.find_document_by_name(args.name)
    if not doc:
        console.print(f"  [red]未找到文档: {args.name}，请先 import[/red]")
        db.close()
        sys.exit(1)

    console.print(Panel(f"更新文档: {args.name} v{doc.version} → {args.version or '新版'}",
                        title="文档更新", border_style="yellow"))

    # Git 备份当前状态
    _git_backup(config, f"backup: {args.name} v{doc.version} before update")

    # 删除旧数据
    db.delete_document(doc.id)
    console.print(f"  [dim]已删除旧版数据[/dim]")

    # 重新导入（复用 import 逻辑）
    from argparse import Namespace
    import_args = Namespace(
        pdf=args.pdf,
        name=args.name,
        version=args.version or doc.version,
        domain=args.domain or doc.domain,
        no_agent=False,
        enhance=False,
    )
    cmd_import(import_args, config)
    db.close()


def _git_backup(config: Config, message: str):
    """Git 备份当前知识库状态。"""
    import subprocess
    try:
        # 检查是否在 git 仓库中
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, cwd=str(config.workdir)
        )
        if result.returncode != 0:
            console.print("  [yellow]不在 git 仓库中，跳过备份[/yellow]")
            return

        # 检查是否有未提交的变更
        status = subprocess.run(
            ["git", "status", "--porcelain", "kb/"],
            capture_output=True, text=True, cwd=str(config.workdir)
        )
        if not status.stdout.strip():
            console.print("  [dim]kb/ 无变更，无需备份[/dim]")
            return

        # 提交
        subprocess.run(
            ["git", "add", "kb/"],
            capture_output=True, cwd=str(config.workdir)
        )
        subprocess.run(
            ["git", "commit", "-m", f"[pdf-to-skill] {message}"],
            capture_output=True, cwd=str(config.workdir)
        )
        console.print(f"  [green]Git 备份: {message}[/green]")
    except FileNotFoundError:
        console.print("  [yellow]git 未安装，跳过备份[/yellow]")
    except Exception as e:
        console.print(f"  [yellow]Git 备份失败: {e}[/yellow]")


if __name__ == "__main__":
    main()

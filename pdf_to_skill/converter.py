"""PDF → Markdown 转换 — 支持 markitdown、PyMuPDF、OCR 三种方式。"""

import hashlib
import shutil
from pathlib import Path

from rich.console import Console

from .config import Config
from .models import Document

console = Console()


def _file_hash(path: Path) -> str:
    """计算 PDF 文件的 SHA256。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def _has_text_layer(pdf_path: str) -> bool:
    """检查 PDF 是否有文本层（非扫描件）。"""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        for i in range(min(3, len(doc))):
            text = doc[i].get_text("text")
            if text.strip():
                doc.close()
                return True
        doc.close()
        return False
    except Exception:
        return False


def _ocr_extract(pdf_path: str) -> str:
    """使用 RapidOCR 提取扫描件文字。"""
    console.print("  [dim]检测为扫描件，使用 RapidOCR 提取 ...[/dim]")

    from rapidocr_onnxruntime import RapidOCR
    import pypdfium2 as pdfium
    import numpy as np

    ocr = RapidOCR()
    pdf = pdfium.PdfDocument(pdf_path)
    total = len(pdf)
    console.print(f"  [dim]共 {total} 页，正在 OCR 提取 ...[/dim]")

    full_text = []
    for i in range(total):
        page = pdf[i]
        bitmap = page.render(scale=2)
        img = np.array(bitmap.to_pil())
        result, _ = ocr(img)
        if result:
            page_text = "\n".join([item[1] for item in result])
            full_text.append(f"## Page {i+1}\n\n{page_text}")
            console.print(f"  [dim]  第 {i+1}/{total} 页: {len(page_text)} 字符[/dim]")
        else:
            full_text.append(f"## Page {i+1}\n\n")
    pdf.close()

    return "\n\n".join(full_text)


def pdf_to_markdown(pdf_path: str, config: Config) -> tuple[str, str]:
    """
    将 PDF 转换为 Markdown。

    返回: (markdown_content, 文件hash)
    优先级: markitdown → PyMuPDF → RapidOCR (扫描件)
    """
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

    file_hash = _file_hash(pdf_file)

    # 1. 尝试 markitdown
    try:
        from markitdown import MarkItDown
        console.print("  [dim]使用 markitdown 转换 PDF ...[/dim]")
        md = MarkItDown()
        result = md.convert(str(pdf_file))
        content = result.text_content
        if content and len(content.strip()) > 100:
            return content, file_hash
        console.print("  [yellow]markitdown 输出过短，尝试 PyMuPDF[/yellow]")
    except ImportError:
        pass
    except Exception as e:
        console.print(f"  [yellow]markitdown 失败 ({type(e).__name__})，尝试 PyMuPDF[/yellow]")

    # 2. 尝试 PyMuPDF
    try:
        import fitz
        console.print("  [dim]使用 PyMuPDF 提取文字 ...[/dim]")
        doc = fitz.open(str(pdf_file))
        pages_content = []
        for i, page in enumerate(doc):
            text = page.get_text("text")
            if text.strip():
                pages_content.append(f"## Page {i+1}\n\n{text}")
        doc.close()
        content = "\n\n".join(pages_content)
        if content.strip():
            return content, file_hash
        console.print("  [yellow]PyMuPDF 提取为空（扫描件），使用 OCR[/yellow]")
    except ImportError:
        pass
    except Exception as e:
        console.print(f"  [yellow]PyMuPDF 失败 ({e})，使用 OCR[/yellow]")

    # 3. OCR 提取
    if _has_text_layer(pdf_path):
        console.print("  [yellow]检测到文本层但提取失败，重试 PyMuPDF[/yellow]")
        # 重试一次 PyMuPDF
        try:
            import fitz
            doc = fitz.open(pdf_path)
            pages_content = []
            for i, page in enumerate(doc):
                text = page.get_text("dict")
                blocks = text.get("blocks", [])
                for block in blocks:
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            t = span.get("text", "").strip()
                            if t:
                                pages_content.append(t)
            doc.close()
            content = "\n".join(pages_content)
            if content.strip():
                return content, file_hash
        except Exception:
            pass

    try:
        return _ocr_extract(pdf_path), file_hash
    except ImportError:
        raise RuntimeError(
            "无法转换 PDF（无文本层且无 OCR 引擎）。\n"
            "请安装: pip install rapidocr_onnxruntime pypdfium2"
        )
    except Exception as e:
        raise RuntimeError(f"OCR 提取失败: {e}")


def split_markdown(content: str, config: Config, n_chunks: int = 5) -> list[Path]:
    """
    将 Markdown 内容拆分为 N 个临时文件，用于并行分析。

    按行近似均分，保留标题边界（不在 ## 标题中间切断）。
    """
    lines = content.split("\n")
    chunk_size = max(1, len(lines) // n_chunks)
    chunks = []

    for i in range(n_chunks):
        start = i * chunk_size
        end = start + chunk_size if i < n_chunks - 1 else len(lines)

        # 向前找到最近的标题行作为切割点
        if end < len(lines):
            for j in range(end, max(end - 50, start), -1):
                if j < len(lines) and lines[j].strip().startswith("#"):
                    end = j
                    break

        chunk_lines = lines[start:end]
        if chunk_lines:
            chunks.append("\n".join(chunk_lines))

    # 写入临时文件
    config.temp_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for idx, chunk in enumerate(chunks):
        p = config.temp_dir / f"part{idx+1}.md"
        p.write_text(chunk, encoding="utf-8")
        paths.append(p)

    return paths


def save_source(pdf_path: str, config: Config, doc_name: str) -> Path:
    """复制原始 PDF 到 sources 目录。"""
    config.sources_dir.mkdir(parents=True, exist_ok=True)
    dest = config.sources_dir / f"{doc_name}.pdf"
    # 如果已存在同名文件，先备份
    if dest.exists():
        backup = dest.with_suffix(".pdf.bak")
        shutil.copy2(str(dest), str(backup))
        console.print(f"  [dim]已备份旧源文件 → {backup.name}[/dim]")
    shutil.copy2(pdf_path, str(dest))
    return dest

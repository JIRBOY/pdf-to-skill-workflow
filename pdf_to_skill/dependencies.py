"""依赖检查与安装提示 — 不静默安装，必须用户确认。"""

import importlib
import subprocess
import sys

from rich.console import Console
from rich.prompt import Confirm

console = Console()

REQUIRED_DEPS = {
    "markitdown": "markitdown",
    "rich": "rich",
}

OPTIONAL_DEPS = {
    "anthropic": "anthropic",
    "openai": "openai",
    "httpx": "httpx",
    "sentence_transformers": "sentence-transformers",
    "numpy": "numpy",
}

# 哪些可选依赖属于 "enhanced" 模式
ENHANCED_DEPS = {"anthropic", "openai", "httpx"}
VECTOR_DEPS = {"sentence_transformers", "numpy"}


def _check(module: str) -> bool:
    try:
        importlib.import_module(module)
        return True
    except ImportError:
        return False


def _install(package: str) -> bool:
    console.print(f"\n  正在安装 {package} ...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode == 0
    except Exception as e:
        console.print(f"  [red]安装失败: {e}[/red]")
        return False


def check_required() -> bool:
    """检查必需依赖，缺失时提示安装。返回是否全部可用。"""
    missing = {mod: pkg for mod, pkg in REQUIRED_DEPS.items() if not _check(mod)}
    if not missing:
        return True

    for module, package in missing.items():
        console.print(f"\n  [yellow]缺少依赖: {module}[/yellow]")
        console.print(f"  用于 PDF 转 Markdown 转换，需要安装 {package}。")
        if Confirm.ask("  现在安装？", default=True):
            if not _install(package):
                console.print(f"  [red]{package} 安装失败，请手动执行: pip install {package}[/red]")
                return False

    return True


def check_enhanced(auto_skip: bool = False) -> bool:
    """检查增强模式依赖（Agent 精炼 + 网络搜索）。"""
    missing = {mod: pkg for mod, pkg in OPTIONAL_DEPS.items() if mod in ENHANCED_DEPS and not _check(mod)}
    if not missing:
        return True

    if auto_skip:
        return False

    console.print(f"\n  [yellow]增强模式需要以下依赖: {', '.join(missing.values())}[/yellow]")
    console.print("  用于 Agent 语义精炼和网络搜索辅助。")
    if Confirm.ask("  安装增强模式依赖？", default=True):
        for module, package in missing.items():
            if not _install(package):
                console.print(f"  [red]{package} 安装失败[/red]")
                return False
        return True
    return False


def check_vector(auto_skip: bool = False) -> bool:
    """检查向量检索依赖。"""
    missing = {mod: pkg for mod, pkg in OPTIONAL_DEPS.items() if mod in VECTOR_DEPS and not _check(mod)}
    if not missing:
        return True

    if auto_skip:
        return False

    console.print(f"\n  [yellow]向量检索需要: {', '.join(missing.values())}[/yellow]")
    if Confirm.ask("  安装？（可选，用于语义相似度搜索）", default=True):
        for module, package in missing.items():
            if not _install(package):
                console.print(f"  [red]{package} 安装失败[/red]")
                return False
        return True
    return False


def check_all_for_import() -> bool:
    """导入 PDF 前检查所有可能需要的依赖。"""
    if not check_required():
        return False
    # 增强模式依赖在查询时才需要，导入时不检查
    return True


def check_all_for_query(enhanced: bool = False) -> bool:
    """查询前检查依赖。"""
    if not check_required():
        return False
    if enhanced:
        return check_enhanced()
    return True

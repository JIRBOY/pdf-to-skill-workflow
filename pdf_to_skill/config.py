"""路径配置 — 不硬编码任何绝对路径。"""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    """运行时路径配置，全部支持环境变量或 CLI 参数覆盖。"""

    # 工作目录：默认当前目录，可通过 PDF_SKILL_WORKDIR 覆盖
    workdir: Path = field(default_factory=lambda: Path(os.getenv("PDF_SKILL_WORKDIR", ".")))

    # 知识库子目录
    kb_dir_name: str = "kb"
    sources_dir_name: str = "sources"
    db_filename: str = "skills.db"

    # 数据库路径：环境变量 PDF_SKILL_DB 优先，否则在 workdir/kb/skills.db
    db_path: Path = field(init=False)

    # 原始 PDF 存储目录
    sources_dir: Path = field(init=False)

    # 临时目录（PDF 转 MD 的中间文件）
    temp_dir: Path = field(init=False)

    # Prompt 模板目录（相对于包路径）
    prompts_dir: Path = field(init=False)

    # 增强模式阈值（字节）
    enhanced_mode_threshold: int = 10 * 1024 * 1024  # 10MB

    def __post_init__(self):
        db_env = os.getenv("PDF_SKILL_DB")
        if db_env:
            self.db_path = Path(db_env)
        else:
            self.db_path = self.workdir / self.kb_dir_name / self.db_filename

        self.sources_dir = self.workdir / self.kb_dir_name / self.sources_dir_name
        self.temp_dir = self.workdir / self.kb_dir_name / "temp"

        # Prompts 目录在包内
        import pdf_to_skill
        pkg_dir = Path(pdf_to_skill.__file__).parent
        self.prompts_dir = pkg_dir / "prompts"

    def ensure_dirs(self):
        """创建所需目录（如果不存在）。"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    @property
    def kb_dir(self) -> Path:
        return self.db_path.parent

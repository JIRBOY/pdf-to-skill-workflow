# CLAUDE.md — PDF to Skill Workflow

## 项目概述

将技术文档（PDF、HTML、API 手册等）转化为可检索的 SQLite 知识库技能。核心产物：**SQLite 数据库**（含 FTS5 全文索引）+ **SKILL.md**（使用指南）。

核心原则：PDF → Markdown → 领域提取 → SQLite 索引 → FTS5/Agent 查询。

## 项目结构

```
pdf-to-skill-workflow/
├── SKILL.md                    # 技能文件（使用指南）
├── CLAUDE.md                   # 本文档（开发上下文）
├── pyproject.toml              # Python 项目配置
├── requirements.txt            # 依赖列表
├── .gitignore                  # Git 忽略规则
└── pdf_to_skill/
    ├── __init__.py             # 包入口
    ├── __main__.py             # python -m pdf_to_skill
    ├── cli.py                  # CLI 入口（6 个子命令）
    ├── config.py               # 路径配置（零硬编码）
    ├── dependencies.py         # 依赖检查与安装提示
    ├── converter.py            # PDF → Markdown（三级提取链）
    ├── extractor.py            # 知识点提取（6 种领域 prompt）
    ├── indexer.py              # 索引构建（文档→章节→知识点）
    ├── searcher.py             # 查询接口（FTS5 + Agent 增强）
    ├── db.py                   # 数据库管理（Schema + CRUD + FTS5 触发器）
    ├── models.py               # 数据模型（Document/Chapter/KnowledgePoint）
    └── prompts/                # 领域 Prompt 模板
        ├── api_doc.md          # API 文档提取 prompt
        ├── database.md         # 数据库文档提取 prompt
        ├── framework.md        # 框架文档提取 prompt
        ├── protocol.md         # 协议/标准提取 prompt
        ├── internal.md         # 内部文档提取 prompt
        └── general.md          # 通用提取 prompt
```

## CLI 命令

| 命令 | 用途 | 关键参数 |
|------|------|---------|
| `import` | 导入 PDF | `--name`, `--version`, `--domain`, `--no-agent` |
| `query` | 查询知识库 | `--type`, `--limit`, `--enhance`, `--json` |
| `list` | 列出已导入文档 | — |
| `stats` | 知识库统计信息 | — |
| `delete` | 删除文档（git 备份） | `name` |
| `update` | 更新文档（git 备份 → 删除 → 重新导入） | `--name`, `--version`, `--domain` |

## 核心架构

### PDF 提取链（三级降级）
1. **markitdown** — 通用 PDF → Markdown 转换（首选）
2. **PyMuPDF (fitz)** — 直接提取 PDF 文本层
3. **RapidOCR + pypdfium2** — OCR 处理扫描件

### 知识点存储
- **SQLite** + **FTS5** 全文索引
- 自动同步触发器（INSERT/UPDATE/DELETE → FTS5）
- 10 列 Schema：id, document_id, chapter_id, kb_type, title, content, code_example, signature, parameters, return_type, page_ref

### 查询模式（10MB 阈值）
- **轻量模式（<10MB）** — FTS5 全文搜索 + LIKE fallback
- **增强模式（>=10MB）** — FTS5 + Agent 精炼 + 网络搜索补充

### 领域提取策略
6 种领域类型自动检测或手动指定：`api_doc`, `protocol`, `framework`, `database`, `internal`, `general`

## 开发约定

- **零硬编码路径** — 所有路径通过 `--db`、`--workdir` 或环境变量（`PDF_SKILL_DB`、`PDF_SKILL_WORKDIR`）指定
- **依赖透明** — 缺失依赖时提示用户确认，不静默安装
- **单版本原则** — 同一技能文件夹只保留一个文档版本
- **中文写作** — SKILL.md 和用户界面用中文，代码示例保持英文
- **Python >= 3.10** — 使用 `match` 语句等现代语法
- **Windows UTF-8** — `sys.stdout.reconfigure(encoding="utf-8")` 解决编码问题

## 依赖说明

| 类型 | 包 | 用途 |
|------|-----|------|
| **必需** | `markitdown` | PDF → Markdown |
| **必需** | `rich` | CLI 美化输出 |
| **必需** | `pypdfium2` | PDF 文本层提取 + OCR 图像渲染 |
| **必需** | `PyMuPDF (fitz)` | 备用 PDF 文本提取 |
| **可选** | `rapidocr_onnxruntime` | 扫描件 OCR |
| **可选** | `anthropic` | Agent 精炼（增强模式） |
| **可选** | `openai` | 备用 LLM API（增强模式） |
| **可选** | `httpx` | 网络搜索（增强模式） |
| **可选** | `sentence-transformers` + `numpy` | 向量语义检索 |

## 测试验证

已通过端到端测试（`six-axis-shaking-table`，32 页扫描件）：
- import → 1 文档 + 32 章节 + 15 知识点
- query → FTS5 搜索返回正确结果
- list/stats → 表格和统计输出正确

## 持续优化方向

1. **PDF 提取质量** — 表格、代码块、图片描述提取
2. **Agent 提取集成** — 在 cli.py 中接入 Claude Code Agent 替代规则提取
3. **向量检索** — 集成 sentence-transformers 做语义相似度搜索
4. **网络搜索** — 增强模式下通过 httpx 调用外部搜索 API 补充
5. **多格式支持** — 除 PDF 外支持 HTML、Word、Markdown 导入
6. **Web UI** — 简单的 Web 界面用于浏览和查询知识库
7. **导出功能** — 将知识库导出为 SKILL.md 格式的纯文本技能文件

## 常见陷阱

- 不要硬编码任何绝对路径
- 不要静默安装依赖，必须用户确认
- 不要让同名文档重复导入（检查 name 和 hash）
- 更新文档时必须先 git 备份旧版
- SKILL.md 不是完整知识库，只是检索入口和使用指南
- `.claude/settings.local.json` 包含本地权限记录，已加入 .gitignore

---
name: pdf-to-skill-workflow
description: 将技术文档（PDF/手册/API 文档）转化为可检索的知识库技能。适用于任何领域的知识管理——框架文档、SDK 手册、协议规范、内部 API 文档等。当用户提供大型技术文档或需要查询已导入的知识库时使用。
type: workflow
---

# 文档转知识库技能

将大型技术文档转化为 SQLite 存储的知识库，支持 FTS5 全文检索和 Agent 语义精炼查询。

## 何时触发

- 用户提供 PDF 技术手册（框架文档、SDK 手册、协议规范等）
- 需要将某个领域的官方文档转化为可检索的知识库
- 需要查询已导入的知识库内容
- 遇到大型文档无法直接用 Read 工具完整阅读

## 核心原则

1. **知识库模式** — PDF 转为 SQLite 数据库，按章节/主题/知识点结构化存储
2. **规模自适应** — 小库 (<10MB) 直接 FTS5 检索，大库 (>=10MB) 启用 Agent 精炼
3. **依赖透明** — 缺失依赖时提示用户确认安装，不静默安装
4. **路径零硬编码** — 所有路径通过 CLI 参数或环境变量指定
5. **单版本原则** — 同一技能文件夹只保留一个文档版本，更新时 git 备份旧版

## 知识库结构

```
pdf_to_skill/
├── __init__.py        # 包入口
├── __main__.py        # python -m pdf_to_skill
├── cli.py             # CLI 入口（import/query/update/delete/stats/list）
├── config.py          # 路径配置（动态，零硬编码）
├── dependencies.py    # 依赖检查与安装提示
├── converter.py       # PDF → Markdown（markitdown / PyMuPDF 备选）
├── extractor.py       # 知识点提取（领域专用 prompt 策略）
├── indexer.py         # 索引构建（写入 SQLite）
├── searcher.py        # 查询接口（FTS5 + Agent 精炼）
├── db.py              # 数据库管理（Schema + FTS5 + CRUD）
├── models.py          # 数据模型
└── prompts/           # Prompt 模板目录
```

## 使用方式

### 导入 PDF

```bash
# 基础导入
python -m pdf_to_skill import doc.pdf --name "框架名称" --version "1.0"

# 指定领域类型（可选，默认自动检测）
python -m pdf_to_skill import api.pdf --name "MyAPI" --domain api_doc

# 自定义数据库路径和工作目录
python -m pdf_to_skill import doc.pdf --name "Doc" --db /path/to/kb.db --workdir /path/to/work
```

支持的领域类型：`api_doc`、`protocol`、`framework`、`database`、`internal`、`general`

### 查询知识库

```bash
# 轻量查询（数据库 < 10MB 时自动使用）
python -m pdf_to_skill query "如何创建连接"

# 按类型过滤
python -m pdf_to_skill query "错误码" --type error

# 增强查询（数据库 >= 10MB 时启用 Agent 语义精炼）
python -m pdf_to_skill query "异步回调处理" --enhance

# JSON 输出（供脚本处理）
python -m pdf_to_skill query "API" --json
```

### 管理

```bash
# 列出已导入文档
python -m pdf_to_skill list

# 查看统计信息
python -m pdf_to_skill stats

# 删除文档（git 备份后删除）
python -m pdf_to_skill delete "旧文档名"

# 更新文档（git 备份旧版本，重新导入新版）
python -m pdf_to_skill update new.pdf --name "文档名" --version "2.0"
```

## 依赖说明

**必需依赖**（导入和查询都需要）：
- `markitdown` — PDF 转 Markdown
- `rich` — CLI 输出美化

**可选依赖**（查询时按需安装）：
- `anthropic` / `openai` — Agent 语义精炼（增强模式）
- `httpx` — 网络搜索辅助
- `sentence-transformers` / `numpy` — 向量相似度搜索

缺失依赖时 CLI 会提示用户确认安装，不会静默安装。

## 模式自适应

| 模式 | 数据库大小 | 查询方式 | 速度 | 精度 |
|------|-----------|---------|------|------|
| 轻量 | < 10MB | FTS5 全文检索 | 毫秒级 | 关键词匹配 |
| 增强 | >= 10MB | FTS5 初筛 → Agent 精炼 → 网络补充 | 秒级 | 语义理解 |

模式自动切换，用户无需手动选择。

## 领域专用提取策略

提取知识点时，根据文档类型使用专用 prompt：

| 领域 | 提取重点 |
|------|---------|
| API/SDK 文档 | 方法签名、参数、返回值、代码示例 |
| 协议规范 | 包结构、命令 ID、端口映射、错误码 |
| 框架文档 | 组件、生命周期、配置、设计模式 |
| 数据库文档 | SQL 语法、数据类型、系统表、错误码 |
| 内部文档 | API 接口、枚举、业务规则、数据结构 |
| 通用 | 自动检测最常见编程元素 |

## 增量更新策略

- **同一技能文件夹只保留一个文档版本**
- 更新时先通过 git 提交备份旧版数据，再删除旧数据并导入新版
- 不同文档可以共存（按 `name` 区分）
- 相同文件 hash 的 PDF 会被拒绝重复导入

## 适用文档类型

| 文档类型 | 示例 | 提取重点 |
|---------|------|---------|
| API 文档 | SDK 手册、REST API 参考 | 方法签名、参数、返回类型、示例 |
| 协议规范 | ADS、Modbus、OPC UA | 包结构、命令 ID、错误码、端口 |
| 框架文档 | React、Spring、Django 文档 | 组件、生命周期、配置项 |
| 数据库文档 | PostgreSQL、MySQL 参考 | SQL 语法、函数、数据类型映射 |
| 内部文档 | 公司 API 文档、设计文档 | 接口定义、枚举值、业务规则 |

## 质量检查清单

生成知识库后验证：
- [ ] 知识点数量是否合理（不应为 0）
- [ ] 代码示例是否完整（非截断）
- [ ] 领域类型是否正确检测
- [ ] 数据库是否可以正常查询
- [ ] 查询结果是否有相关性
- [ ] FTS5 索引是否正确构建（查询命中）

---
name: pdf-to-skill-workflow
description: 将技术文档（PDF/手册/API 文档）转化为 Claude Code 技能文件的标准工作流。适用于任何领域的知识管理——框架文档、SDK 手册、协议规范、内部 API 文档等。当用户提供大型技术文档时使用。
type: workflow
---

# 文档转技能标准工作流

将大型技术文档（PDF、HTML 文档、API 参考手册等）转化为结构化的 Claude Code 技能文件，使编程时能精准索引领域知识，避免幻觉。

## 何时触发

- 用户提供 PDF 技术手册（框架文档、SDK 手册、协议规范等）
- 需要将某个领域的官方文档转化为可复用的编程技能
- 遇到大型文档无法直接用 Read 工具完整阅读
- 需要对技术文档做结构化提取（API、枚举、错误码、配置项等）

## 核心原则

1. **大文件不要直接 Read** — PDF 超过 50 页时，先拆分为 MD 再阅读，否则上下文被撑满
2. **分而治之** — 拆分后用独立 Agent 并行分析各部分
3. **双产物输出** — SKILL.md（编程指南） + JSON 索引（结构化查询）
4. **领域无关** — 流程适用于任何技术文档，不限编程语言或领域

## 标准流程

### 步骤 1：PDF 转 MD

使用 PyMuPDF 脚本将大 PDF 拆分为 5 个左右的临时 `.md` 文件。

```python
# pdf_extract.py — 通用 PDF 拆分脚本
import fitz, os

pdf_path = "path/to/document.pdf"
out_dir = "temp_parts"
os.makedirs(out_dir, exist_ok=True)

doc = fitz.open(pdf_path)
total = len(doc)
chunk = total // 5 + 1

for idx in range(5):
    start = idx * chunk
    end = min(start + chunk, total)
    if start >= total: break
    out_path = os.path.join(out_dir, f"part{idx+1}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# {os.path.basename(pdf_path)} - Part {idx+1}\n")
        f.write(f"# Pages: {start+1} - {end}\n\n")
        for page_num in range(start, end):
            page = doc[page_num]
            f.write(f"\n## Page {page_num+1}\n\n{page.get_text('text')}")
```

运行后得到 5 个 `part1.md` ~ `part5.md` 文件。

### 步骤 2：分 Agent 并行分析

每个临时文件派发给独立 Agent 进行知识提取：

```
Agent prompt 模板:
"这是某技术文档的第 X 部分（共 5 部分）。
提取所有编程相关的知识：API 类/方法/参数、代码示例、枚举值、
常量、配置项、错误码、类型映射、使用模式。
返回结构化摘要，包含类名、方法签名、代码片段和关键常量。"
```

各 Agent 独立运行，互不阻塞，结果汇总后进入下一步。

### 步骤 3：生成 SKILL.md

整合所有 Agent 分析结果，生成主技能文件。结构模板：

```markdown
---
name: <领域简称>
description: <一句话描述适用场景>
type: programming
---

# <领域名称> 编程技能

## 何时触发
- 场景 1
- 场景 2

## 1. 快速开始
- 安装/配置
- 最简示例

## 2. 核心 API / 协议规范
- 类/接口/方法清单
- 参数说明
- 代码示例

## 3. 数据类型 / 枚举
- 类型映射表
- 枚举值速查

## 4. 高级模式 / 最佳实践
- 模式 1
- 模式 2

## 5. 错误码 / 故障排查
- 常见错误速查表
```

**SKILL.md 写作规则：**
- 代码示例必须是完整可运行的（非伪代码）
- 表格优于段落（快速扫描）
- 标注"推荐"和"避免"的做法
- 注明版本信息

### 步骤 4：生成 JSON 索引

创建 `api-index.json` 供结构化查询：

```json
{
  "meta": {
    "name": "<索引名称>",
    "version": "1.0.0",
    "source": "<原始文档名称和版本>"
  },
  "namespaces": [
    {
      "name": "<命名空间/模块名>",
      "description": "<用途>",
      "classes": ["类1", "类2"],
      "interfaces": ["接口1"]
    }
  ],
  "enums": {
    "枚举名": { "值1": 0, "值2": 1 }
  },
  "error_codes": {
    "0x001": { "name": "ERROR_NAME", "desc": "描述" }
  },
  "type_mapping": { "源类型": "目标类型" },
  "constants": { "常量名": "值" },
  "reference_tables": {
    "端口映射": { "851": "TC3 PLC Runtime 1" },
    "索引组": { "0x4020": "%M 字段" }
  }
}
```

### 步骤 5：存储

```
skills/
├── <手册简称>/
│   └── SKILL.md              ← 编程指南
└── <领域>-API-Reference/
    └── api-index.json        ← 结构化查询索引
```

## 适用文档类型

| 文档类型 | 示例 | 提取重点 |
|---------|------|---------|
| API 文档 | SDK 手册、REST API 参考 | 方法签名、参数、返回类型、示例 |
| 协议规范 | ADS、Modbus、OPC UA | 包结构、命令 ID、错误码、端口 |
| 框架文档 | React、Spring、Django 文档 | 组件、生命周期、配置项 |
| 数据库文档 | PostgreSQL、MySQL 参考 | SQL 语法、函数、数据类型映射 |
| 内部文档 | 公司 API 文档、设计文档 | 接口定义、枚举值、业务规则 |

## 质量检查清单

生成技能后验证：
- [ ] 代码示例是否完整可运行
- [ ] 是否标注了版本信息
- [ ] 枚举值和常量是否完整
- [ ] 错误码是否有排查建议
- [ ] JSON 索引是否能正确解析
- [ ] SKILL.md 触发场景描述是否清晰

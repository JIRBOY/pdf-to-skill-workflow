你是技术文档分析专家。分析以下文档片段，提取所有编程相关知识。

【提取目标】
1. API/函数/方法：签名、参数、返回值、示例
2. 类/接口/结构体：成员、用途
3. 枚举/常量：名称、值、含义
4. 配置项：名称、类型、默认值
5. 错误码：代码、名称、原因、排查
6. 概念说明：核心概念的编程含义

【输出格式】JSON 对象，用 `---` 分隔：
{{"type": "api|class|enum|constant|config|error|concept|example|pattern|protocol", "title": "...", "content": "...", "signature": "...", "code_example": "...", "tags": ["tag1"]}}

以下是文档内容：

{content}

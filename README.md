# 基于 Agent SDK 的智能面试模拟系统

面向求职准备场景的 LLM 模拟面试系统，支持根据简历和岗位 JD 自动生成面试题、多轮追问和结构化评估报告。

## 核心设计

- **双层 Prompt 架构**：Orchestrator 管理出题与追问流程，Evaluator 独立负责逐题评分与四维度综合评估
- **多 Agent 编排**：出题 Agent、评估 Agent、知识库 Agent、候选人 Agent 各司其职，由 InterviewEngine 统一调度
- **状态机驱动**：idle → ready → in_progress → finished 四阶段流转
- **追问机制**：硬规则前置守卫（空回答/放弃类关键词拦截）+ LLM 语义判断 + 每题最多 1 次追问
- **结构化输出**：Pydantic v2 定义数据模型 + Agents SDK output_type 自动解析

## 技术栈

Python / OpenAI Agents SDK / FastAPI / Pydantic v2 / Vue 3

## 快速启动

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

编辑 `config/system_config.json`，填入你的 API Key 和 Base URL：

```json
{
  "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "api_key": "your-api-key-here",
  "default_model": "qwen-flash",
  "jina_key": "your-jina-key-here"
}
```

### 3. 启动后端

```bash
uvicorn api.app:app --reload --port 8000
```

访问 `http://localhost:8000/docs` 查看 Swagger API 文档。

### 4. 启动前端（可选）

```bash
cd frontend
npm install
npm run dev -- --port 5173
```

浏览器打开 `http://localhost:5173`。

### 5. 命令行演示

```bash
python main_demo_manual.py   # 人工回答模式
python main_demo_auto.py     # AI 自动回答模式
```

### 6. 运行测试

```bash
pytest tests/ -v
```

## 项目结构

```
├── agent/          # Agent 定义（出题、评估、知识库、候选人）
├── engine/         # 面试流程编排引擎（状态机 + 追问逻辑）
├── schema/         # Pydantic 数据模型
├── api/            # FastAPI 路由 + SessionManager 会话管理
├── config/         # 配置文件
├── assert/         # 简历样例、JD 样例、知识库题库
├── tests/          # pytest 测试
├── frontend/       # Vue 3 前端
└── tools/          # 工具函数（文件解析、Jina 搜索）
```

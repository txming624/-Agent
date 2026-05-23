# 运维排障 Agent

自动化故障诊断系统：**日志分析 → 根因定位 → 修复建议**

## 功能特性

- 🔍 **日志分析Agent** - 从原始日志中提取关键信息、识别异常模式
- 🎯 **根因定位Agent** - 基于RAG知识库定位故障根本原因
- 🛠️ **修复建议Agent** - 生成具体可执行的修复方案

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                      Orchestrator                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Log Analysis │→│ Root Cause   │→│ Fix Suggest  │      │
│  │    Agent     │  │    Agent     │  │    Agent     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         ↑                ↑                                   │
│  ┌──────────────┐  ┌──────────────┐                         │
│  │Log Collector │  │ RAG Knowledge│                         │
│  │(Local + ES)  │  │    Base      │                         │
│  └──────────────┘  └──────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```env
# LLM配置 (支持OpenAI兼容接口)
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o

# Elasticsearch配置 (可选)
ES_HOSTS=localhost:9200
ES_USERNAME=
ES_PASSWORD=

# RAG配置
EMBEDDING_MODEL=text-embedding-3-small
VECTOR_DB_PATH=./data/chroma_db
```

### 3. 运行

```bash
# 交互模式
python -m ops_agent

# 分析本地日志
python -m ops_agent --source local --hours 24

# 分析ES日志
python -m ops_agent --source es --hours 6 --keywords "error,timeout"

# 演示模式
python -m ops_agent --demo

# 初始化知识库
python -m ops_agent --init-kb ./ops_agent/data/fault_library.json
```

## 使用示例

### Python API调用

```python
from ops_agent import load_config, Orchestrator

# 初始化
config = load_config()
orchestrator = Orchestrator(config)
orchestrator.init_knowledge_base("./ops_agent/data/fault_library.json")

# 诊断
result = orchestrator.diagnose(
    source_type="local",
    hours=24,
    keywords=["error", "exception"]
)

# 输出报告
print(result.generate_report())
```

### 交互模式命令

```
ops-agent> analyze local --hours 24           # 分析本地日志
ops-agent> analyze es --hours 6               # 分析ES日志
ops-agent> search mysql 连接池                 # 搜索故障库
ops-agent> status                             # 查看系统状态
ops-agent> demo                               # 运行演示
```

## 项目结构

```
ops_agent/
├── __init__.py          # 包初始化
├── __main__.py          # 命令行入口
├── config.py            # 配置管理
├── orchestrator.py      # Agent编排器
├── main.py              # 主程序
├── agents/              # Agent实现
│   ├── base.py          # Agent基类
│   ├── log_analysis_agent.py    # 日志分析Agent
│   ├── root_cause_agent.py      # 根因定位Agent
│   └── fix_suggestion_agent.py  # 修复建议Agent
├── collectors/          # 日志采集
│   └── log_collector.py # 支持本地文件+ES
├── rag/                 # RAG知识库
│   └── knowledge_base.py
├── data/                # 数据文件
│   └── fault_library.json  # 历史故障库
└── utils/               # 工具函数
```

## 扩展故障库

编辑 `ops_agent/data/fault_library.json` 添加新的故障案例：

```json
{
  "id": "FAULT-013",
  "title": "故障标题",
  "category": "故障分类",
  "symptoms": ["症状1", "症状2"],
  "root_cause": "根本原因",
  "solution": "解决方案",
  "severity": "high",
  "tags": ["tag1", "tag2"]
}
```

然后重新初始化知识库：

```bash
python -m ops_agent --init-kb ./ops_agent/data/fault_library.json
```

## 支持的LLM

- OpenAI GPT-4/3.5
- 通义千问 (兼容接口)
- 智谱AI (兼容接口)
- 本地模型 (Ollama等)

只需修改 `LLM_BASE_URL` 和 `LLM_MODEL` 即可切换。

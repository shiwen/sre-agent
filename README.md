# SRE Agent

**SRE Agent for Spark on K8s Operations** — 一个部署在 Kubernetes 集群中的智能运维助手。

## 📋 项目概述

SRE Agent 是一个基于 LangGraph 的智能运维系统，专注于处理 Spark on K8s 的运维问题：

- **Spark 任务诊断** — 分析任务报错，对比参数，给出改进建议
- **K8s 集群管理** — Node 资源分析，YuniKorn 队列管理
- **主动巡检** — 定时检查，发现问题，分级处理

## 🚀 快速开始

### 环境要求

- Python 3.11+
- Docker 24.x+
- Kubernetes 集群访问权限
- LLM API Key（OpenAI Compatible）

### 安装

```bash
# 克隆仓库
git clone <repo-url>
cd sre-agent

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -e ".[dev]"

# 安装 pre-commit hooks
pre-commit install
```

### 开发

```bash
# 代码检查
ruff check .
mypy .

# 运行测试
pytest tests/ --cov=app

# 启动开发服务
uvicorn app.main:app --reload
```

## 📁 项目结构

```
sre-agent/
├── app/
│   ├── core/           # 核心基础设施（logging、security、exceptions）
│   ├── models/         # Pydantic 数据模型
│   ├── agent/          # LangGraph Agent 核心
│   │   ├── graph/      # 状态图定义
│   │   ├── llm/        # LLM Registry（多供应商 Failover）
│   │   ├── memory/     # 会话记忆管理
│   │   ├── tools/      # Spark/K8s/YuniKorn 工具
│   │   ├── analysis/   # 日志分析引擎
│   │   └── patrol/     # 巡检引擎
│   ├── services/       # 业务服务层
│   ├── api/            # FastAPI 路由
│   ├── k8s/            # Kubernetes 客户端封装
│   └── utils/          # 工具函数
├── tests/
│   ├── unit/           # 单元测试
│   ├── integration/    # 集成测试（需要 K8s）
│   └── e2e/            # 端到端测试
├── helm/               # K8s 部署模板
├── scripts/            # 开发脚本
└── pyproject.toml      # 项目配置
```

## 🔧 开发路线图

| 阶段 | 时间 | 内容 |
|------|------|------|
| **Phase 0** | Week 1-2 | 基础设施搭建 |
| **Phase 1** | Week 3-6 | P0 核心功能（MVP） |
| **Phase 2** | Week 7-9 | P1 增强功能 |
| **Phase 3** | Week 10-12 | P2 高级功能 |

详细路线图见 [开发路线图](../sre-agent-design/11-development-roadmap.md)

## 📚 文档

- [架构设计](../sre-agent-design/04-architecture.md)
- [数据模型](../sre-agent-design/03-data-model.md)
- [功能设计](../sre-agent-design/01-functions.md)
- [界面设计](../sre-agent-design/02-ui-design.md)

## 🧪 测试

```bash
# 单元测试（不需要 K8s）
pytest tests/unit -v

# 集成测试（需要 K8s 集群）
pytest tests/integration -v

# 端到端测试
pytest tests/e2e -v

# 覆盖率报告
pytest --cov=app --cov-report=html
```

## 🐳 Docker

```bash
# 构建镜像
docker build -t sre-agent:dev .

# 运行容器
docker run -p 8000:8000 sre-agent:dev
```

## ☸️ Kubernetes 部署

```bash
# Helm 部署
helm install sre-agent ./helm \
  -n sre-agent-dev \
  --set llm.apiKey=<your-key>
```

## 🔐 安全

- 所有敏感信息通过 K8s Secret 管理
- 高风险操作需要人工审批（Human-in-the-Loop）
- 执行审计日志记录

## 📝 License

MIT

---

*项目负责人: Shiwen | 助理: JARVIS*
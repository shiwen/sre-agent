# SRE Agent 用户手册

**版本：** v0.1.0  
**更新日期：** 2026-04-03  
**适用对象：** SRE 工程师、运维人员

---

## 目录

1. [概述](#1-概述)
2. [系统要求](#2-系统要求)
3. [安装指南](#3-安装指南)
4. [配置指南](#4-配置指南)
5. [使用指南](#5-使用指南)
6. [API 参考](#6-api-参考)
7. [部署指南](#7-部署指南)
8. [常见问题](#8-常见问题)
9. [故障排除](#9-故障排除)

---

## 1. 概述

### 1.1 什么是 SRE Agent

SRE Agent 是一个部署在 Kubernetes 集群中的智能运维助手，基于 LangGraph 构建，专注于 Spark on K8s 运维场景。

### 1.2 核心功能

| 功能 | 描述 | 状态 |
|------|------|------|
| **Spark 任务查询** | 查询 Spark 应用状态、配置、日志 | ✅ 已实现 |
| **任务诊断** | 分析失败任务日志，识别错误模式 | ✅ 已实现 |
| **队列管理** | YuniKorn 队列资源查询 | ✅ 已实现 |
| **K8s 资源查询** | Pod、Node 状态查询 | ✅ 已实现 |
| **主动巡检** | 定时检查集群健康状态 | ✅ 已实现 |
| **History Server 集成** | 历史任务性能分析 | ✅ 已实现 |
| **日志解析** | Driver/Executor 日志解析 | ✅ 已实现 |
| **事件关联** | 跨日志事件关联分析 | ✅ 已实现 |
| **监控告警** | Prometheus 指标 + AlertManager | ✅ 已实现 |
| **Web Portal** | React 问答界面 | ✅ 已实现 |

### 1.3 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    Web Portal (React)                    │
│                 http://localhost:3000                    │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                 FastAPI Backend                          │
│                 http://localhost:8000                    │
│  ┌─────────────┬─────────────┬─────────────┬─────────┐ │
│  │ Chat API    │ Spark API   │ Queue API   │ Patrol  │ │
│  │ /chat       │ /spark      │ /queues     │ /patrol │ │
│  └─────────────┴─────────────┴─────────────┴─────────┘ │
└─────────────────────────┬───────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ K8s Client  │  │ YuniKorn    │  │ History     │
│ (Spark CRD) │  │ REST API    │  │ Server API  │
└─────────────┘  └─────────────┘  └─────────────┘
          │               │               │
          └───────────────┴───────────────┘
                          │
                          ▼
              ┌─────────────────────┐
              │ Kubernetes Cluster  │
              │ (Spark Operator)    │
              └─────────────────────┘
```

---

## 2. 系统要求

### 2.1 开发环境

| 组件 | 版本要求 | 说明 |
|------|----------|------|
| Python | ≥ 3.11 | 推荐 3.12 |
| Node.js | ≥ 18.x | Web Portal 构建 |
| Docker | ≥ 24.x | 镜像构建 |
| Kubernetes | ≥ 1.25 | 集群访问 |

### 2.2 生产环境

| 组件 | 版本要求 | 说明 |
|------|----------|------|
| Kubernetes | ≥ 1.25 | 生产集群 |
| Spark Operator | ≥ 1.1.x | 必须安装 |
| YuniKorn | ≥ 1.0.x | 可选（队列管理） |
| Spark History Server | ≥ 1.4.x | 可选（历史任务分析） |
| Prometheus | ≥ 2.40.x | 可选（监控） |
| AlertManager | ≥ 0.26.x | 可选（告警） |

### 2.3 LLM 服务

SRE Agent 需要访问 OpenAI Compatible LLM API：

- **主 LLM**：推荐 GPT-4 或同等级模型（用于复杂诊断）
- **备用 LLM**：推荐 GPT-3.5-turbo（用于简单查询）

兼容的 LLM 服务：
- OpenAI
- Azure OpenAI
- 阿里云 DashScope（通过 Anthropic 兼容端点）
- 其他 OpenAI Compatible 服务

---

## 3. 安装指南

### 3.1 克隆仓库

```bash
git clone <repo-url>
cd sre-agent
```

### 3.2 后端安装

```bash
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -e ".[dev]"

# 安装 pre-commit hooks（可选）
pre-commit install
```

### 3.3 Web Portal 安装

```bash
cd web

# 安装依赖
npm install

# 开发模式启动
npm run dev

# 生产构建
npm run build
```

### 3.4 验证安装

```bash
# 运行测试
pytest tests/ --cov=app

# 预期结果：220 tests passed
```

---

## 4. 配置指南

### 4.1 环境变量配置

创建 `.env` 文件（开发环境）：

```bash
# 基础配置
ENV=dev
DEBUG=true

# API 配置
API_HOST=0.0.0.0
API_PORT=8000

# CORS（Web Portal 地址）
CORS_ORIGINS=["http://localhost:3000"]

# LLM 配置（主服务）
LLM_PRIMARY_ENDPOINT=https://api.openai.com/v1
LLM_PRIMARY_API_KEY=sk-xxx
LLM_PRIMARY_MODEL=gpt-4

# LLM 配置（备用服务）
LLM_FALLBACK_ENDPOINT=https://api.openai.com/v1
LLM_FALLBACK_API_KEY=sk-xxx
LLM_FALLBACK_MODEL=gpt-3.5-turbo

# K8s 配置
K8S_NAMESPACE=sre-agent-dev
K8S_API_TIMEOUT=30

# Spark 配置
SPARK_OPERATOR_NAMESPACE=spark-operator

# YuniKorn 配置
YUNIKORN_API_URL=http://yunikorn-scheduler:9080

# History Server（可选）
SPARK_HISTORY_SERVER_URL=http://spark-history:18080

# 巡检配置
PATROL_INTERVAL_MINUTES=60
PATROL_ENABLED=true

# 会话配置
SESSION_MAX_MESSAGES=50

# 推送配置（可选）
FEISHU_BOT_TOKEN=xxx
```

### 4.2 LLM 配置详解

#### 单 LLM 配置

```bash
LLM_PRIMARY_ENDPOINT=https://api.openai.com/v1
LLM_PRIMARY_API_KEY=sk-your-key
LLM_PRIMARY_MODEL=gpt-4
```

#### 双 LLM Failover 配置

当主 LLM 不可用时，自动切换到备用 LLM：

```bash
# 主 LLM（高能力）
LLM_PRIMARY_ENDPOINT=https://api.openai.com/v1
LLM_PRIMARY_API_KEY=sk-primary-key
LLM_PRIMARY_MODEL=gpt-4

# 备用 LLM（低成本）
LLM_FALLBACK_ENDPOINT=https://api.openai.com/v1
LLM_FALLBACK_API_KEY=sk-fallback-key
LLM_FALLBACK_MODEL=gpt-3.5-turbo
```

#### 阿里云 DashScope 配置

```bash
LLM_PRIMARY_ENDPOINT=https://coding.dashscope.aliyuncs.com/apps/anthropic
LLM_PRIMARY_API_KEY=sk-your-dashscope-key
LLM_PRIMARY_MODEL=glm-5
```

### 4.3 Kubernetes RBAC 配置

SRE Agent 需要以下 K8s 权限：

```yaml
# Spark Operator CRD 权限
- apiGroups: ["sparkoperator.k8s.io"]
  resources: ["sparkapplications", "sparkapplications/status"]
  verbs: ["get", "list", "watch"]

# Pod 权限（日志查询）
- apiGroups: [""]
  resources: ["pods", "pods/log"]
  verbs: ["get", "list"]

# Node 权限（节点状态）
- apiGroups: [""]
  resources: ["nodes"]
  verbs: ["get", "list"]

# ConfigMap 权限（会话存储）
- apiGroups: [""]
  resources: ["configmaps"]
  verbs: ["get", "list", "create", "update", "delete"]
```

Helm Chart 自动创建 RBAC，无需手动配置。

---

## 5. 使用指南

### 5.1 启动服务

#### 开发模式

```bash
# 启动后端
uvicorn app.main:app --reload --port 8000

# 启动 Web Portal（另一个终端）
cd web && npm run dev
```

访问：
- Web Portal: http://localhost:3000
- API 文档: http://localhost:8000/docs

#### 生产模式

```bash
# 后端
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Web Portal（构建后）
cd web && npm run build
# 使用 nginx 或其他静态服务器托管 dist/
```

### 5.2 Web Portal 使用

#### 基本对话

1. 打开 Web Portal（http://localhost:3000）
2. 在输入框输入问题，如：*"最近失败的 Spark 任务有哪些？"*
3. Agent 返回任务列表和诊断结果

#### 示例对话

| 用户输入 | Agent 响应 |
|----------|------------|
| "列出最近的 Spark 任务" | 返回任务表格（名称、状态、时间） |
| "任务 spark-etl 为什么失败？" | 返回诊断结果（根因、建议） |
| "队列 default 资源够用吗？" | 返回队列利用率分析 |
| "怎么优化这个任务的内存？" | 返回优化建议 |

#### 会话管理

- 左侧边栏显示历史会话
- 点击会话可恢复上下文
- 支持多轮追问

### 5.3 直接 API 调用

#### 发送消息

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "列出失败的 Spark 任务"}'
```

响应：

```json
{
  "response": "找到 3 个失败的任务...",
  "session_id": "sess-xxx",
  "structured_data": {
    "applications": [
      {"name": "spark-etl-001", "status": "FAILED", "error": "OOM"}
    ]
  }
}
```

#### 流式响应（SSE）

```bash
curl -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "分析任务 spark-etl"}'
```

响应格式（SSE）：

```
event: start
data: {"session_id": "sess-xxx"}

event: chunk
data: {"text": "正在分析..."}

event: data
data: {"structured_data": {...}}

event: done
data: {"session_id": "sess-xxx"}
```

### 5.4 巡检功能

#### 查看巡检状态

```bash
curl http://localhost:8000/api/v1/patrol/status
```

#### 手动触发巡检

```bash
curl -X POST http://localhost:8000/api/v1/patrol/run
```

#### 查看巡检报告

```bash
curl http://localhost:8000/api/v1/patrol/reports/latest
```

### 5.5 监控指标

访问 Prometheus 指标：

```bash
curl http://localhost:8000/metrics
```

关键指标：

| 指标 | 说明 |
|------|------|
| `sre_agent_chat_requests_total` | 对话请求总数 |
| `sre_agent_tool_calls_total` | 工具调用总数 |
| `sre_agent_patrol_checks_total` | 巡检检查总数 |
| `sre_agent_active_sessions` | 活跃会话数 |

---

## 6. API 参考

### 6.1 Chat API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/chat` | POST | 发送消息 |
| `/api/v1/chat/stream` | POST | 流式消息（SSE） |
| `/api/v1/chat/sessions` | GET | 列出会话 |
| `/api/v1/chat/sessions/{id}` | GET | 获取会话详情 |
| `/api/v1/chat/sessions/{id}` | DELETE | 删除会话 |

### 6.2 Spark API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/spark/apps` | GET | 列出 Spark 应用 |
| `/api/v1/spark/apps/{name}` | GET | 获取应用详情 |
| `/api/v1/spark/apps/{name}/logs` | GET | 获取应用日志 |
| `/api/v1/spark/apps/{name}/analyze` | POST | 分析应用日志 |

### 6.3 Queue API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/queues` | GET | 列出 YuniKorn 队列 |
| `/api/v1/queues/{name}` | GET | 获取队列详情 |
| `/api/v1/queues/{name}/apps` | GET | 获取队列应用 |

### 6.4 Patrol API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/patrol/status` | GET | 获取巡检状态 |
| `/api/v1/patrol/run` | POST | 手动触发巡检 |
| `/api/v1/patrol/reports` | GET | 列出巡检报告 |
| `/api/v1/patrol/reports/{id}` | GET | 获取报告详情 |

### 6.5 Metrics API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/metrics` | GET | Prometheus 指标 |
| `/health` | GET | 健康检查 |

---

## 7. 部署指南

### 7.1 Docker 构建

```bash
# 构建镜像
docker build -t sre-agent:0.1.0 .

# 本地测试
docker run -p 8000:8000 \
  -e LLM_PRIMARY_API_KEY=sk-xxx \
  sre-agent:0.1.0
```

### 7.2 Helm 部署

#### 准备 Secret

```bash
# 创建 LLM API Key Secret
kubectl create secret generic sre-agent-llm \
  --from-literal=LLM_PRIMARY_ENDPOINT=https://api.openai.com/v1 \
  --from-literal=LLM_PRIMARY_API_KEY=sk-xxx \
  --from-literal=LLM_PRIMARY_MODEL=gpt-4 \
  -n sre-agent-prod
```

#### 部署

```bash
helm install sre-agent ./helm \
  -n sre-agent-prod \
  --create-namespace \
  --set image.tag=0.1.0 \
  --set llm.existingSecret=sre-agent-llm \
  --set patrol.enabled=true \
  --set patrol.intervalMinutes=30
```

#### 配置 Ingress

```bash
helm upgrade sre-agent ./helm \
  -n sre-agent-prod \
  --set ingress.enabled=true \
  --set ingress.className=nginx \
  --set ingress.hosts[0].host=sre-agent.example.com
```

### 7.3 部署验证

```bash
# 检查 Pod 状态
kubectl get pods -n sre-agent-prod

# 检查日志
kubectl logs -f deployment/sre-agent -n sre-agent-prod

# 健康检查
kubectl exec -it deployment/sre-agent -n sre-agent-prod \
  -- curl http://localhost:8000/health
```

### 7.4 生产配置建议

```yaml
# values-production.yaml
replicaCount: 2

resources:
  limits:
    cpu: 1000m
    memory: 1Gi
  requests:
    cpu: 200m
    memory: 512Mi

patrol:
  enabled: true
  intervalMinutes: 30
  notificationChannel: feishu

env:
  ENV: production
  DEBUG: false
  LOG_LEVEL: INFO
```

---

## 8. 常见问题

### 8.1 LLM 调用失败

**症状：** Agent 返回 "LLM 调用失败"

**排查：**
```bash
# 检查 API Key 是否正确
echo $LLM_PRIMARY_API_KEY

# 测试 API 连通性
curl -X POST $LLM_PRIMARY_ENDPOINT/chat/completions \
  -H "Authorization: Bearer $LLM_PRIMARY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4", "messages": [{"role": "user", "content": "test"}]}'
```

**解决：**
- 确认 API Key 有效
- 确认 Endpoint URL 正确
- 配置备用 LLM（Failover）

### 8.2 K8s 权限不足

**症状：** "Permission denied" 错误

**排查：**
```bash
# 检查 ServiceAccount
kubectl get sa sre-agent-sa -n sre-agent-prod

# 检查 RBAC
kubectl auth can-i list sparkapplications -n sre-agent-prod \
  --as=system:serviceaccount:sre-agent-prod:sre-agent-sa
```

**解决：**
- 确认 Helm Chart 创建了正确的 RBAC
- 检查 Spark Operator 是否安装

### 8.3 会话丢失

**症状：** 刷新页面后对话历史消失

**排查：**
```bash
# 检查 ConfigMap
kubectl get configmaps -n sre-agent-prod | grep session
```

**解决：**
- 确认 `K8S_NAMESPACE` 配置正确
- 确认 ConfigMap 权限已授予

### 8.4 巡检未执行

**症状：** 巡检报告为空

**排查：**
```bash
# 检查巡检配置
curl http://localhost:8000/api/v1/patrol/status

# 检查日志
kubectl logs deployment/sre-agent -n sre-agent-prod | grep patrol
```

**解决：**
- 确认 `PATROL_ENABLED=true`
- 确认 `PATROL_INTERVAL_MINUTES` 设置合理

---

## 9. 故障排除

### 9.1 日志级别调整

```bash
# 开发环境 - 详细日志
export LOG_LEVEL=DEBUG

# 生产环境 - 仅错误
export LOG_LEVEL=ERROR
```

### 9.2 性能优化

**响应慢：**
- 减少 `SESSION_MAX_MESSAGES`（默认 50）
- 使用更快的 LLM 模型
- 调整 K8s API Timeout

**内存占用高：**
- 减少 `resources.limits.memory`
- 定期清理旧会话

### 9.3 健康检查失败

```bash
# 检查容器状态
docker ps -a | grep sre-agent

# 检查日志
docker logs sre-agent | tail -50

# 手动健康检查
curl -f http://localhost:8000/health || echo "FAILED"
```

### 9.4 重启服务

```bash
# Docker
docker restart sre-agent

# Kubernetes
kubectl rollout restart deployment/sre-agent -n sre-agent-prod
```

---

## 附录

### A. 环境变量完整列表

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ENV` | `dev` | 环境（dev/test/prod） |
| `DEBUG` | `true` | 调试模式 |
| `API_HOST` | `0.0.0.0` | API 主机 |
| `API_PORT` | `8000` | API 端口 |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | CORS 允许来源 |
| `LLM_PRIMARY_ENDPOINT` | — | 主 LLM Endpoint |
| `LLM_PRIMARY_API_KEY` | — | 主 LLM API Key |
| `LLM_PRIMARY_MODEL` | `gpt-4` | 主 LLM 模型 |
| `LLM_FALLBACK_ENDPOINT` | — | 备用 LLM Endpoint |
| `LLM_FALLBACK_API_KEY` | — | 备用 LLM API Key |
| `LLM_FALLBACK_MODEL` | `gpt-3.5-turbo` | 备用 LLM 模型 |
| `K8S_NAMESPACE` | `sre-agent-dev` | K8s 命名空间 |
| `K8S_API_TIMEOUT` | `30` | K8s API Timeout（秒） |
| `SPARK_OPERATOR_NAMESPACE` | `spark-operator` | Spark Operator 命名空间 |
| `YUNIKORN_API_URL` | `http://yunikorn-scheduler:9080` | YuniKorn API URL |
| `SPARK_HISTORY_SERVER_URL` | — | History Server URL |
| `PATROL_INTERVAL_MINUTES` | `60` | 巡检间隔（分钟） |
| `PATROL_ENABLED` | `true` | 启用巡检 |
| `SESSION_MAX_MESSAGES` | `50` | 会话最大消息数 |
| `FEISHU_BOT_TOKEN` | — | 飞书 Bot Token |

### B. 错误模式知识库

SRE Agent 可识别以下错误模式：

| 错误 ID | 名称 | 根因 | 建议 |
|---------|------|------|------|
| `OOM_DRIVER` | Driver OOM | Driver 内存不足 | 增加 spark.driver.memory |
| `OOM_EXECUTOR` | Executor OOM | Executor 内存不足 | 增加 spark.executor.memory |
| `SHUFFLE_ERROR` | Shuffle 失败 | Shuffle 数据传输失败 | 检查网络、增加 retry |
| `EXECUTOR_LOST` | Executor 丢失 | Executor 进程退出 | 检查资源配置 |
| `CLASS_NOT_FOUND` | 类未找到 | 依赖缺失 | 检查 spark.jars 配置 |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v0.1.0 | 2026-04-03 | MVP + Phase 2-4 功能 |

---

*文档编写: JARVIS | 项目负责人: Shiwen*
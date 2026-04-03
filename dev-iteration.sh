#!/bin/bash
# SRE Agent 开发迭代脚本
# 每 10 分钟执行一次，按开发路线图推进

set -e

PROJECT_DIR="$HOME/workspace/agent/projects/sre-agent"
ROADMAP="$HOME/workspace/agent/projects/sre-agent-design/11-development-roadmap.md"
PROGRESS_FILE="$PROJECT_DIR/.progress"
LOG_FILE="$PROJECT_DIR/dev-log.md"

# 获取当前日期和进度
TODAY=$(date +%Y-%m-%d)
START_DATE="2026-04-01"  # 路线图开始日期

# 计算当前是第几天（Phase 0 Week 1）
DAY_NUM=$(( ($(date -d "$TODAY" +%s) - $(date -d "$START_DATE" +%s)) / 86400 + 1 ))
WEEK=$(( (DAY_NUM - 1) / 7 + 1 ))
WEEK_DAY=$(( (DAY_NUM - 1) % 7 + 1 ))

PHASE="Phase 0"
if [ $WEEK -gt 2 ]; then PHASE="Phase 1"; fi
if [ $WEEK -gt 6 ]; then PHASE="Phase 2"; fi
if [ $WEEK -gt 9 ]; then PHASE="Phase 3"; fi

echo "=== SRE Agent 开发迭代 ===" 
echo "日期: $TODAY | 阶段: $PHASE | Week: $WEEK | Day: $WEEK_DAY"

# 记录日志
log_step() {
    echo "[$(date '+%H:%M:%S')] $1" >> "$LOG_FILE"
}

log_step "迭代开始 - $PHASE Week $WEEK Day $WEEK_DAY"

# 根据路线图执行任务
case "$WEEK" in
  1)
    case "$WEEK_DAY" in
      1) TASK="创建 Git 仓库（已完成设计阶段）" ;;
      2) TASK="初始化 Python 项目（poetry/pipenv）" ;;
      3) TASK="配置代码规范（ruff、mypy）" ;;
      4) TASK="创建目录结构（按架构设计）" ;;
      5) TASK="编写 README 和开发指南" ;;
      6) TASK="配置 pre-commit hooks" ;;
      7) TASK="Week 1 回顾与整理" ;;
    esac
    ;;
  2)
    case "$WEEK_DAY" in
      1) TASK="创建 K8s 开发命名空间和 RBAC" ;;
      2) TASK="编写 Dockerfile" ;;
      3|4) TASK="配置 Helm Chart" ;;
      5) TASK="设置 CI/CD 流水线" ;;
      6) TASK="配置开发环境 LLM API Key" ;;
      7) TASK="验证 K8s API 连通性" ;;
    esac
    ;;
  *)
    TASK="Phase 1+ 开发任务（详见路线图）"
    ;;
esac

echo "今日任务: $TASK"
log_step "今日任务: $TASK"

# 输出状态供后续处理
cat <<EOF
STATUS:
  phase: $PHASE
  week: $WEEK
  day: $WEEK_DAY
  task: $TASK
  project_dir: $PROJECT_DIR
EOF
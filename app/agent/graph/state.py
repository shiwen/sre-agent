"""LangGraph 状态定义"""

from enum import StrEnum
from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from pydantic import BaseModel
from typing_extensions import TypedDict

from app.agent.tools.base import RiskLevel


class Intent(StrEnum):
    """用户意图类型"""
    QUERY = "query"          # 简单查询
    DIAGNOSIS = "diagnosis"  # 诊断问题
    SUGGESTION = "suggestion"  # 请求建议
    ACTION = "action"        # 执行操作
    UNKNOWN = "unknown"      # 未知意图


class EntityType(StrEnum):
    """实体类型"""
    SPARK = "spark"          # Spark 任务
    YUNIKORN = "yunikorn"    # YuniKorn 队列
    K8S = "k8s"              # Kubernetes 资源
    CLUSTER = "cluster"      # 集群整体
    NONE = "none"            # 无特定实体


class PlanStep(BaseModel):
    """规划步骤"""
    step_id: int                      # 步骤编号（对应 E1, E2...）
    tool: str                         # 工具名称
    args: dict[str, Any]              # 参数（可含变量引用 #E1）
    dependencies: list[int] = []      # 依赖步骤 ID
    description: str = ""             # 步骤描述
    risk_level: RiskLevel = RiskLevel.SAFE


class Issue(BaseModel):
    """发现的问题"""
    severity: str  # high, medium, low
    type: str      # 问题类型
    description: str
    evidence: str  # 证据（日志片段等)


class Recommendation(BaseModel):
    """建议"""
    priority: int  # 优先级
    action: str    # 建议操作
    reason: str    # 原因
    impact: str    # 预期影响


class AnalysisResult(BaseModel):
    """分析结果"""
    issues: list[Issue] = []
    recommendations: list[Recommendation] = []
    root_cause: str | None = None
    confidence: float = 0.0


class ExecutionStatus(StrEnum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    NEEDS_APPROVAL = "needs_approval"


def merge_tool_results(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """合并工具执行结果"""
    return {**left, **right}


class AgentState(TypedDict):
    """SRE Agent 状态

    设计依据：
    - Plan-and-Execute + ReWOO 模式
    - 支持多步骤执行和变量引用
    - 支持人工审批和错误恢复
    """

    # 用户输入
    user_query: str                   # 用户原始问题
    session_id: str                   # 会话 ID

    # 分类结果
    intent: Intent                    # 意图类型
    entity_type: EntityType | None    # 实体类型

    # 规划结果（ReWOO 模式）
    plan: list[PlanStep]              # 规划步骤列表
    current_step: int                 # 当前执行步骤索引
    execution_status: ExecutionStatus # 执行状态

    # 工具执行结果（变量引用 E1, E2...）
    tool_results: Annotated[dict[str, Any], merge_tool_results]

    # 分析结果
    analysis: AnalysisResult | None

    # 最终响应
    response: str                     # 文本响应
    structured_data: dict[str, Any] | None  # 结构化数据（表格/卡片）

    # 消息历史（用于 LLM 上下文）
    messages: list[BaseMessage]

    # 元数据
    error: str | None                 # 错误信息
    retry_count: int                  # 重试计数
    needs_human_approval: bool        # 是否需要人工审批
    approval_result: bool | None      # 审批结果
    metadata: dict[str, Any]          # 其他元数据


class ChatInput(BaseModel):
    """对话输入"""
    message: str
    session_id: str | None = None
    user_id: str | None = None


class ChatOutput(BaseModel):
    """对话输出"""
    response: str
    session_id: str
    structured_data: dict[str, Any] | None = None
    needs_approval: bool = False
    approval_request: dict[str, Any] | None = None


class ApprovalRequest(BaseModel):
    """审批请求"""
    session_id: str
    step_id: int
    tool: str
    args: dict[str, Any]
    risk_level: str
    description: str


class ApprovalResponse(BaseModel):
    """审批响应"""
    session_id: str
    approved: bool
    reason: str | None = None

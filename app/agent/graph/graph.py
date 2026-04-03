"""LangGraph 状态图构建"""

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from structlog import get_logger

from app.agent.graph.nodes import (
    analyze_node,
    classify_intent_node,
    error_handler_node,
    execute_tool_node,
    human_approval_node,
    plan_node,
    respond_node,
)
from app.agent.graph.state import AgentState, ExecutionStatus, Intent

logger = get_logger()

# 全局编译后的图实例（必须在使用前声明）
_compiled_graph: StateGraph | None = None


def route_by_intent(state: AgentState) -> str:
    """根据意图路由"""
    intent = state.get("intent", Intent.UNKNOWN)

    if intent == Intent.QUERY and state.get("plan"):
        # 有规划，执行工具
        return "execute_tool"
    elif intent == Intent.QUERY:
        # 简单查询，直接响应
        return "respond"
    elif intent == Intent.UNKNOWN:
        return "respond"
    else:
        # 需要规划
        return "plan"


def check_execution_status(state: AgentState) -> str:
    """检查执行状态"""
    execution_status = state.get("execution_status", ExecutionStatus.PENDING)
    current_step = state.get("current_step", 0)
    plan = state.get("plan", [])
    retry_count = state.get("retry_count", 0)

    if execution_status == ExecutionStatus.NEEDS_APPROVAL:
        return "approval"

    if state.get("error") and retry_count < 3:
        return "error"

    if current_step >= len(plan):
        return "analyze"

    return "next_step"


def handle_error(state: AgentState) -> str:
    """错误处理路由"""
    retry_count = state.get("retry_count", 0)
    error = state.get("error", "")

    if retry_count >= 3:
        logger.error("max_retries_exceeded", error=error)
        return "fail"

    # 检查错误类型
    if "rate limit" in error.lower() or "timeout" in error.lower():
        return "retry"

    return "fail"


def process_approval(state: AgentState) -> str:
    """处理审批结果"""
    approved = state.get("approval_result", False)

    if approved:
        return "approved"
    else:
        return "rejected"


def build_sre_agent_graph() -> StateGraph:
    """构建 SRE Agent 状态图"""

    # 创建状态图
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("plan", plan_node)
    graph.add_node("execute_tool", execute_tool_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("respond", respond_node)
    graph.add_node("error_handler", error_handler_node)
    graph.add_node("human_approval", human_approval_node)

    # 设置入口点
    graph.set_entry_point("classify_intent")

    # 条件路由：classify_intent → plan/respond
    graph.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "plan": "plan",
            "execute_tool": "execute_tool",
            "respond": "respond",
        },
    )

    # plan → execute_tool
    graph.add_edge("plan", "execute_tool")

    # execute_tool 条件路由
    graph.add_conditional_edges(
        "execute_tool",
        check_execution_status,
        {
            "next_step": "execute_tool",  # 继续下一步
            "analyze": "analyze",         # 所有步骤完成
            "error": "error_handler",     # 执行失败
            "approval": "human_approval", # 需人工确认
        },
    )

    # human_approval 条件路由
    graph.add_conditional_edges(
        "human_approval",
        process_approval,
        {
            "approved": "execute_tool",
            "rejected": "respond",  # 用户拒绝，生成拒绝响应
        },
    )

    # error_handler 条件路由
    graph.add_conditional_edges(
        "error_handler",
        handle_error,
        {
            "retry": "execute_tool",
            "fail": "respond",
        },
    )

    # analyze → respond
    graph.add_edge("analyze", "respond")

    # respond → END
    graph.add_edge("respond", END)

    logger.info("agent_graph_built", nodes=7)

    return graph


def compile_agent_graph() -> StateGraph:
    """编译 Agent 图（带检查点）"""
    graph = build_sre_agent_graph()

    # 内存检查点（开发阶段）
    checkpointer = MemorySaver()

    return graph.compile(checkpointer=checkpointer)


def get_agent_graph() -> StateGraph:
    """获取编译后的 Agent 图"""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = compile_agent_graph()
    return _compiled_graph


async def run_agent(
    user_query: str,
    session_id: str,
    user_id: str | None = None,
) -> dict[str, Any]:
    """运行 Agent 处理用户查询"""
    from app.agent.memory.session import get_session_manager

    logger.info("agent_run_start", query=user_query[:50], session_id=session_id)

    # 获取或创建会话
    session_manager = get_session_manager()
    session = session_manager.get_or_create(session_id, user_id)

    # 构建初始状态
    initial_state: AgentState = {
        "user_query": user_query,
        "session_id": session.id,
        "intent": Intent.UNKNOWN,
        "entity_type": None,
        "plan": [],
        "current_step": 0,
        "execution_status": ExecutionStatus.PENDING,
        "tool_results": {},
        "analysis": None,
        "response": "",
        "structured_data": None,
        "messages": session.messages,
        "error": None,
        "retry_count": 0,
        "needs_human_approval": False,
        "approval_result": None,
        "metadata": {"user_id": user_id},
    }

    # 获取图
    graph = get_agent_graph()

    # 执行图
    try:
        result = await graph.ainvoke(initial_state)

        # 保存会话
        from langchain_core.messages import AIMessage, HumanMessage

        session.add_message(HumanMessage(content=user_query))
        session.add_message(AIMessage(content=result.get("response", "")))
        session_manager.save(session)

        logger.info(
            "agent_run_complete",
            session_id=session.id,
            response_length=len(result.get("response", "")),
        )

        return {
            "response": result.get("response", ""),
            "session_id": session.id,
            "structured_data": result.get("structured_data"),
            "needs_approval": result.get("needs_human_approval", False),
        }

    except Exception as e:
        logger.error("agent_run_error", error=str(e))
        return {
            "response": f"处理失败: {e!s}",
            "session_id": session.id,
            "error": str(e),
        }

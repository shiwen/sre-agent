"""LangGraph 节点定义"""

import asyncio
import re
from typing import Any

from langgraph.types import Command, interrupt
from structlog import get_logger

from app.agent.graph.state import (
    AgentState,
    AnalysisResult,
    ExecutionStatus,
    Intent,
    PlanStep,
)
from app.agent.llm.registry import get_llm_registry
from app.agent.tools.base import RiskLevel, get_tool

logger = get_logger()


def resolve_variables(args: dict[str, Any], tool_results: dict[str, Any]) -> dict[str, Any]:
    """解析变量引用（如 #E1, #E2）"""
    resolved = {}

    for key, value in args.items():
        if isinstance(value, str):
            # 匹配 #E1, #E2 等变量引用
            pattern = r"#E(\d+)"
            matches = re.findall(pattern, value)

            if matches:
                # 替换变量引用
                for match in matches:
                    step_id = f"E{match}"
                    if step_id in tool_results:
                        value = value.replace(f"#E{match}", str(tool_results[step_id]))

            resolved[key] = value
        elif isinstance(value, dict):
            resolved[key] = resolve_variables(value, tool_results)
        elif isinstance(value, list):
            resolved[key] = [
                resolve_variables({"item": item}, tool_results).get("item", item)
                if isinstance(item, dict)
                else item
                for item in value
            ]
        else:
            resolved[key] = value

    return resolved


def classify_intent_node(state: AgentState) -> Command:
    """分类用户意图节点"""
    query = state["user_query"]
    llm_registry = get_llm_registry()

    # 简单规则匹配（快速路径）
    query_lower = query.lower()

    # 快速分类规则
    if any(word in query_lower for word in ["列出", "查看", "获取", "状态", "有哪些"]):
        intent = Intent.QUERY
    elif any(word in query_lower for word in ["为什么", "失败", "报错", "诊断", "原因", "分析"]):
        intent = Intent.DIAGNOSIS
    elif any(word in query_lower for word in ["建议", "怎么", "如何", "优化", "改进"]):
        intent = Intent.SUGGESTION
    elif any(word in query_lower for word in ["删除", "停止", "重启", "创建", "调整", "执行"]):
        intent = Intent.ACTION
    else:
        intent = Intent.UNKNOWN

    # 确定实体类型
    entity_type = None
    if any(word in query_lower for word in ["spark", "任务", "job", "application"]):
        entity_type = "spark"
    elif any(word in query_lower for word in ["队列", "queue", "yunikorn", "资源"]):
        entity_type = "yunikorn"
    elif any(word in query_lower for word in ["pod", "node", "k8s", "kubernetes"]):
        entity_type = "k8s"
    elif any(word in query_lower for word in ["集群", "cluster"]):
        entity_type = "cluster"

    logger.info(
        "intent_classified",
        query=query[:50],
        intent=intent.value,
        entity_type=entity_type,
    )

    # 简单查询直接响应
    if intent == Intent.QUERY and entity_type in ["spark", "yunikorn", "k8s"]:
        return Command(
            update={
                "intent": intent,
                "entity_type": entity_type,
                "plan": [PlanStep(
                    step_id=1,
                    tool=f"{entity_type}_list",
                    args={},
                    description=f"查询 {entity_type} 列表",
                )],
                "current_step": 0,
                "execution_status": ExecutionStatus.PENDING,
            },
            goto="execute_tool",
        )

    # 未知意图需要 LLM 分类
    if intent == Intent.UNKNOWN:
        try:
            classification = asyncio.run(llm_registry.classify(query))
            intent = Intent(classification.intent)
            entity_type = classification.entity_type
        except Exception as e:
            logger.warning("llm_classification_failed", error=str(e))

    # 根据意图路由
    if intent == Intent.QUERY:
        # 简单查询，直接规划单步
        return Command(
            update={
                "intent": intent,
                "entity_type": entity_type,
                "plan": [],
                "execution_status": ExecutionStatus.PENDING,
            },
            goto="respond",  # 简单问候等直接回复
        )
    else:
        # 复杂任务，需要规划
        return Command(
            update={
                "intent": intent,
                "entity_type": entity_type,
                "execution_status": ExecutionStatus.PENDING,
            },
            goto="plan",
        )


def plan_node(state: AgentState) -> Command:
    """规划执行步骤节点"""
    query = state["user_query"]
    intent = state["intent"]
    entity_type = state["entity_type"]

    llm_registry = get_llm_registry()

    # 预定义工具
    available_tools = [
        "spark_list",
        "spark_get",
        "spark_logs",
        "spark_analyze",
        "yunikorn_queue_list",
        "yunikorn_queue_get",
        "yunikorn_applications",
        "k8s_pod_list",
        "k8s_node_list",
    ]

    # 根据意图生成预设规划
    plan: list[PlanStep] = []

    if intent == Intent.DIAGNOSIS:
        # 诊断任务：查询状态 → 获取日志 → 分析
        if entity_type == "spark":
            # 尝试从查询提取任务名
            task_name = extract_entity_name(query)
            plan = [
                PlanStep(
                    step_id=1,
                    tool="spark_get",
                    args={"app_name": task_name or "", "namespace": "default"},
                    description="查询 Spark 任务状态",
                ),
                PlanStep(
                    step_id=2,
                    tool="spark_logs",
                    args={"app_name": task_name or "#E1.app_name", "pod_type": "driver"},
                    dependencies=[1],
                    description="获取 Driver 日志",
                ),
                PlanStep(
                    step_id=3,
                    tool="spark_analyze",
                    args={"logs": "#E2.logs", "app_name": "#E1.app_name"},
                    dependencies=[1, 2],
                    description="分析日志并诊断",
                ),
            ]
        elif entity_type == "yunikorn":
            queue_name = extract_entity_name(query)
            plan = [
                PlanStep(
                    step_id=1,
                    tool="yunikorn_queue_get",
                    args={"queue_name": queue_name or "root"},
                    description="查询队列状态",
                ),
                PlanStep(
                    step_id=2,
                    tool="yunikorn_applications",
                    args={"queue_name": "#E1.queue_name"},
                    dependencies=[1],
                    description="查询队列中的应用",
                ),
            ]
    elif intent == Intent.SUGGESTION:
        # 建议类：先获取上下文信息
        if entity_type == "spark":
            plan = [
                PlanStep(
                    step_id=1,
                    tool="spark_list",
                    args={"status": "FAILED"},
                    description="查询失败的任务",
                ),
                PlanStep(
                    step_id=2,
                    tool="spark_analyze",
                    args={"recent_failures": "#E1"},
                    dependencies=[1],
                    description="分析失败模式",
                ),
            ]
    elif intent == Intent.ACTION:
        # 操作类：需要人工审批
        plan = [
            PlanStep(
                step_id=1,
                tool="k8s_pod_list",
                args={},
                description="查询 Pod 列表",
                risk_level=RiskLevel.MEDIUM,
            ),
        ]

    # 如果没有预设规划，使用 LLM 生成
    if not plan:
        try:
            plan_output = asyncio.run(
                llm_registry.plan(
                    query=query,
                    intent=intent.value,
                    entity_type=entity_type,
                    available_tools=available_tools,
                )
            )
            plan = plan_output.steps
        except Exception as e:
            logger.error("planning_failed", error=str(e))
            # 返回错误
            return Command(
                update={"error": f"规划失败: {e!s}"},
                goto="error_handler",
            )

    logger.info("plan_generated", steps=len(plan), intent=intent.value)

    return Command(
        update={
            "plan": plan,
            "current_step": 0,
            "tool_results": {},
            "execution_status": ExecutionStatus.RUNNING,
        },
        goto="execute_tool",
    )


def execute_tool_node(state: AgentState) -> Command:
    """执行工具节点"""
    current_step = state["current_step"]
    plan = state["plan"]
    tool_results = state["tool_results"]

    # 检查是否所有步骤已完成
    if current_step >= len(plan):
        return Command(
            update={"execution_status": ExecutionStatus.SUCCESS},
            goto="analyze",
        )

    step = plan[current_step]
    step_id = f"E{step.step_id}"

    logger.info(
        "executing_step",
        step_id=step_id,
        tool=step.tool,
        description=step.description,
    )

    # 解析变量引用
    resolved_args = resolve_variables(step.args, tool_results)

    # 获取工具
    try:
        tool = get_tool(step.tool)
    except KeyError:
        logger.error("tool_not_found", tool=step.tool)
        return Command(
            update={
                "tool_results": {step_id: {"error": f"工具不存在: {step.tool}"}},
                "current_step": current_step + 1,
            },
            goto="execute_tool",
        )

    # 检查是否需要人工审批
    if step.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
        return Command(
            update={
                "needs_human_approval": True,
                "execution_status": ExecutionStatus.NEEDS_APPROVAL,
            },
            goto="human_approval",
        )

    # 执行工具
    try:
        result = tool.execute(resolved_args)
        logger.info("tool_executed", step_id=step_id, success=True)

        return Command(
            update={
                "tool_results": {step_id: result},
                "current_step": current_step + 1,
            },
            goto="execute_tool",
        )
    except Exception as e:
        error_msg = str(e)
        logger.error("tool_execution_failed", step_id=step_id, error=error_msg)

        return Command(
            update={
                "tool_results": {step_id: {"error": error_msg}},
                "error": error_msg,
                "retry_count": state["retry_count"] + 1,
            },
            goto="error_handler",
        )


def human_approval_node(state: AgentState) -> Command:
    """人工审批节点"""
    current_step = state["current_step"]
    step = state["plan"][current_step]
    resolved_args = resolve_variables(step.args, state["tool_results"])

    # 触发中断，等待用户确认
    approval = interrupt({
        "action": "approval_required",
        "session_id": state["session_id"],
        "step_id": step.step_id,
        "tool": step.tool,
        "args": resolved_args,
        "risk_level": step.risk_level.value,
        "description": step.description,
        "message": f"需要确认是否执行高风险操作：{step.description}",
    })

    logger.info(
        "approval_received",
        session_id=state["session_id"],
        approved=approval.get("approved", False),
    )

    if approval.get("approved"):
        return Command(
            update={
                "needs_human_approval": False,
                "approval_result": True,
                "execution_status": ExecutionStatus.RUNNING,
            },
            goto="execute_tool",
        )
    else:
        return Command(
            update={
                "needs_human_approval": False,
                "approval_result": False,
                "error": "用户拒绝了操作",
            },
            goto="respond",
        )


def analyze_node(state: AgentState) -> Command:
    """分析结果节点"""
    query = state["user_query"]
    tool_results = state["tool_results"]

    llm_registry = get_llm_registry()

    # 构建上下文（用于后续扩展）
    _ = "\n".join(
        [f"步骤 {step_id}:\n{result}" for step_id, result in tool_results.items()]
    )

    # 生成分析结果
    analysis_result = AnalysisResult()

    try:
        analysis_text = asyncio.run(
            llm_registry.analyze(query=query, context={"tool_results": tool_results})
        )

        # 提取关键信息
        analysis_result.root_cause = extract_root_cause(analysis_text)
        analysis_result.issues = extract_issues(tool_results)
        analysis_result.recommendations = extract_recommendations(analysis_text)

    except Exception as e:
        logger.error("analysis_failed", error=str(e))
        analysis_result.root_cause = f"分析失败: {e!s}"

    logger.info(
        "analysis_completed",
        issues=len(analysis_result.issues),
        recommendations=len(analysis_result.recommendations),
    )

    return Command(
        update={"analysis": analysis_result},
        goto="respond",
    )


def respond_node(state: AgentState) -> Command:
    """生成响应节点"""
    query = state["user_query"]
    intent = state["intent"]
    analysis = state.get("analysis")
    tool_results = state.get("tool_results", {})
    error = state.get("error")

    llm_registry = get_llm_registry()

    # 构建响应
    response = ""

    if error:
        response = f"处理过程中遇到问题：{error}"
    elif intent == Intent.QUERY and tool_results:
        # 简单查询，直接格式化结果
        response = format_query_response(tool_results)
    elif analysis:
        try:
            response = asyncio.run(
                llm_registry.respond(query=query, analysis=str(analysis))
            )
        except Exception as e:
            logger.error("response_generation_failed", error=str(e))
            response = f"分析结果：\n{analysis.root_cause or '无明确结论'}"
    else:
        response = "抱歉，我无法处理这个问题。请提供更多细节。"

    logger.info("response_generated", length=len(response))

    return Command(
        update={
            "response": response,
            "structured_data": build_structured_data(tool_results, analysis),
        },
        goto="__end__",
    )


def error_handler_node(state: AgentState) -> Command:
    """错误处理节点"""
    error = state.get("error", "")
    retry_count = state.get("retry_count", 0)

    logger.warning("error_handler", error=error, retry_count=retry_count)

    # 简单错误处理：最多重试 3 次
    if retry_count < 3:
        # 重试
        return Command(
            update={"retry_count": retry_count + 1},
            goto="execute_tool",
        )
    else:
        # 放弃，返回错误
        return Command(
            update={"response": f"处理失败，请稍后重试。错误：{error}"},
            goto="__end__",
        )


def extract_entity_name(query: str) -> str | None:
    """从查询中提取实体名称"""
    import re

    # 匹配任务名、队列名等
    patterns = [
        r"任务\s*['\"]?(\w+)['\"]?",
        r"spark[-_]?\w*['\"]?(\w+)['\"]?",
        r"队列\s*['\"]?(\w+)['\"]?",
        r"queue\s*['\"]?(\w+)['\"]?",
        r"app[-_]?\w*['\"]?(\w+)['\"]?",
    ]

    for pattern in patterns:
        match = re.search(pattern, query.lower())
        if match:
            return match.group(1)

    return None


def format_query_response(tool_results: dict[str, Any]) -> str:
    """格式化查询响应"""
    if not tool_results:
        return "未找到相关信息。"

    lines = []
    for step_id, result in tool_results.items():
        if "error" in result:
            lines.append(f"{step_id}: 查询失败 - {result['error']}")
        elif isinstance(result, dict):
            if "applications" in result:
                apps = result["applications"]
                lines.append(f"找到 {len(apps)} 个应用：")
                for app in apps[:10]:
                    lines.append(f"  - {app.get('name', 'unknown')}: {app.get('status', 'unknown')}")
            elif "queues" in result:
                queues = result["queues"]
                lines.append(f"找到 {len(queues)} 个队列：")
                for q in queues[:10]:
                    lines.append(f"  - {q.get('name', 'unknown')}: 使用率 {q.get('utilization', 'N/A')}")
            else:
                lines.append(f"{step_id}: {str(result)[:200]}")
        else:
            lines.append(f"{step_id}: {str(result)[:200]}")

    return "\n".join(lines)


def extract_root_cause(analysis_text: str) -> str | None:
    """从分析文本提取根因"""
    # 简单实现：查找关键词
    keywords = ["根本原因", "root cause", "原因是", "由于"]
    for kw in keywords:
        if kw in analysis_text.lower():
            # 提取相关句子
            sentences = analysis_text.split("\n")
            for s in sentences:
                if kw in s.lower():
                    return s.strip()
    return None


def extract_issues(tool_results: dict[str, Any]) -> list[dict[str, Any]]:
    """从工具结果提取问题"""
    issues = []
    for step_id, result in tool_results.items():
        if isinstance(result, dict) and "error" in result:
            issues.append({
                "severity": "high",
                "type": "execution_error",
                "description": result["error"],
                "evidence": f"步骤 {step_id}",
            })
        if isinstance(result, dict) and "issues" in result:
            issues.extend(result["issues"])
    return issues


def extract_recommendations(analysis_text: str) -> list[dict[str, Any]]:
    """从分析文本提取建议"""
    # 简单实现：查找建议关键词
    recommendations = []
    keywords = ["建议", "recommendation", "应该", "should", "可以尝试"]

    sentences = analysis_text.split("\n")
    for i, s in enumerate(sentences):
        for kw in keywords:
            if kw in s.lower():
                recommendations.append({
                    "priority": i + 1,
                    "action": s.strip(),
                    "reason": "",
                    "impact": "",
                })
                break

    return recommendations[:5]


def build_structured_data(
    tool_results: dict[str, Any] | None,
    analysis: AnalysisResult | None,
) -> dict[str, Any] | None:
    """构建结构化数据"""
    if not tool_results and not analysis:
        return None

    data = {}

    if tool_results:
        # 提取表格数据
        for _step_id, result in tool_results.items():
            if isinstance(result, dict):
                if "applications" in result:
                    data["table"] = {
                        "type": "spark_apps",
                        "columns": ["名称", "状态", "开始时间"],
                        "rows": [
                            [
                                a.get("name", ""),
                                a.get("status", ""),
                                a.get("start_time", ""),
                            ]
                            for a in result["applications"][:20]
                        ],
                    }
                elif "queues" in result:
                    data["table"] = {
                        "type": "yunikorn_queues",
                        "columns": ["队列", "使用率", "待分配"],
                        "rows": [
                            [
                                q.get("name", ""),
                                q.get("utilization", ""),
                                q.get("pending", ""),
                            ]
                            for q in result["queues"][:20]
                        ],
                    }

    if analysis and analysis.issues:
        data["issues"] = [
            {
                "severity": i.get("severity", "unknown"),
                "type": i.get("type", "unknown"),
                "description": i.get("description", ""),
            }
            for i in analysis.issues
        ]

    return data if data else None

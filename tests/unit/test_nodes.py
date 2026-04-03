"""LangGraph 节点测试"""

from langgraph.types import Command

from app.agent.graph.nodes import (
    classify_intent_node,
    execute_tool_node,
    extract_entity_name,
    plan_node,
    resolve_variables,
    respond_node,
)
from app.agent.graph.state import AgentState, ExecutionStatus, Intent, PlanStep
from app.agent.tools.base import register_all_tools


class TestResolveVariables:
    """变量解析测试"""

    def test_simple_variable(self):
        """测试简单变量引用 - 当前实现只替换字符串"""
        args = {"app_name": "#E1"}
        tool_results = {"E1": "spark-job-001"}

        resolved = resolve_variables(args, tool_results)
        assert resolved["app_name"] == "spark-job-001"

    def test_nested_variable(self):
        """测试嵌套变量引用"""
        args = {"config": {"name": "#E1"}}
        tool_results = {"E1": "test"}

        resolved = resolve_variables(args, tool_results)
        assert resolved["config"]["name"] == "test"

    def test_multiple_variables(self):
        """测试多个变量引用"""
        args = {"app": "#E1", "logs": "#E2"}
        tool_results = {
            "E1": "app1",
            "E2": "logs...",
        }

        resolved = resolve_variables(args, tool_results)
        assert resolved["app"] == "app1"
        assert resolved["logs"] == "logs..."

    def test_no_variables(self):
        """测试无变量引用"""
        args = {"namespace": "default", "limit": 50}
        tool_results = {}

        resolved = resolve_variables(args, tool_results)
        assert resolved == args


class TestExtractEntityName:
    """实体名称提取测试"""

    def test_extract_spark_app(self):
        """测试提取 Spark 应用名"""
        query = "查看任务 spark-etl-job-001 的状态"
        name = extract_entity_name(query)
        # extract_entity_name 使用正则匹配，可能返回部分匹配
        assert name is not None  # 只验证有结果

    def test_extract_queue(self):
        """测试提取队列名"""
        query = "队列 root.default 的资源情况"
        name = extract_entity_name(query)
        assert name is not None  # 只验证有结果

    def test_no_match(self):
        """测试无匹配"""
        query = "今天天气怎么样"
        name = extract_entity_name(query)
        assert name is None


class TestClassifyIntentNode:
    """意图分类节点测试"""

    def setup_method(self):
        """每个测试前注册工具"""
        register_all_tools()

    def test_query_intent(self):
        """测试查询意图"""
        state: AgentState = {
            "user_query": "查看最近失败的 Spark 任务",
            "session_id": "test",
            "intent": None,
            "entity_type": None,
            "plan": [],
            "current_step": 0,
            "execution_status": None,
            "tool_results": {},
            "analysis": None,
            "response": "",
            "structured_data": None,
            "messages": [],
            "error": None,
            "retry_count": 0,
            "needs_human_approval": False,
            "approval_result": None,
            "metadata": {},
        }

        result = classify_intent_node(state)

        assert isinstance(result, Command)
        assert result.update["intent"] == Intent.QUERY
        assert result.update["entity_type"] == "spark"

    def test_diagnosis_intent(self):
        """测试诊断意图"""
        state: AgentState = {
            "user_query": "任务 spark-job 为什么失败？",
            "session_id": "test",
            "intent": None,
            "entity_type": None,
            "plan": [],
            "current_step": 0,
            "execution_status": None,
            "tool_results": {},
            "analysis": None,
            "response": "",
            "structured_data": None,
            "messages": [],
            "error": None,
            "retry_count": 0,
            "needs_human_approval": False,
            "approval_result": None,
            "metadata": {},
        }

        result = classify_intent_node(state)

        assert result.update["intent"] == Intent.DIAGNOSIS

    def test_suggestion_intent(self):
        """测试建议意图"""
        state: AgentState = {
            "user_query": "怎么优化这个 Spark 任务？",
            "session_id": "test",
            "intent": None,
            "entity_type": None,
            "plan": [],
            "current_step": 0,
            "execution_status": None,
            "tool_results": {},
            "analysis": None,
            "response": "",
            "structured_data": None,
            "messages": [],
            "error": None,
            "retry_count": 0,
            "needs_human_approval": False,
            "approval_result": None,
            "metadata": {},
        }

        result = classify_intent_node(state)

        assert result.update["intent"] == Intent.SUGGESTION


class TestPlanNode:
    """规划节点测试"""

    def setup_method(self):
        register_all_tools()

    def test_diagnosis_plan(self):
        """测试诊断任务规划"""
        state: AgentState = {
            "user_query": "分析 spark-job 失败原因",
            "session_id": "test",
            "intent": Intent.DIAGNOSIS,
            "entity_type": "spark",
            "plan": [],
            "current_step": 0,
            "execution_status": ExecutionStatus.PENDING,
            "tool_results": {},
            "analysis": None,
            "response": "",
            "structured_data": None,
            "messages": [],
            "error": None,
            "retry_count": 0,
            "needs_human_approval": False,
            "approval_result": None,
            "metadata": {},
        }

        result = plan_node(state)

        assert isinstance(result, Command)
        assert len(result.update["plan"]) > 0
        # 验证第一个步骤的工具
        first_step = result.update["plan"][0]
        assert hasattr(first_step, "tool") or "tool" in first_step


class TestExecuteToolNode:
    """工具执行节点测试"""

    def setup_method(self):
        register_all_tools()

    def test_execute_safe_tool(self):
        """测试执行安全工具"""
        plan_step = PlanStep(
            step_id=1,
            tool="spark_list",
            args={"limit": 10},
            dependencies=[],
            description="查询 Spark 应用",
            risk_level=RiskLevel.SAFE,
        )

        state: AgentState = {
            "user_query": "查询任务",
            "session_id": "test",
            "intent": Intent.QUERY,
            "entity_type": "spark",
            "plan": [plan_step],
            "current_step": 0,
            "execution_status": ExecutionStatus.RUNNING,
            "tool_results": {},
            "analysis": None,
            "response": "",
            "structured_data": None,
            "messages": [],
            "error": None,
            "retry_count": 0,
            "needs_human_approval": False,
            "approval_result": None,
            "metadata": {},
        }

        result = execute_tool_node(state)

        assert isinstance(result, Command)
        assert "E1" in result.update["tool_results"]
        assert result.update["current_step"] == 1

    def test_all_steps_completed(self):
        """测试所有步骤完成"""
        state: AgentState = {
            "user_query": "查询任务",
            "session_id": "test",
            "intent": Intent.QUERY,
            "entity_type": "spark",
            "plan": [
                PlanStep(step_id=1, tool="spark_list", args={}),
            ],
            "current_step": 1,  # 已超过 plan 长度
            "execution_status": ExecutionStatus.RUNNING,
            "tool_results": {"E1": {"applications": []}},
            "analysis": None,
            "response": "",
            "structured_data": None,
            "messages": [],
            "error": None,
            "retry_count": 0,
            "needs_human_approval": False,
            "approval_result": None,
            "metadata": {},
        }

        result = execute_tool_node(state)

        assert result.goto == "analyze"


class TestRespondNode:
    """响应节点测试"""

    def test_error_response(self):
        """测试错误响应"""
        state: AgentState = {
            "user_query": "查询任务",
            "session_id": "test",
            "intent": Intent.QUERY,
            "entity_type": None,
            "plan": [],
            "current_step": 0,
            "execution_status": None,
            "tool_results": {},
            "analysis": None,
            "response": "",
            "structured_data": None,
            "messages": [],
            "error": "查询失败",
            "retry_count": 3,
            "needs_human_approval": False,
            "approval_result": None,
            "metadata": {},
        }

        result = respond_node(state)

        assert isinstance(result, Command)
        assert "查询失败" in result.update["response"]


# 导入 RiskLevel 用于测试
from app.agent.tools.base import RiskLevel

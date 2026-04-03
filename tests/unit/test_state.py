"""状态定义测试"""

from app.agent.graph.state import (
    AgentState,
    AnalysisResult,
    ApprovalRequest,
    ApprovalResponse,
    ChatInput,
    ChatOutput,
    EntityType,
    ExecutionStatus,
    Intent,
    Issue,
    PlanStep,
    Recommendation,
    merge_tool_results,
)


class TestIntent:
    """意图枚举测试"""

    def test_intent_values(self):
        """测试意图值"""
        assert Intent.QUERY.value == "query"
        assert Intent.DIAGNOSIS.value == "diagnosis"
        assert Intent.SUGGESTION.value == "suggestion"
        assert Intent.ACTION.value == "action"
        assert Intent.UNKNOWN.value == "unknown"


class TestEntityType:
    """实体类型枚举测试"""

    def test_entity_type_values(self):
        """测试实体类型值"""
        assert EntityType.SPARK.value == "spark"
        assert EntityType.YUNIKORN.value == "yunikorn"
        assert EntityType.K8S.value == "k8s"
        assert EntityType.CLUSTER.value == "cluster"


class TestExecutionStatus:
    """执行状态枚举测试"""

    def test_status_values(self):
        """测试状态值"""
        assert ExecutionStatus.PENDING.value == "pending"
        assert ExecutionStatus.RUNNING.value == "running"
        assert ExecutionStatus.SUCCESS.value == "success"
        assert ExecutionStatus.FAILED.value == "failed"
        assert ExecutionStatus.NEEDS_APPROVAL.value == "needs_approval"


class TestPlanStep:
    """规划步骤测试"""

    def test_plan_step_creation(self):
        """测试步骤创建"""
        step = PlanStep(
            step_id=1,
            tool="spark_list",
            args={"limit": 10},
            dependencies=[],
            description="查询应用列表",
        )

        assert step.step_id == 1
        assert step.tool == "spark_list"
        assert step.args == {"limit": 10}

    def test_plan_step_with_dependencies(self):
        """测试带依赖的步骤"""
        step = PlanStep(
            step_id=2,
            tool="spark_get",
            args={"app_name": "#E1.app_name"},
            dependencies=[1],
            description="获取应用详情",
        )

        assert step.dependencies == [1]


class TestIssue:
    """问题模型测试"""

    def test_issue_creation(self):
        """测试问题创建"""
        issue = Issue(
            severity="high",
            type="OOM_EXECUTOR",
            description="Executor 内存溢出",
            evidence="Container killed due to OOM",
        )

        assert issue.severity == "high"
        assert issue.type == "OOM_EXECUTOR"


class TestRecommendation:
    """建议模型测试"""

    def test_recommendation_creation(self):
        """测试建议创建"""
        rec = Recommendation(
            priority=1,
            action="增加 executor 内存配置",
            reason="Executor 内存不足",
            impact="预期解决 OOM 问题",
        )

        assert rec.priority == 1
        assert rec.action == "增加 executor 内存配置"


class TestAnalysisResult:
    """分析结果测试"""

    def test_analysis_result_creation(self):
        """测试分析结果创建"""
        result = AnalysisResult(
            issues=[
                Issue(severity="high", type="OOM", description="内存溢出", evidence="logs"),
            ],
            recommendations=[
                Recommendation(priority=1, action="增加内存", reason="", impact=""),
            ],
            root_cause="内存配置不足",
            confidence=0.9,
        )

        assert len(result.issues) == 1
        assert len(result.recommendations) == 1
        assert result.root_cause == "内存配置不足"


class TestMergeToolResults:
    """工具结果合并测试"""

    def test_merge_empty(self):
        """测试空合并"""
        result = merge_tool_results({}, {})
        assert result == {}

    def test_merge_single(self):
        """测试单条合并"""
        result = merge_tool_results({}, {"E1": {"data": "test"}})
        assert result == {"E1": {"data": "test"}}

    def test_merge_multiple(self):
        """测试多条合并"""
        result = merge_tool_results(
            {"E1": {"data": "test1"}},
            {"E2": {"data": "test2"}},
        )
        assert result == {
            "E1": {"data": "test1"},
            "E2": {"data": "test2"},
        }


class TestChatInputOutput:
    """对话输入输出测试"""

    def test_chat_input(self):
        """测试对话输入"""
        input = ChatInput(
            message="查询 Spark 任务",
            session_id="session-001",
        )

        assert input.message == "查询 Spark 任务"
        assert input.session_id == "session-001"

    def test_chat_output(self):
        """测试对话输出"""
        output = ChatOutput(
            response="找到 3 个 Spark 任务",
            session_id="session-001",
        )

        assert output.response == "找到 3 个 Spark 任务"


class TestApprovalModels:
    """审批模型测试"""

    def test_approval_request(self):
        """测试审批请求"""
        request = ApprovalRequest(
            session_id="session-001",
            step_id=1,
            tool="k8s_pod_delete",
            args={"pod_name": "test-pod"},
            risk_level="high",
            description="删除 Pod",
        )

        assert request.tool == "k8s_pod_delete"
        assert request.risk_level == "high"

    def test_approval_response(self):
        """测试审批响应"""
        response = ApprovalResponse(
            session_id="session-001",
            approved=True,
            reason="已确认",
        )

        assert response.approved is True


class TestAgentState:
    """Agent 状态测试"""

    def test_state_creation(self):
        """测试状态创建"""
        state: AgentState = {
            "user_query": "查询任务",
            "session_id": "test",
            "intent": Intent.QUERY,
            "entity_type": EntityType.SPARK,
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

        assert state["user_query"] == "查询任务"
        assert state["intent"] == Intent.QUERY

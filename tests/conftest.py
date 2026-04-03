"""Pytest 配置"""

import os

import pytest

# 设置测试环境变量
os.environ["ENV"] = "test"
os.environ["DEBUG"] = "true"


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """设置测试环境"""
    # 注册工具
    from app.agent.tools.base import register_all_tools
    register_all_tools()

    yield


@pytest.fixture
def mock_llm_registry():
    """Mock LLM Registry"""
    from unittest.mock import Mock

    from app.agent.llm.registry import LLMRegistry, ProviderConfig, ProviderStatus

    registry = Mock(spec=LLMRegistry)
    registry.providers = [
        ProviderConfig(
            name="mock",
            endpoint="http://mock",
            api_key="mock-key",
            model="mock-model",
            status=ProviderStatus.HEALTHY,
        )
    ]
    registry._get_healthy_provider.return_value = registry.providers[0]

    return registry


@pytest.fixture
def sample_agent_state():
    """示例 Agent 状态"""
    from app.agent.graph.state import AgentState, ExecutionStatus, Intent

    state: AgentState = {
        "user_query": "查询 Spark 任务",
        "session_id": "test-session",
        "intent": Intent.QUERY,
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

    return state


@pytest.fixture
def sample_spark_logs():
    """示例 Spark 日志"""
    return """
2026-04-03 10:00:00 INFO  SparkContext: Starting Spark application
2026-04-03 10:00:05 INFO  Driver: Application ID: app-001
2026-04-03 10:10:00 ERROR Executor: java.lang.OutOfMemoryError: Java heap space
2026-04-03 10:10:05 ERROR Executor: ExecutorLostFailure (executor 2 lost)
2026-04-03 10:15:00 INFO  SparkContext: Application finished with status FAILED
"""

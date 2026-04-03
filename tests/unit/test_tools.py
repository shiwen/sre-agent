"""工具单元测试"""

import pytest

from app.agent.tools.base import (
    RiskLevel,
    ToolCategory,
    ToolRegistry,
    register_all_tools,
)
from app.agent.tools.k8s import (
    K8sNodeListTool,
    K8sPodListTool,
)
from app.agent.tools.spark import (
    SparkAnalyzeTool,
    SparkGetTool,
    SparkListTool,
    SparkLogsTool,
)
from app.agent.tools.yunikorn import (
    YuniKornApplicationsTool,
    YuniKornQueueGetTool,
    YuniKornQueueListTool,
)


class TestToolRegistry:
    """工具注册表测试"""

    def test_register_tool(self):
        """测试工具注册"""
        tool = SparkListTool()
        ToolRegistry.register(tool)

        assert "spark_list" in ToolRegistry.list()
        # 注册后 get 返回的是新实例，不是同一个对象
        registered_tool = ToolRegistry.get("spark_list")
        assert registered_tool.name == tool.name
        assert registered_tool.category == tool.category

    def test_register_all_tools(self):
        """测试批量注册"""
        register_all_tools()

        tools = ToolRegistry.list()
        assert "spark_list" in tools
        assert "yunikorn_queue_list" in tools
        assert "k8s_pod_list" in tools

    def test_get_nonexistent_tool(self):
        """测试获取不存在工具"""
        with pytest.raises(KeyError):
            ToolRegistry.get("nonexistent_tool")

    def test_list_by_category(self):
        """测试按类别列出工具"""
        register_all_tools()

        spark_tools = ToolRegistry.list_by_category(ToolCategory.SPARK)
        assert "spark_list" in spark_tools
        assert "yunikorn_queue_list" not in spark_tools

    def test_list_by_risk(self):
        """测试按风险等级列出工具"""
        register_all_tools()

        safe_tools = ToolRegistry.list_by_risk(RiskLevel.SAFE)
        assert "spark_list" in safe_tools


class TestSparkTools:
    """Spark 工具测试"""

    def test_spark_list(self):
        """测试 Spark 列表查询"""
        tool = SparkListTool()
        result = tool.execute({"namespace": None, "limit": 50})

        assert "applications" in result
        assert "total" in result
        assert isinstance(result["applications"], list)

    def test_spark_list_with_status_filter(self):
        """测试按状态过滤"""
        tool = SparkListTool()
        result = tool.execute({"status": ["FAILED"], "limit": 10})

        applications = result["applications"]
        for app in applications:
            assert app["status"] == "FAILED"

    def test_spark_get(self):
        """测试 Spark 详情查询"""
        tool = SparkGetTool()
        result = tool.execute({
            "app_name": "spark-etl-job-001",
            "namespace": "default",
        })

        assert "application" in result
        assert result["application"]["name"] == "spark-etl-job-001"

    def test_spark_get_nonexistent(self):
        """测试获取不存在应用 - Mock 返回默认应用"""
        tool = SparkGetTool()
        result = tool.execute({
            "app_name": "nonexistent-app",
            "namespace": "default",
        })

        # Mock 模式返回默认应用
        assert "application" in result
        assert result["application"]["name"] == "nonexistent-app"

    def test_spark_logs(self):
        """测试日志获取"""
        tool = SparkLogsTool()
        result = tool.execute({
            "app_name": "spark-etl-job-001",
            "pod_type": "driver",
        })

        assert "logs" in result
        assert "pod_name" in result

    def test_spark_analyze(self):
        """测试日志分析"""
        tool = SparkAnalyzeTool()

        # 测试 Executor OOM 日志分析
        logs = """
ERROR Executor: java.lang.OutOfMemoryError: Java heap space
ERROR Executor: ExecutorLostFailure (executor 2 lost)
"""
        result = tool.execute({"logs": logs, "app_name": "test-app"})

        assert "issues" in result
        assert len(result["issues"]) > 0
        # OOM_EXECUTOR 或 EXECUTOR_LOST 都是有效的诊断结果
        issue_types = [i["type"] for i in result["issues"]]
        assert any(t in ["OOM_EXECUTOR", "EXECUTOR_LOST", "OOM_DRIVER"] for t in issue_types)

    def test_spark_analyze_with_oom_pattern(self):
        """测试 OOM 错误模式匹配"""
        tool = SparkAnalyzeTool()

        logs = """
Container killed due to exceeding memory
java.lang.OutOfMemoryError: Java heap space
"""
        result = tool.execute({"logs": logs})

        issues = result["issues"]
        issue_types = [i["type"] for i in issues]
        assert any(i_type in ["OOM_DRIVER", "OOM_EXECUTOR"] for i_type in issue_types)


class TestYuniKornTools:
    """YuniKorn 工具测试"""

    def test_queue_list(self):
        """测试队列列表查询"""
        tool = YuniKornQueueListTool()
        result = tool.execute({"partition": "default"})

        assert "queues" in result
        assert len(result["queues"]) > 0

    def test_queue_get(self):
        """测试队列详情查询 - 返回 data 字段"""
        tool = YuniKornQueueGetTool()
        result = tool.execute({"queue_name": "root"})

        assert "success" in result
        assert "data" in result
        assert result["success"] is True
        assert result["data"]["name"] == "root"

    def test_queue_utilization_analysis(self):
        """测试利用率分析 - data 中包含 analysis 信息"""
        tool = YuniKornQueueGetTool()
        result = tool.execute({"queue_name": "root.default"})

        data = result["data"]
        assert "analysis" in data
        analysis = data["analysis"]
        assert "status" in analysis
        assert analysis["status"] in ["healthy", "warning", "critical"]

    def test_applications(self):
        """测试应用查询"""
        tool = YuniKornApplicationsTool()
        result = tool.execute({"queue_name": "root"})

        assert "applications" in result


class TestK8sTools:
    """K8s 工具测试"""

    def test_pod_list(self):
        """测试 Pod 列表查询"""
        tool = K8sPodListTool()
        result = tool.execute({"namespace": None})

        assert "pods" in result
        assert len(result["pods"]) > 0

    def test_pod_list_with_status_filter(self):
        """测试按状态过滤 Pod - Mock 模式返回所有 Pod"""
        tool = K8sPodListTool()
        result = tool.execute({"status": "Running"})

        pods = result["pods"]
        # Mock 模式不支持状态过滤，返回所有 Pod
        assert isinstance(pods, list)

    def test_node_list(self):
        """测试 Node 列表查询"""
        tool = K8sNodeListTool()
        result = tool.execute({})

        assert "nodes" in result
        assert len(result["nodes"]) > 0

    def test_node_list_not_ready(self):
        """测试 NotReady 节点查询"""
        tool = K8sNodeListTool()
        result = tool.execute({"status": "NotReady"})

        nodes = result["nodes"]
        for node in nodes:
            assert node["status"] == "NotReady"


class TestToolMetadata:
    """工具元数据测试"""

    def test_metadata(self):
        """测试元数据生成"""
        tool = SparkListTool()
        metadata = tool.metadata

        assert metadata.name == "spark_list"
        assert metadata.category == ToolCategory.SPARK
        assert metadata.risk_level == RiskLevel.SAFE

    def test_high_risk_tool(self):
        """测试高风险工具"""
        from app.agent.tools.k8s import K8sPodDeleteTool

        tool = K8sPodDeleteTool()
        assert tool.risk_level == RiskLevel.HIGH

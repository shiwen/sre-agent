"""工具模块单元测试"""

import pytest

from app.agent.tools.base import ToolCategory, get_tool, ToolRegistry
from app.agent.tools.spark import SparkListTool, SparkLogsTool, SparkAnalyzeTool
from app.agent.llm.registry import RiskLevel


@pytest.mark.unit
def test_spark_list_tool():
    """测试 Spark 列表查询工具"""
    tool = SparkListTool()

    result = tool.execute({"namespace": "default"})

    assert "applications" in result
    assert isinstance(result["applications"], list)


@pytest.mark.unit
def test_spark_list_tool_with_filter():
    """测试带状态筛选的 Spark 列表查询"""
    tool = SparkListTool()

    result = tool.execute({"namespace": "default", "status": "FAILED"})

    assert "applications" in result
    # 所有返回的应用状态应该是 FAILED
    for app in result["applications"]:
        assert app["status"] == "FAILED"


@pytest.mark.unit
def test_spark_logs_tool():
    """测试 Spark 日志获取工具"""
    tool = SparkLogsTool()

    result = tool.execute({"app_name": "spark-etl-job", "pod_type": "driver"})

    assert "logs" in result
    assert "namespace" in result


@pytest.mark.unit
def test_spark_analyze_tool():
    """测试 Spark 日志分析工具"""
    tool = SparkAnalyzeTool()

    # 模拟 OOM 错误日志
    mock_logs = """
    Executor lost (exit code 137)
    Container killed by YARN for exceeding memory limits
    OutOfMemoryError: Java heap space
    """

    result = tool.execute({"app_name": "spark-etl-job", "logs": mock_logs})

    assert "issues" in result
    assert len(result["issues"]) > 0

    # 应该检测到 OOM 问题
    oom_issues = [i for i in result["issues"] if "OOM" in i["type"]]
    assert len(oom_issues) > 0

    assert "recommendations" in result
    assert len(result["recommendations"]) > 0


@pytest.mark.unit
def test_tool_registry():
    """测试工具注册"""
    tools = ToolRegistry.list()

    # 应该注册了多个工具
    assert len(tools) >= 6

    # 检查工具分类
    spark_tools = ToolRegistry.list_by_category(ToolCategory.SPARK)
    assert len(spark_tools) >= 3

    yunikorn_tools = ToolRegistry.list_by_category(ToolCategory.YUNIKORN)
    assert len(yunikorn_tools) >= 3


@pytest.mark.unit
def test_get_tool_by_name():
    """测试通过名称获取工具"""
    tool = get_tool("spark_list")

    assert tool.name == "spark_list"
    assert tool.category == ToolCategory.SPARK
    assert tool.risk_level == RiskLevel.SAFE


@pytest.mark.unit
def test_tool_not_found():
    """测试获取不存在工具"""
    with pytest.raises(KeyError):
        get_tool("nonexistent_tool")


@pytest.mark.unit
def test_tool_metadata():
    """测试工具元数据"""
    tool = get_tool("spark_list")
    metadata = tool.metadata

    assert metadata.name == "spark_list"
    assert metadata.description
    assert metadata.category == ToolCategory.SPARK
    assert metadata.risk_level == RiskLevel.SAFE
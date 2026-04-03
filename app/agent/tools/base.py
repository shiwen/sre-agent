"""SRE Tool Base - 工具基类和注册表"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel
from structlog import get_logger

logger = get_logger()


class ToolCategory(str, Enum):
    """工具类别"""
    SPARK = "spark"
    YUNIKORN = "yunikorn"
    K8S = "k8s"
    ANALYSIS = "analysis"
    PATROL = "patrol"


class RiskLevel(str, Enum):
    """操作风险等级"""
    SAFE = "safe"       # 只读操作
    LOW = "low"         # 低风险写操作
    MEDIUM = "medium"   # 中风险操作
    HIGH = "high"       # 高风险操作（需审批）
    CRITICAL = "critical"  # 关键操作（强制审批)


class ToolResult(BaseModel):
    """工具执行结果"""
    success: bool = True
    data: dict[str, Any] = {}
    error: str | None = None
    message: str | None = None


class ToolMetadata(BaseModel):
    """工具元数据"""
    name: str
    description: str
    category: ToolCategory
    risk_level: RiskLevel = RiskLevel.SAFE
    args_schema: dict[str, Any] | None = None
    permissions: list[str] = []


class BaseTool(ABC):
    """工具基类"""

    name: str = ""
    description: str = ""
    category: ToolCategory = ToolCategory.SPARK
    risk_level: RiskLevel = RiskLevel.SAFE
    permissions: list[str] = []

    @property
    def metadata(self) -> ToolMetadata:
        """获取工具元数据"""
        return ToolMetadata(
            name=self.name,
            description=self.description,
            category=self.category,
            risk_level=self.risk_level,
            permissions=self.permissions,
        )

    @abstractmethod
    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        """执行工具逻辑

        Args:
            args: 工具参数

        Returns:
            执行结果字典
        """
        pass

    def validate_args(self, args: dict[str, Any]) -> bool:
        """验证参数"""
        return True  # 默认不做验证

    def log_execution(self, args: dict[str, Any], result: dict[str, Any]) -> None:
        """记录执行日志"""
        logger.info(
            "tool_executed",
            tool=self.name,
            category=self.category.value,
            risk_level=self.risk_level.value,
            success="error" not in result,
        )


class ToolRegistry:
    """工具注册表"""

    _tools: dict[str, BaseTool] = {}

    @classmethod
    def register(cls, tool: BaseTool) -> None:
        """注册工具"""
        if tool.name in cls._tools:
            logger.warning("tool_already_registered", tool=tool.name)
            return

        cls._tools[tool.name] = tool
        logger.info("tool_registered", tool=tool.name, category=tool.category.value)

    @classmethod
    def unregister(cls, tool_name: str) -> None:
        """取消注册工具"""
        if tool_name in cls._tools:
            del cls._tools[tool_name]
            logger.info("tool_unregistered", tool=tool_name)

    @classmethod
    def get(cls, tool_name: str) -> BaseTool:
        """获取工具"""
        if tool_name not in cls._tools:
            raise KeyError(f"工具不存在: {tool_name}")
        return cls._tools[tool_name]

    @classmethod
    def list(cls) -> list[str]:
        """列出所有工具名"""
        return list(cls._tools.keys())

    @classmethod
    def list_by_category(cls, category: ToolCategory) -> list[str]:
        """按类别列出工具"""
        return [
            name for name, tool in cls._tools.items()
            if tool.category == category
        ]

    @classmethod
    def list_by_risk(cls, risk_level: RiskLevel) -> list[str]:
        """按风险等级列出工具"""
        return [
            name for name, tool in cls._tools.items()
            if tool.risk_level == risk_level
        ]

    @classmethod
    def get_metadata(cls, tool_name: str) -> ToolMetadata:
        """获取工具元数据"""
        tool = cls.get(tool_name)
        return tool.metadata

    @classmethod
    def get_all_metadata(cls) -> list[ToolMetadata]:
        """获取所有工具元数据"""
        return [tool.metadata for tool in cls._tools.values()]


def get_tool(tool_name: str) -> BaseTool:
    """获取工具实例"""
    return ToolRegistry.get(tool_name)


def register_tool(tool: BaseTool) -> None:
    """注册单个工具"""
    ToolRegistry.register(tool)


def get_all_tools() -> list[BaseTool]:
    """获取所有工具实例"""
    return list(ToolRegistry._tools.values())


def get_tool_schemas() -> list[dict[str, Any]]:
    """获取所有工具的 JSON Schema"""
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "category": tool.category.value,
            "risk_level": tool.risk_level.value,
            "parameters": tool.args_schema if hasattr(tool, "args_schema") else {},
        }
        for tool in ToolRegistry._tools.values()
    ]


def register_all_tools() -> None:
    """注册所有工具"""
    from app.agent.tools.k8s import (
        K8sNodeGetTool,
        K8sNodeListTool,
        K8sPodGetTool,
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

    # 注册 Spark 工具
    ToolRegistry.register(SparkListTool())
    ToolRegistry.register(SparkGetTool())
    ToolRegistry.register(SparkLogsTool())
    ToolRegistry.register(SparkAnalyzeTool())

    # 注册 YuniKorn 工具
    ToolRegistry.register(YuniKornQueueListTool())
    ToolRegistry.register(YuniKornQueueGetTool())
    ToolRegistry.register(YuniKornApplicationsTool())

    # 注册 K8s 工具
    ToolRegistry.register(K8sPodListTool())
    ToolRegistry.register(K8sPodGetTool())
    ToolRegistry.register(K8sNodeListTool())
    ToolRegistry.register(K8sNodeGetTool())

    logger.info("all_tools_registered", count=len(ToolRegistry.list()))


# Mock 数据生成函数（用于开发和测试）
def _mock_spark_applications() -> list[dict[str, Any]]:
    """生成 Mock Spark 应用数据"""
    return [
        {
            "name": "spark-etl-job-001",
            "namespace": "default",
            "status": "COMPLETED",
            "driver_pod": "spark-etl-job-001-driver",
            "start_time": "2026-04-03T10:00:00Z",
            "end_time": "2026-04-03T10:30:00Z",
            "duration_seconds": 1800,
        },
        {
            "name": "spark-analytics-002",
            "namespace": "analytics",
            "status": "RUNNING",
            "driver_pod": "spark-analytics-002-driver",
            "start_time": "2026-04-03T11:00:00Z",
            "end_time": None,
            "duration_seconds": None,
        },
        {
            "name": "spark-batch-load-003",
            "namespace": "default",
            "status": "FAILED",
            "driver_pod": "spark-batch-load-003-driver",
            "start_time": "2026-04-03T09:00:00Z",
            "end_time": "2026-04-03T09:15:00Z",
            "duration_seconds": 900,
            "error_message": "Container killed due to OOM",
        },
    ]


def _mock_yunikorn_queues() -> list[dict[str, Any]]:
    """生成 Mock YuniKorn 队列数据"""
    return [
        {
            "name": "root",
            "path": "root",
            "utilization": 45,
            "used_memory": 102400,
            "max_memory": 227200,
            "used_vcore": 50,
            "max_vcore": 100,
            "running_apps": 3,
        },
        {
            "name": "root.default",
            "path": "root.default",
            "utilization": 60,
            "used_memory": 61440,
            "max_memory": 102400,
            "used_vcore": 30,
            "max_vcore": 50,
            "running_apps": 2,
        },
        {
            "name": "root.analytics",
            "path": "root.analytics",
            "utilization": 25,
            "used_memory": 25600,
            "max_memory": 102400,
            "used_vcore": 10,
            "max_vcore": 30,
            "running_apps": 1,
        },
    ]


def _mock_k8s_pods() -> list[dict[str, Any]]:
    """生成 Mock K8s Pod 数据"""
    return [
        {
            "name": "spark-etl-job-001-driver",
            "namespace": "default",
            "status": "Succeeded",
            "node": "node-01",
            "phase": "Succeeded",
            "restart_count": 0,
            "containers": ["driver"],
        },
        {
            "name": "spark-analytics-002-driver",
            "namespace": "analytics",
            "status": "Running",
            "node": "node-02",
            "phase": "Running",
            "restart_count": 0,
            "containers": ["driver", "executor-1", "executor-2"],
        },
        {
            "name": "spark-batch-load-003-driver",
            "namespace": "default",
            "status": "Failed",
            "node": "node-01",
            "phase": "Failed",
            "restart_count": 0,
            "containers": ["driver"],
            "error_reason": "OOMKilled",
        },
    ]


def _mock_k8s_nodes() -> list[dict[str, Any]]:
    """生成 Mock K8s Node 数据"""
    return [
        {
            "name": "node-01",
            "status": "Ready",
            "cpu_allocatable": 32,
            "mem_allocatable": "128Gi",
            "cpu_capacity": 32,
            "mem_capacity": "128Gi",
            "pods_running": 15,
        },
        {
            "name": "node-02",
            "status": "Ready",
            "cpu_allocatable": 32,
            "mem_allocatable": "128Gi",
            "cpu_capacity": 32,
            "mem_capacity": "128Gi",
            "pods_running": 12,
        },
        {
            "name": "node-03",
            "status": "NotReady",
            "cpu_allocatable": 32,
            "mem_allocatable": "128Gi",
            "cpu_capacity": 32,
            "mem_capacity": "128Gi",
            "pods_running": 0,
            "error_reason": "NetworkUnavailable",
        },
    ]

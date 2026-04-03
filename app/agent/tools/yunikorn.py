"""YuniKorn 队列查询工具"""

from typing import Any

from pydantic import BaseModel
from structlog import get_logger

from app.agent.tools.base import (
    BaseTool,
    RiskLevel,
    ToolCategory,
)

logger = get_logger()


class YuniKornQueueListArgs(BaseModel):
    """队列列表参数"""
    partition: str = "default"


class YuniKornQueueGetArgs(BaseModel):
    """队列详情参数"""
    queue_name: str
    partition: str = "default"


class YuniKornApplicationsArgs(BaseModel):
    """队列应用参数"""
    queue_name: str
    partition: str = "default"
    state: str | None = None  # Running, Pending, Completed, Failed
    limit: int = 50


class YuniKornQueueListTool(BaseTool):
    """YuniKorn 队列列表工具"""

    name = "yunikorn_queue_list"
    description = "查询 YuniKorn 所有队列状态"
    category = ToolCategory.YUNIKORN
    risk_level = RiskLevel.SAFE
    args_schema = YuniKornQueueListArgs

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        """执行查询"""
        kwargs = YuniKornQueueListArgs(**args).model_dump()

        # TODO: 实际实现需要 YuniKorn REST API client
        mock_queues = [
            {
                "name": "root",
                "partition": kwargs["partition"],
                "status": "active",
                "children": ["root.prod", "root.dev", "root.default"],
                "max_capacity": {
                    "memory": "100Gi",
                    "vcore": 100,
                },
                "used_capacity": {
                    "memory": "45Gi",
                    "vcore": 45,
                },
                "utilization": "45%",
                "pending_apps": 3,
                "running_apps": 5,
            },
            {
                "name": "root.prod",
                "partition": kwargs["partition"],
                "status": "active",
                "parent": "root",
                "max_capacity": {
                    "memory": "60Gi",
                    "vcore": 60,
                },
                "used_capacity": {
                    "memory": "35Gi",
                    "vcore": 35,
                },
                "utilization": "58%",
                "pending_apps": 1,
                "running_apps": 3,
                "properties": {
                    "guaranteed.memory": "40Gi",
                    "guaranteed.vcore": 40,
                },
            },
            {
                "name": "root.dev",
                "partition": kwargs["partition"],
                "status": "active",
                "parent": "root",
                "max_capacity": {
                    "memory": "30Gi",
                    "vcore": 30,
                },
                "used_capacity": {
                    "memory": "10Gi",
                    "vcore": 10,
                },
                "utilization": "33%",
                "pending_apps": 2,
                "running_apps": 2,
            },
            {
                "name": "root.default",
                "partition": kwargs["partition"],
                "status": "active",
                "parent": "root",
                "max_capacity": {
                    "memory": "10Gi",
                    "vcore": 10,
                },
                "used_capacity": {
                    "memory": "0Gi",
                    "vcore": 0,
                },
                "utilization": "0%",
                "pending_apps": 0,
                "running_apps": 0,
            },
        ]

        return {
            "success": True,
            "queues": mock_queues,
            "partition": kwargs["partition"],
            "total_queues": len(mock_queues),
        }


class YuniKornQueueGetTool(BaseTool):
    """YuniKorn 队列详情工具"""

    name = "yunikorn_queue_get"
    description = "查询指定队列的详细状态和资源配置"
    category = ToolCategory.YUNIKORN
    risk_level = RiskLevel.SAFE
    args_schema = YuniKornQueueGetArgs

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        """执行查询"""
        kwargs = YuniKornQueueGetArgs(**args).model_dump()

        # TODO: 实际实现需要 YuniKorn REST API
        mock_queue = {
            "name": kwargs["queue_name"],
            "partition": kwargs["partition"],
            "status": "active",
            "config": {
                "guaranteed_resources": {
                    "memory": "40Gi",
                    "vcore": 40,
                },
                "max_resources": {
                    "memory": "60Gi",
                    "vcore": 60,
                },
                "max_running_apps": 10,
                "scheduling_policy": "fair",
            },
            "current_usage": {
                "memory": "35Gi",
                "vcore": 35,
                "memory_percent": 58.3,
                "vcore_percent": 58.3,
            },
            "applications": {
                "pending": 1,
                "running": 3,
                "completed_today": 15,
                "failed_today": 2,
            },
            "health": {
                "status": "healthy",
                "warnings": [
                    "队列使用率接近上限,建议关注",
                ] if 58 > 50 else [],
            },
        }

        return {
            "success": True,
            "data": mock_queue,
        }


class YuniKornApplicationsTool(BaseTool):
    """YuniKorn 队列应用查询工具"""

    name = "yunikorn_applications"
    description = "查询指定队列中的应用状态"
    category = ToolCategory.YUNIKORN
    risk_level = RiskLevel.SAFE
    args_schema = YuniKornApplicationsArgs

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        """执行查询"""
        kwargs = YuniKornApplicationsArgs(**args).model_dump()

        # TODO: 实际实现需要 YuniKorn REST API
        mock_apps = [
            {
                "application_id": "app-spark-etl-001",
                "queue": kwargs["queue_name"],
                "state": "Running",
                "submission_time": "2026-04-03T08:00:00Z",
                "allocated_resources": {
                    "memory": "8Gi",
                    "vcore": 4,
                },
                "requested_resources": {
                    "memory": "12Gi",
                    "vcore": 6,
                },
                "pending_requests": 2,
                "max_used_resources": {
                    "memory": "10Gi",
                    "vcore": 5,
                },
            },
            {
                "application_id": "app-spark-analytics-002",
                "queue": kwargs["queue_name"],
                "state": "Failed",
                "submission_time": "2026-04-03T09:00:00Z",
                "terminated_time": "2026-04-03T09:15:00Z",
                "allocated_resources": {},
                "error_message": "Application failed: OOM",
            },
            {
                "application_id": "app-spark-streaming-003",
                "queue": kwargs["queue_name"],
                "state": "Pending",
                "submission_time": "2026-04-03T10:00:00Z",
                "requested_resources": {
                    "memory": "16Gi",
                    "vcore": 8,
                },
                "pending_requests": 5,
                "wait_time_seconds": 300,
            },
        ]

        # 状态筛选
        state = kwargs.get("state")
        filtered = [a for a in mock_apps if a["state"] == state] if state else mock_apps

        return {
            "success": True,
            "applications": filtered[:kwargs["limit"]],
            "queue": kwargs["queue_name"],
            "partition": kwargs["partition"],
            "total": len(filtered),
        }

"""YuniKorn 队列查询工具"""

from typing import Any

from pydantic import BaseModel
from structlog import get_logger

from app.agent.tools.base import (
    BaseTool,
    RiskLevel,
    ToolCategory,
)
from app.infrastructure.yunikorn_client import get_yunikorn_client

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

        # 使用 YuniKorn 客户端查询
        client = get_yunikorn_client()
        queues = client.list_queues(kwargs["partition"])

        return {
            "success": True,
            "queues": queues,
            "partition": kwargs["partition"],
            "total_queues": len(queues),
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

        # 使用 YuniKorn 客户端查询
        client = get_yunikorn_client()
        queue = client.get_queue(kwargs["queue_name"], kwargs["partition"])

        if not queue:
            return {
                "success": False,
                "error": f"队列不存在: {kwargs['queue_name']}",
            }

        # 添加分析
        analysis = self._analyze_queue(queue)

        return {
            "success": True,
            "data": {
                **queue,
                "analysis": analysis,
            },
        }

    def _analyze_queue(self, queue: dict[str, Any]) -> dict[str, Any]:
        """分析队列状态"""
        apps = queue.get("applications", {})
        running = apps.get("running", 0)
        pending = apps.get("pending", 0)

        # 计算利用率
        queue.get("current_usage", {}).get("allocated", {})
        queue.get("config", {}).get("max_resources", {})

        analysis = {
            "status": "healthy",
            "message": "队列运行正常",
            "warnings": [],
        }

        # 检查资源压力
        if pending > 5:
            analysis["status"] = "warning"
            analysis["warnings"].append(f"有 {pending} 个应用等待调度")

        if running > 20:
            analysis["warnings"].append(f"运行应用数较多 ({running})")

        return analysis


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

        # 使用 YuniKorn 客户端查询
        client = get_yunikorn_client()
        applications = client.list_applications(
            kwargs["queue_name"],
            kwargs["partition"],
            kwargs.get("state"),
        )

        # 截断
        applications = applications[:kwargs["limit"]]

        return {
            "success": True,
            "applications": applications,
            "queue": kwargs["queue_name"],
            "partition": kwargs["partition"],
            "total": len(applications),
        }

"""YuniKorn 客户端封装"""

from typing import Any, Optional
import httpx
from structlog import get_logger

logger = get_logger()

# YuniKorn 默认配置
YUNIKORN_DEFAULT_HOST = "http://yunikorn-service.yunikorn.svc.cluster.local:9080"
YUNIKORN_API_PREFIX = "/ws/v1"


class YuniKornClient:
    """YuniKorn REST API 客户端"""

    def __init__(self, host: Optional[str] = None, timeout: float = 10.0):
        self.host = host or YUNIKORN_DEFAULT_HOST
        self.timeout = timeout
        self._client: Optional[httpx.Client] = None

    @property
    def client(self) -> httpx.Client:
        """获取 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.Client(
                base_url=f"{self.host}{YUNIKORN_API_PREFIX}",
                timeout=self.timeout,
            )
        return self._client

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        """发送请求"""
        try:
            response = self.client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error("yunikorn_request_failed", method=method, path=path, error=str(e))
            return {"error": str(e)}
        except Exception as e:
            logger.error("yunikorn_unexpected_error", error=str(e))
            return {"error": str(e)}

    # ============ 队列操作 ============

    def list_queues(self, partition: str = "default") -> list[dict[str, Any]]:
        """列出所有队列
        
        Args:
            partition: 分区名称，默认为 "default"
        
        Returns:
            队列列表
        """
        result = self._request("GET", f"/partitions/{partition}/queues")
        
        if "error" in result:
            logger.warning("yunikorn_list_queues_failed", fallback="mock")
            return self._mock_queues()

        # 解析队列树
        queues = []
        root = result.get("rootQueue", {})
        self._flatten_queues(root, queues)
        return queues

    def _flatten_queues(self, queue: dict[str, Any], result: list[dict[str, Any]], parent: str = "") -> None:
        """展平队列树"""
        name = queue.get("queueName", "")
        full_name = f"{parent}.{name}" if parent else name
        
        queue_info = {
            "name": full_name,
            "partition": queue.get("partition"),
            "status": queue.get("status", "ACTIVE"),
            "pending_apps": queue.get("pendingApplications", 0),
            "running_apps": queue.get("runningApplications", 0),
            "max_capacity": queue.get("maxResource"),
            "used_capacity": queue.get("allocatedResource"),
            "guaranteed": queue.get("guaranteedResource"),
            "properties": queue.get("properties", {}),
        }
        result.append(queue_info)

        # 递归处理子队列
        for child in queue.get("children", []):
            self._flatten_queues(child, result, full_name)

    def get_queue(self, queue_name: str, partition: str = "default") -> dict[str, Any] | None:
        """获取队列详情
        
        Args:
            queue_name: 队列名称
            partition: 分区名称
        
        Returns:
            队列详情
        """
        result = self._request("GET", f"/partitions/{partition}/queues/{queue_name}")
        
        if "error" in result:
            logger.warning("yunikorn_get_queue_failed", queue=queue_name, fallback="mock")
            return self._mock_queue(queue_name)

        return self._parse_queue_detail(result)

    def _parse_queue_detail(self, data: dict[str, Any]) -> dict[str, Any]:
        """解析队列详情"""
        return {
            "name": data.get("queueName"),
            "partition": data.get("partition"),
            "status": data.get("status", "ACTIVE"),
            "config": {
                "max_resources": data.get("maxResource", {}),
                "guaranteed_resources": data.get("guaranteedResource", {}),
                "properties": data.get("properties", {}),
            },
            "current_usage": {
                "allocated": data.get("allocatedResource", {}),
                "pending": data.get("pendingResource", {}),
            },
            "applications": {
                "running": data.get("runningApplications", 0),
                "pending": data.get("pendingApplications", 0),
            },
        }

    # ============ 应用操作 ============

    def list_applications(
        self,
        queue_name: str = "root",
        partition: str = "default",
        state: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """列出队列中的应用
        
        Args:
            queue_name: 队列名称
            partition: 分区名称
            state: 状态过滤 (Running, Pending, Completed, Failed)
        
        Returns:
            应用列表
        """
        params = {}
        if state:
            params["state"] = state

        result = self._request(
            "GET",
            f"/partitions/{partition}/queues/{queue_name}/applications",
            params=params,
        )

        if "error" in result:
            logger.warning("yunikorn_list_apps_failed", fallback="mock")
            return self._mock_applications(queue_name)

        return [self._parse_application(app) for app in result.get("applications", [])]

    def get_application(self, app_id: str, partition: str = "default") -> dict[str, Any] | None:
        """获取应用详情
        
        Args:
            app_id: 应用 ID
            partition: 分区名称
        
        Returns:
            应用详情
        """
        result = self._request("GET", f"/partitions/{partition}/applications/{app_id}")

        if "error" in result:
            logger.warning("yunikorn_get_app_failed", app=app_id)
            return None

        return self._parse_application(result)

    def _parse_application(self, data: dict[str, Any]) -> dict[str, Any]:
        """解析应用数据"""
        return {
            "application_id": data.get("applicationID"),
            "queue": data.get("queueName"),
            "user": data.get("user"),
            "state": data.get("state", "UNKNOWN"),
            "submission_time": data.get("submissionTime"),
            "allocated_resource": data.get("allocatedResource", {}),
            "requested_resource": data.get("requestedResource", {}),
            "tasks": {
                "running": len([t for t in data.get("tasks", []) if t.get("state") == "RUNNING"]),
                "pending": len([t for t in data.get("tasks", []) if t.get("state") == "PENDING"]),
            },
        }

    # ============ 分区操作 ============

    def list_partitions(self) -> list[dict[str, Any]]:
        """列出所有分区"""
        result = self._request("GET", "/partitions")

        if "error" in result:
            return [{"name": "default", "state": "ACTIVE"}]

        return [
            {
                "name": p.get("name"),
                "state": p.get("state", "ACTIVE"),
                "last_state_transition": p.get("lastStateTransitionTime"),
            }
            for p in result.get("partitionInfo", [])
        ]

    # ============ 健康检查 ============

    def health_check(self) -> dict[str, Any]:
        """健康检查"""
        result = self._request("GET", "/cluster/health")
        
        if "error" in result:
            return {"status": "unhealthy", "error": result["error"]}

        return {
            "status": "healthy",
            "scheduler": result.get("Scheduler", {}).get("State", "UNKNOWN"),
        }

    # ============ Mock 数据 ============

    def _mock_queues(self) -> list[dict[str, Any]]:
        """Mock 队列列表"""
        return [
            {"name": "root", "partition": "default", "status": "ACTIVE", "pending_apps": 3, "running_apps": 5, "max_capacity": {"memory": "100Gi", "vcore": 100}, "used_capacity": {"memory": "45Gi", "vcore": 45}},
            {"name": "root.prod", "partition": "default", "status": "ACTIVE", "pending_apps": 1, "running_apps": 3, "max_capacity": {"memory": "60Gi", "vcore": 60}, "used_capacity": {"memory": "35Gi", "vcore": 35}},
            {"name": "root.dev", "partition": "default", "status": "ACTIVE", "pending_apps": 2, "running_apps": 2, "max_capacity": {"memory": "30Gi", "vcore": 30}, "used_capacity": {"memory": "10Gi", "vcore": 10}},
            {"name": "root.default", "partition": "default", "status": "ACTIVE", "pending_apps": 0, "running_apps": 0, "max_capacity": {"memory": "10Gi", "vcore": 10}, "used_capacity": {"memory": "0Gi", "vcore": 0}},
        ]

    def _mock_queue(self, queue_name: str) -> dict[str, Any]:
        """Mock 队列详情"""
        return {
            "name": queue_name,
            "partition": "default",
            "status": "ACTIVE",
            "config": {
                "max_resources": {"memory": "60Gi", "vcore": 60},
                "guaranteed_resources": {"memory": "40Gi", "vcore": 40},
            },
            "current_usage": {
                "allocated": {"memory": "35Gi", "vcore": 35},
                "pending": {"memory": "5Gi", "vcore": 5},
            },
            "applications": {"running": 3, "pending": 1},
        }

    def _mock_applications(self, queue_name: str) -> list[dict[str, Any]]:
        """Mock 应用列表"""
        return [
            {"application_id": "spark-etl-001", "queue": queue_name, "user": "spark", "state": "Running", "submission_time": "2026-04-03T10:00:00Z"},
            {"application_id": "spark-analytics-002", "queue": queue_name, "user": "analytics", "state": "Pending", "submission_time": "2026-04-03T11:00:00Z"},
        ]


# 全局实例
_yunikorn_client: Optional[YuniKornClient] = None


def get_yunikorn_client(host: Optional[str] = None) -> YuniKornClient:
    """获取全局 YuniKorn 客户端"""
    global _yunikorn_client
    if _yunikorn_client is None:
        _yunikorn_client = YuniKornClient(host)
    return _yunikorn_client
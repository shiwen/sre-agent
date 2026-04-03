"""Spark History Server 客户端封装"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from structlog import get_logger

logger = get_logger()

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logger.warning("httpx_not_available", note="Using mock data")


class SparkHistoryApp(BaseModel):
    """Spark History Server 应用信息"""

    id: str
    name: str
    status: str  # RUNNING, COMPLETED, FAILED
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_ms: int | None = None
    spark_user: str | None = None
    spark_version: str | None = None
    cores_per_executor: int | None = None
    memory_per_executor: str | None = None
    num_executors: int | None = None
    driver_host: str | None = None
    attempts: list[dict[str, Any]] = Field(default_factory=list)

    # 性能指标
    completed_tasks: int | None = None
    failed_tasks: int | None = None
    completed_stages: int | None = None
    failed_stages: int | None = None
    input_bytes: int | None = None
    output_bytes: int | None = None
    shuffle_read_bytes: int | None = None
    shuffle_write_bytes: int | None = None
    memory_bytes_spilled: int | None = None
    disk_bytes_spilled: int | None = None


class SparkHistoryEnvironment(BaseModel):
    """Spark 环境配置"""

    spark_properties: dict[str, str] = Field(default_factory=dict)
    system_properties: dict[str, str] = Field(default_factory=dict)
    classpath_entries: list[str] = Field(default_factory=list)
    jvm_info: dict[str, str] = Field(default_factory=dict)


class SparkHistoryExecutor(BaseModel):
    """Executor 信息"""

    id: str
    host: str
    port: int | None = None
    cores: int | None = None
    memory: str | None = None
    state: str  # RUNNING, LOST, DEAD
    active_tasks: int | None = None
    completed_tasks: int | None = None
    failed_tasks: int | None = None
    add_time: datetime | None = None
    remove_time: datetime | None = None
    total_memory_bytes: int | None = None
    total_disk_bytes: int | None = None


class SparkHistoryStage(BaseModel):
    """Stage 信息"""

    stage_id: int
    name: str
    description: str | None = None
    num_tasks: int
    completed_tasks: int = 0
    failed_tasks: int = 0
    active_tasks: int = 0
    status: str  # PENDING, RUNNING, SKIPPED, FAILED, COMPLETE
    submission_time: datetime | None = None
    completion_time: datetime | None = None
    duration_ms: int | None = None
    input_bytes: int | None = None
    output_bytes: int | None = None
    shuffle_read_bytes: int | None = None
    shuffle_write_bytes: int | None = None
    memory_bytes_spilled: int | None = None
    disk_bytes_spilled: int | None = None
    executor_run_time_ms: int | None = None


class SparkHistoryClient:
    """Spark History Server API 客户端"""

    def __init__(
        self,
        base_url: str = "http://localhost:18080",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client: httpx.AsyncClient | None = None
        self._initialized = False

    def _init_client(self) -> None:
        """初始化 HTTP 客户端"""
        if self._initialized:
            return

        if not HTTPX_AVAILABLE:
            logger.warning("history_client_unavailable", fallback="mock_mode")
            self._initialized = True
            return

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout_seconds),
            follow_redirects=True,
        )
        self._initialized = True

    async def close(self) -> None:
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def is_available(self) -> bool:
        """检查客户端是否可用"""
        self._init_client()
        return self._client is not None

    # ============ Application 查询 ============

    async def list_applications(
        self,
        status: str | None = None,
        min_date: datetime | None = None,
        max_date: datetime | None = None,
        limit: int = 100,
    ) -> list[SparkHistoryApp]:
        """列出历史应用"""
        self._init_client()

        if not self.is_available:
            return self._mock_applications()

        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status.upper()
        if min_date:
            params["minDate"] = min_date.isoformat()
        if max_date:
            params["maxDate"] = max_date.isoformat()

        try:
            response = await self._client.get("/api/v1/applications", params=params)
            response.raise_for_status()
            data = response.json()

            apps = []
            for item in data:
                try:
                    app = self._parse_application(item)
                    apps.append(app)
                except Exception as e:
                    logger.warning(
                        "parse_app_failed",
                        app_id=item.get("id"),
                        error=str(e),
                    )

            return apps

        except Exception as e:
            logger.error("list_applications_failed", error=str(e))
            return self._mock_applications()

    async def get_application(self, app_id: str) -> SparkHistoryApp | None:
        """获取应用详情"""
        self._init_client()

        if not self.is_available:
            return self._mock_application(app_id)

        try:
            response = await self._client.get(f"/api/v1/applications/{app_id}")
            response.raise_for_status()
            data = response.json()
            return self._parse_application(data)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("app_not_found", app_id=app_id)
                return None
            logger.error("get_app_failed", app_id=app_id, error=str(e))
            return None
        except Exception as e:
            logger.error("get_app_failed", app_id=app_id, error=str(e))
            return None

    async def get_application_environment(
        self, app_id: str
    ) -> SparkHistoryEnvironment | None:
        """获取应用环境配置"""
        self._init_client()

        if not self.is_available:
            return self._mock_environment()

        try:
            response = await self._client.get(
                f"/api/v1/applications/{app_id}/environment"
            )
            response.raise_for_status()
            data = response.json()

            return SparkHistoryEnvironment(
                spark_properties=data.get("sparkProperties", {}),
                system_properties=data.get("systemProperties", {}),
                classpath_entries=data.get("classpathEntries", []),
                jvm_info=data.get("jvmInformation", {}),
            )

        except Exception as e:
            logger.error("get_environment_failed", app_id=app_id, error=str(e))
            return None

    async def get_application_executors(
        self, app_id: str
    ) -> list[SparkHistoryExecutor]:
        """获取应用 Executor 信息"""
        self._init_client()

        if not self.is_available:
            return self._mock_executors()

        try:
            response = await self._client.get(
                f"/api/v1/applications/{app_id}/executors"
            )
            response.raise_for_status()
            data = response.json()

            executors = []
            for item in data:
                try:
                    executor = self._parse_executor(item)
                    executors.append(executor)
                except Exception as e:
                    logger.warning(
                        "parse_executor_failed",
                        executor_id=item.get("id"),
                        error=str(e),
                    )

            return executors

        except Exception as e:
            logger.error("get_executors_failed", app_id=app_id, error=str(e))
            return self._mock_executors()

    async def get_application_stages(self, app_id: str) -> list[SparkHistoryStage]:
        """获取应用 Stage 信息"""
        self._init_client()

        if not self.is_available:
            return self._mock_stages()

        try:
            response = await self._client.get(
                f"/api/v1/applications/{app_id}/stages"
            )
            response.raise_for_status()
            data = response.json()

            stages = []
            for item in data:
                try:
                    stage = self._parse_stage(item)
                    stages.append(stage)
                except Exception as e:
                    logger.warning(
                        "parse_stage_failed",
                        stage_id=item.get("stageId"),
                        error=str(e),
                    )

            return stages

        except Exception as e:
            logger.error("get_stages_failed", app_id=app_id, error=str(e))
            return self._mock_stages()

    async def get_application_logs(
        self, app_id: str, executor_id: str | None = None
    ) -> str:
        """获取应用日志"""
        self._init_client()

        if not self.is_available:
            return self._mock_logs(app_id)

        url = f"/api/v1/applications/{app_id}/logs"
        if executor_id:
            url = f"/api/v1/applications/{app_id}/executors/{executor_id}/logs"

        try:
            response = await self._client.get(url)
            response.raise_for_status()
            return response.text

        except Exception as e:
            logger.error("get_logs_failed", app_id=app_id, error=str(e))
            return ""

    async def get_application_sql(self, app_id: str) -> list[dict[str, Any]]:
        """获取 SQL 执行计划"""
        self._init_client()

        if not self.is_available:
            return self._mock_sql()

        try:
            response = await self._client.get(
                f"/api/v1/applications/{app_id}/SQL"
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error("get_sql_failed", app_id=app_id, error=str(e))
            return []

    # ============ 解析方法 ============

    def _parse_application(self, data: dict[str, Any]) -> SparkHistoryApp:
        """解析应用数据"""
        start_time = self._parse_timestamp(data.get("attempts", [{}])[0].get("startTime"))
        end_time = self._parse_timestamp(data.get("attempts", [{}])[0].get("endTime"))

        duration_ms = None
        if start_time and end_time:
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

        # 从尝试记录获取更多信息
        attempt = data.get("attempts", [{}])[0] if data.get("attempts") else {}

        return SparkHistoryApp(
            id=data.get("id", ""),
            name=data.get("name", ""),
            status="COMPLETED" if attempt.get("completed", False)
                else ("RUNNING" if end_time is None else "FAILED"),
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            spark_user=attempt.get("sparkUser"),
            spark_version=attempt.get("appSparkVersion"),
            cores_per_executor=attempt.get("appCoresPerExecutor"),
            memory_per_executor=attempt.get("appMemoryPerExecutorMB"),
            num_executors=attempt.get("appExecutorCores"),
            driver_host=attempt.get("driverHost"),
            attempts=data.get("attempts", []),
        )

    def _parse_executor(self, data: dict[str, Any]) -> SparkHistoryExecutor:
        """解析 Executor 数据"""
        return SparkHistoryExecutor(
            id=str(data.get("id", "")),
            host=data.get("host", ""),
            port=data.get("port"),
            cores=data.get("totalCores"),
            memory=data.get("totalMemory"),
            state="RUNNING" if data.get("isActive", True) else "DEAD",
            active_tasks=data.get("activeTasks", 0),
            completed_tasks=data.get("completedTasks", 0),
            failed_tasks=data.get("failedTasks", 0),
            add_time=self._parse_timestamp(data.get("addTime")),
            remove_time=self._parse_timestamp(data.get("removeTime")),
            total_memory_bytes=data.get("memoryUsed"),
            total_disk_bytes=data.get("diskUsed"),
        )

    def _parse_stage(self, data: dict[str, Any]) -> SparkHistoryStage:
        """解析 Stage 数据"""
        return SparkHistoryStage(
            stage_id=data.get("stageId", 0),
            name=data.get("name", ""),
            description=data.get("description"),
            num_tasks=data.get("numTasks", 0),
            completed_tasks=data.get("numCompleteTasks", 0),
            failed_tasks=data.get("numFailedTasks", 0),
            active_tasks=data.get("numActiveTasks", 0),
            status=data.get("status", "PENDING"),
            submission_time=self._parse_timestamp(data.get("submissionTime")),
            completion_time=self._parse_timestamp(data.get("completionTime")),
            duration_ms=data.get("executorRunTime"),
            input_bytes=data.get("inputBytes"),
            output_bytes=data.get("outputBytes"),
            shuffle_read_bytes=data.get("shuffleReadBytes"),
            shuffle_write_bytes=data.get("shuffleWriteBytes"),
            memory_bytes_spilled=data.get("memoryBytesSpilled"),
            disk_bytes_spilled=data.get("diskBytesSpilled"),
            executor_run_time_ms=data.get("executorRunTime"),
        )

    def _parse_timestamp(self, value: str | None) -> datetime | None:
        """解析时间戳"""
        if not value:
            return None

        try:
            # History Server 使用 ISO 格式
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None

    # ============ Mock 数据 ============

    def _mock_applications(self) -> list[SparkHistoryApp]:
        """Mock 应用列表"""
        return [
            SparkHistoryApp(
                id="app-20260403100000-0001",
                name="spark-etl-job",
                status="COMPLETED",
                start_time=datetime(2026, 4, 3, 10, 0, 0),
                end_time=datetime(2026, 4, 3, 10, 30, 0),
                duration_ms=1800000,
                spark_user="spark",
                num_executors=4,
                cores_per_executor=2,
                completed_tasks=100,
                failed_tasks=0,
            ),
            SparkHistoryApp(
                id="app-20260403110000-0002",
                name="spark-analytics",
                status="FAILED",
                start_time=datetime(2026, 4, 3, 11, 0, 0),
                end_time=datetime(2026, 4, 3, 11, 15, 0),
                duration_ms=900000,
                spark_user="spark",
                num_executors=3,
                cores_per_executor=4,
                completed_tasks=50,
                failed_tasks=10,
            ),
            SparkHistoryApp(
                id="app-20260403120000-0003",
                name="spark-batch-load",
                status="RUNNING",
                start_time=datetime(2026, 4, 3, 12, 0, 0),
                spark_user="spark",
                num_executors=8,
                cores_per_executor=4,
                completed_tasks=25,
                failed_tasks=0,
            ),
        ]

    def _mock_application(self, app_id: str) -> SparkHistoryApp:
        """Mock 单个应用"""
        return SparkHistoryApp(
            id=app_id,
            name="mock-spark-app",
            status="COMPLETED",
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration_ms=1000,
            spark_user="spark",
            num_executors=2,
            cores_per_executor=2,
            completed_tasks=10,
            failed_tasks=0,
        )

    def _mock_environment(self) -> SparkHistoryEnvironment:
        """Mock 环境配置"""
        return SparkHistoryEnvironment(
            spark_properties={
                "spark.executor.memory": "8g",
                "spark.executor.cores": "4",
                "spark.driver.memory": "4g",
                "spark.shuffle.partitions": "200",
            },
            system_properties={"java.version": "11"},
            classpath_entries=["/opt/spark/jars/*"],
            jvm_info={"Java VM Name": "OpenJDK 64-Bit Server VM"},
        )

    def _mock_executors(self) -> list[SparkHistoryExecutor]:
        """Mock Executor 列表"""
        return [
            SparkHistoryExecutor(
                id="0",
                host="192.168.1.10",
                port=3030,
                cores=4,
                memory="8g",
                state="RUNNING",
                active_tasks=2,
                completed_tasks=25,
                failed_tasks=0,
            ),
            SparkHistoryExecutor(
                id="1",
                host="192.168.1.11",
                port=3031,
                cores=4,
                memory="8g",
                state="RUNNING",
                active_tasks=3,
                completed_tasks=20,
                failed_tasks=1,
            ),
        ]

    def _mock_stages(self) -> list[SparkHistoryStage]:
        """Mock Stage 列表"""
        return [
            SparkHistoryStage(
                stage_id=0,
                name="Stage 0: read data",
                num_tasks=10,
                completed_tasks=10,
                failed_tasks=0,
                status="COMPLETE",
                duration_ms=5000,
                input_bytes=1024000,
            ),
            SparkHistoryStage(
                stage_id=1,
                name="Stage 1: transform",
                num_tasks=20,
                completed_tasks=15,
                failed_tasks=5,
                status="FAILED",
                duration_ms=10000,
                shuffle_read_bytes=512000,
            ),
        ]

    def _mock_logs(self, app_id: str) -> str:
        """Mock 日志"""
        return f"""
INFO SparkContext: Started Spark application {app_id}
INFO Driver: Starting driver
INFO Executor: Executor 0 started on host-1
INFO TaskSetManager: Starting task 0 in stage 0
ERROR Executor: OOM encountered while processing task
INFO SparkContext: Application finished
"""

    def _mock_sql(self) -> list[dict[str, Any]]:
        """Mock SQL 执行计划"""
        return [
            {
                "id": 0,
                "description": "Scan hive.default.table",
                "physicalPlan": "HiveTableScan",
                "duration": 1000,
            },
        ]


# 全局实例
_history_client: SparkHistoryClient | None = None


def get_history_client(
    base_url: str | None = None,
    timeout_seconds: float = 30.0,
) -> SparkHistoryClient:
    """获取全局 History Server 客户端"""
    global _history_client
    if _history_client is None:
        import os
        url = base_url or os.getenv("SPARK_HISTORY_SERVER_URL", "http://localhost:18080")
        _history_client = SparkHistoryClient(url, timeout_seconds)
    return _history_client

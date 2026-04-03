"""Spark 日志解析器

从 Spark History Server 获取日志并解析，提取结构化信息用于故障诊断。
"""

import re
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from structlog import get_logger

from app.infrastructure.history_client import (
    SparkHistoryApp,
    SparkHistoryStage,
    SparkHistoryExecutor,
    get_history_client,
)

logger = get_logger()


class LogEntryType(str, Enum):
    """日志条目类型"""
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    DEBUG = "DEBUG"
    METRIC = "METRIC"


class LogEntry(BaseModel):
    """解析后的日志条目"""
    timestamp: datetime | None = None
    level: LogEntryType
    source: str | None = None  # 来源组件（SparkContext, Executor, TaskSetManager 等）
    message: str
    context: dict[str, Any] = Field(default_factory=dict)  # 额外上下文
    raw_line: str | None = None


class ParsedLogResult(BaseModel):
    """解析结果"""
    app_id: str
    total_lines: int
    entries: list[LogEntry] = Field(default_factory=list)
    errors: list[LogEntry] = Field(default_factory=list)
    warnings: list[LogEntry] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    stages: dict[int, dict[str, Any]] = Field(default_factory=dict)
    executors: dict[str, dict[str, Any]] = Field(default_factory=dict)


class SparkLogParser:
    """Spark 日志解析器"""

    # 日志行格式正则（支持 ISO 和空格分隔格式）
    LOG_PATTERN = re.compile(
        r"^(?:(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[.,]?\d*Z?)\s+)?"
        r"(INFO|WARN|ERROR|DEBUG)\s+"
        r"([A-Za-z0-9_]+(?:\$\d+)?):\s+"
        r"(.+)$"
    )

    # 关键事件正则
    STAGE_START_PATTERN = re.compile(r"Starting stage (\d+).*\(.*\)")
    STAGE_END_PATTERN = re.compile(r"Stage (\d+).*finished")
    TASK_START_PATTERN = re.compile(r"Starting task (\d+).*in stage (\d+)")
    TASK_END_PATTERN = re.compile(r"Finished task (\d+).*in stage (\d+)")
    EXECUTOR_ADD_PATTERN = re.compile(r"Executor[^\d]*(\d+)[^\d]*(?:added|started)")
    EXECUTOR_REMOVE_PATTERN = re.compile(r"Executor[^\d]*(\d+)[^\d]*(?:removed|lost)")
    JOB_START_PATTERN = re.compile(r"Starting job (\d+)")
    JOB_END_PATTERN = re.compile(r"Job (\d+).*finished")

    # 指标正则
    METRIC_PATTERN = re.compile(
        r"(bytes|records|ms|tasks|stages).*[:=]\s*(\d+)"
    )

    # 错误模式（扩展版）
    ERROR_PATTERNS = {
        "oom_driver": [
            re.compile(r"java\.lang\.OutOfMemoryError.*driver", re.I),
            re.compile(r"Container.*killed.*driver.*memory", re.I),
        ],
        "oom_executor": [
            re.compile(r"java\.lang\.OutOfMemoryError.*heap", re.I),
            re.compile(r"Executor.*OOM", re.I),
            re.compile(r"Container.*exceeded.*memory", re.I),
        ],
        "shuffle_failure": [
            re.compile(r"FetchFailedException", re.I),
            re.compile(r"Failed.*shuffle.*block", re.I),
            re.compile(r"Connection.*refused.*shuffle", re.I),
        ],
        "executor_lost": [
            re.compile(r"ExecutorLostFailure", re.I),
            re.compile(r"Executor.*lost", re.I),
            re.compile(r"Container.*exit", re.I),
        ],
        "stage_failure": [
            re.compile(r"Stage (\d+).*failed", re.I),
            re.compile(r"TaskSetManager:.*failed", re.I),
        ],
        "class_not_found": [
            re.compile(r"ClassNotFoundException", re.I),
            re.compile(r"NoClassDefFoundError", re.I),
        ],
        "spark_context_error": [
            re.compile(r"SparkContext.*stopped", re.I),
            re.compile(r"SparkContext.*error", re.I),
        ],
    }

    def __init__(self) -> None:
        self._history_client = get_history_client()

    async def parse_application_logs(
        self,
        app_id: str,
        include_executor_logs: bool = False,
    ) -> ParsedLogResult:
        """解析应用日志"""
        logger.info("parse_logs_start", app_id=app_id)

        # 从 History Server 获取日志
        driver_logs = await self._history_client.get_application_logs(app_id)

        # 解析 Driver 日志
        result = self._parse_log_text(app_id, driver_logs, "driver")

        # 可选：解析 Executor 日志
        if include_executor_logs:
            executors = await self._history_client.get_application_executors(app_id)
            for executor in executors:
                executor_logs = await self._history_client.get_application_logs(
                    app_id, executor.id
                )
                executor_result = self._parse_log_text(
                    app_id, executor_logs, f"executor-{executor.id}"
                )
                result.entries.extend(executor_result.entries)
                result.errors.extend(executor_result.errors)
                result.executors[executor.id] = {
                    "parsed": executor_result.total_lines,
                    "errors": len(executor_result.errors),
                }

        # 从 History Server 获取补充信息
        await self._enrich_with_history_data(app_id, result)

        logger.info(
            "parse_logs_done",
            app_id=app_id,
            total=result.total_lines,
            errors=len(result.errors),
        )

        return result

    def _parse_log_text(
        self,
        app_id: str,
        log_text: str,
        source: str,
    ) -> ParsedLogResult:
        """解析日志文本"""
        lines = log_text.split("\n")
        result = ParsedLogResult(
            app_id=app_id,
            total_lines=len(lines),
        )

        for line in lines:
            line = line.strip()
            if not line:
                continue

            entry = self._parse_line(line, source)
            if entry:
                result.entries.append(entry)

                # 分类
                if entry.level == LogEntryType.ERROR:
                    result.errors.append(entry)
                elif entry.level == LogEntryType.WARN:
                    result.warnings.append(entry)

                # 提取事件
                self._extract_events(entry, result)

        return result

    def _parse_line(self, line: str, default_source: str) -> LogEntry | None:
        """解析单行日志"""
        match = self.LOG_PATTERN.match(line)
        if match:
            timestamp_str, level, source, message = match.groups()

            timestamp = None
            if timestamp_str:
                timestamp = self._parse_timestamp(timestamp_str)

            return LogEntry(
                timestamp=timestamp,
                level=LogEntryType(level),
                source=source,
                message=message,
                raw_line=line,
            )

        # 不匹配标准格式，尝试提取级别
        for level_type in [LogEntryType.ERROR, LogEntryType.WARN, LogEntryType.INFO]:
            if level_type.value in line.upper():
                return LogEntry(
                    level=level_type,
                    source=default_source,
                    message=line,
                    raw_line=line,
                )

        # 默认 INFO
        return LogEntry(
            level=LogEntryType.INFO,
            source=default_source,
            message=line,
            raw_line=line,
        )

    def _parse_timestamp(self, ts_str: str) -> datetime | None:
        """解析时间戳"""
        try:
            # 处理不同格式
            ts_str = ts_str.replace(",", ".")
            if "T" in ts_str:
                return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            else:
                # 空格分隔格式
                return datetime.strptime(ts_str[:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    def _extract_events(self, entry: LogEntry, result: ParsedLogResult) -> None:
        """提取关键事件"""

        # Stage 事件
        stage_match = self.STAGE_START_PATTERN.search(entry.message)
        if stage_match:
            stage_id = int(stage_match.group(1))
            result.stages[stage_id] = {
                "start_time": entry.timestamp,
                "start_entry": entry,
                "status": "running",
            }

        stage_match = self.STAGE_END_PATTERN.search(entry.message)
        if stage_match:
            stage_id = int(stage_match.group(1))
            if stage_id in result.stages:
                result.stages[stage_id]["end_time"] = entry.timestamp
                result.stages[stage_id]["status"] = "completed"

        # Executor 事件
        exec_match = self.EXECUTOR_ADD_PATTERN.search(entry.message)
        if exec_match:
            exec_id = exec_match.group(1)
            result.executors[exec_id] = {
                "add_time": entry.timestamp,
                "status": "running",
            }

        exec_match = self.EXECUTOR_REMOVE_PATTERN.search(entry.message)
        if exec_match:
            exec_id = exec_match.group(1)
            if exec_id in result.executors:
                result.executors[exec_id]["remove_time"] = entry.timestamp
                result.executors[exec_id]["status"] = "removed"

        # 指标提取
        metrics = self.METRIC_PATTERN.findall(entry.message)
        for metric_name, value in metrics:
            result.metrics[metric_name] = int(value)

    async def _enrich_with_history_data(
        self,
        app_id: str,
        result: ParsedLogResult,
    ) -> None:
        """使用 History Server 数据补充"""
        # 获取应用信息
        app = await self._history_client.get_application(app_id)
        if app:
            result.metrics["duration_ms"] = app.duration_ms
            result.metrics["completed_tasks"] = app.completed_tasks
            result.metrics["failed_tasks"] = app.failed_tasks

        # 获取 Stage 详情
        stages = await self._history_client.get_application_stages(app_id)
        for stage in stages:
            if stage.stage_id not in result.stages:
                result.stages[stage.stage_id] = {}
            result.stages[stage.stage_id].update({
                "name": stage.name,
                "num_tasks": stage.num_tasks,
                "completed_tasks": stage.completed_tasks,
                "failed_tasks": stage.failed_tasks,
                "duration_ms": stage.duration_ms,
                "shuffle_read": stage.shuffle_read_bytes,
                "shuffle_write": stage.shuffle_write_bytes,
            })

    def classify_errors(
        self,
        result: ParsedLogResult,
    ) -> dict[str, list[LogEntry]]:
        """分类错误"""
        classified: dict[str, list[LogEntry]] = {}

        for error in result.errors:
            for error_type, patterns in self.ERROR_PATTERNS.items():
                for pattern in patterns:
                    if pattern.search(error.message):
                        classified.setdefault(error_type, []).append(error)
                        break

        return classified

    def get_error_summary(
        self,
        result: ParsedLogResult,
    ) -> dict[str, Any]:
        """获取错误摘要"""
        classified = self.classify_errors(result)

        summary = {
            "app_id": result.app_id,
            "total_errors": len(result.errors),
            "total_warnings": len(result.warnings),
            "error_types": {},
            "most_severe": None,
        }

        for error_type, entries in classified.items():
            summary["error_types"][error_type] = {
                "count": len(entries),
                "first_occurrence": entries[0].timestamp,
                "last_occurrence": entries[-1].timestamp if len(entries) > 1 else entries[0].timestamp,
                "sample_message": entries[0].message[:200],
            }

        # 确定最严重错误
        severity_order = ["oom_driver", "oom_executor", "shuffle_failure", "executor_lost"]
        for error_type in severity_order:
            if error_type in classified:
                summary["most_severe"] = error_type
                break

        return summary

    def generate_diagnostic_report(
        self,
        result: ParsedLogResult,
        app: SparkHistoryApp | None = None,
        stages: list[SparkHistoryStage] | None = None,
    ) -> dict[str, Any]:
        """生成诊断报告"""
        error_summary = self.get_error_summary(result)
        classified = self.classify_errors(result)

        # 根因分析
        root_cause = self._analyze_root_cause(classified, result)

        # 建议
        recommendations = self._generate_recommendations(root_cause, classified)

        report = {
            "app_id": result.app_id,
            "analysis_timestamp": datetime.now().isoformat(),
            "application_info": {
                "name": app.name if app else "unknown",
                "status": app.status if app else "unknown",
                "duration_ms": app.duration_ms if app else None,
                "spark_user": app.spark_user if app else None,
            },
            "log_analysis": {
                "total_lines": result.total_lines,
                "errors": error_summary["total_errors"],
                "warnings": error_summary["total_warnings"],
            },
            "stage_analysis": self._analyze_stages(result, stages),
            "error_analysis": error_summary,
            "root_cause": root_cause,
            "recommendations": recommendations,
        }

        return report

    def _analyze_root_cause(
        self,
        classified: dict[str, list[LogEntry]],
        result: ParsedLogResult,
    ) -> dict[str, Any]:
        """根因分析"""
        root_cause = {
            "primary": None,
            "secondary": [],
            "confidence": 0.0,
        }

        if not classified:
            return root_cause

        # 按优先级确定主因
        priority_order = [
            ("oom_driver", "Driver 内存不足", 0.9),
            ("oom_executor", "Executor 内存不足", 0.85),
            ("shuffle_failure", "Shuffle 数据传输失败", 0.8),
            ("executor_lost", "Executor 异常丢失", 0.7),
            ("stage_failure", "Stage 执行失败", 0.6),
            ("class_not_found", "依赖缺失", 0.95),
        ]

        for error_type, cause, confidence in priority_order:
            if error_type in classified:
                root_cause["primary"] = {
                    "type": error_type,
                    "cause": cause,
                    "confidence": confidence,
                    "count": len(classified[error_type]),
                }
                break

        # 次要原因
        for error_type, entries in classified.items():
            if root_cause["primary"] and error_type != root_cause["primary"]["type"]:
                root_cause["secondary"].append({
                    "type": error_type,
                    "count": len(entries),
                })

        return root_cause

    def _analyze_stages(
        self,
        result: ParsedLogResult,
        stages: list[SparkHistoryStage] | None = None,
    ) -> dict[str, Any]:
        """Stage 分析"""
        stage_analysis = {
            "total_stages": len(result.stages),
            "failed_stages": [],
            "slow_stages": [],
            "shuffle_heavy_stages": [],
        }

        for stage_id, stage_data in result.stages.items():
            # 失败的 Stage
            if stage_data.get("status") == "failed" or stage_data.get("failed_tasks", 0) > 0:
                stage_analysis["failed_stages"].append({
                    "stage_id": stage_id,
                    "name": stage_data.get("name"),
                    "failed_tasks": stage_data.get("failed_tasks", 0),
                })

            # 慢 Stage（> 5 分钟）
            duration = stage_data.get("duration_ms", 0)
            if duration > 300000:
                stage_analysis["slow_stages"].append({
                    "stage_id": stage_id,
                    "name": stage_data.get("name"),
                    "duration_ms": duration,
                })

            # Shuffle 重 Stage
            shuffle_read = stage_data.get("shuffle_read", 0)
            shuffle_write = stage_data.get("shuffle_write", 0)
            if shuffle_read > 1000000000 or shuffle_write > 1000000000:  # > 1GB
                stage_analysis["shuffle_heavy_stages"].append({
                    "stage_id": stage_id,
                    "name": stage_data.get("name"),
                    "shuffle_read_bytes": shuffle_read,
                    "shuffle_write_bytes": shuffle_write,
                })

        return stage_analysis

    def _generate_recommendations(
        self,
        root_cause: dict[str, Any],
        classified: dict[str, list[LogEntry]],
    ) -> list[dict[str, Any]]:
        """生成建议"""
        recommendations = []

        if not root_cause["primary"]:
            return recommendations

        primary_type = root_cause["primary"]["type"]

        recommendation_map = {
            "oom_driver": [
                {"action": "增加 spark.driver.memory", "priority": 1},
                {"action": "检查是否有 collect() 大数据集", "priority": 2},
                {"action": "优化代码减少 Driver 内存占用", "priority": 3},
            ],
            "oom_executor": [
                {"action": "增加 spark.executor.memory", "priority": 1},
                {"action": "减少 spark.executor.cores 降低并行度", "priority": 2},
                {"action": "增加 spark.executor.instances 分担压力", "priority": 3},
                {"action": "检查是否有数据倾斜", "priority": 4},
            ],
            "shuffle_failure": [
                {"action": "检查网络连通性", "priority": 1},
                {"action": "增加 spark.shuffle.io.maxRetries", "priority": 2},
                {"action": "增加 spark.shuffle.io.retryWait", "priority": 3},
            ],
            "executor_lost": [
                {"action": "检查 Executor 资源配置", "priority": 1},
                {"action": "查看 Executor 日志确定原因", "priority": 2},
                {"action": "检查是否有外部 kill 信号", "priority": 3},
            ],
            "class_not_found": [
                {"action": "检查 spark.jars 配置", "priority": 1},
                {"action": "确认依赖包已正确上传", "priority": 2},
            ],
            "stage_failure": [
                {"action": "检查 Stage 具体错误原因", "priority": 1},
                {"action": "检查是否有数据问题", "priority": 2},
            ],
        }

        for rec in recommendation_map.get(primary_type, []):
            recommendations.append({
                **rec,
                "reason": root_cause["primary"]["cause"],
                "confidence": root_cause["primary"]["confidence"],
            })

        return recommendations


# 全局实例
_log_parser: SparkLogParser | None = None


def get_log_parser() -> SparkLogParser:
    """获取日志解析器实例"""
    global _log_parser
    if _log_parser is None:
        _log_parser = SparkLogParser()
    return _log_parser
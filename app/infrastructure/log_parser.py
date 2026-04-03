"""Spark 日志解析器

解析 Spark driver/executor 日志，提取结构化事件和错误信息。
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from structlog import get_logger

logger = get_logger()


class LogLevel(str, Enum):
    """日志级别"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    FATAL = "FATAL"


class LogSource(str, Enum):
    """日志来源"""

    DRIVER = "driver"
    EXECUTOR = "executor"
    UNKNOWN = "unknown"


class ParsedLogEntry(BaseModel):
    """解析后的日志条目"""

    timestamp: datetime | None = None
    level: LogLevel
    source: LogSource = LogSource.UNKNOWN
    component: str = ""
    message: str
    exception_type: str | None = None
    exception_message: str | None = None
    stack_trace: str | None = None
    raw_line: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    # 关联信息
    app_id: str | None = None
    executor_id: str | None = None
    stage_id: int | None = None
    task_id: int | None = None
    job_id: int | None = None


class ErrorPattern(BaseModel):
    """错误模式定义"""

    name: str
    pattern: re.Pattern
    category: str
    severity: str = "medium"  # low, medium, high, critical
    description: str = ""
    suggestions: list[str] = Field(default_factory=list)


@dataclass
class LogPattern:
    """日志格式模式"""

    name: str
    regex: re.Pattern
    level: LogLevel
    component: str = ""


# 常见的 Spark 日志格式
SPARK_LOG_PATTERNS = [
    # 标准 Spark 日志格式: 24/04/03 10:00:00 INFO Driver: message
    LogPattern(
        name="standard",
        regex=re.compile(
            r"^(\d{2}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})\s+"
            r"(DEBUG|INFO|WARN|ERROR|FATAL)\s+"
            r"(\S+):\s*(.*)$"
        ),
        level=LogLevel.INFO,
    ),
    # 带年份的格式: 2026-04-03 10:00:00,000 INFO Driver: message
    LogPattern(
        name="with_year",
        regex=re.compile(
            r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}[,.]\d{3})\s+"
            r"(DEBUG|INFO|WARN|ERROR|FATAL)\s+"
            r"(\S+):\s*(.*)$"
        ),
        level=LogLevel.INFO,
    ),
    # YARN 日志格式
    LogPattern(
        name="yarn",
        regex=re.compile(
            r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}[,.]\d{3})\s+"
            r"\[([A-Z]+)\]\s+\[([^\]]+)\]\s+(.*)$"
        ),
        level=LogLevel.INFO,
    ),
    # Kubernetes pod 日志格式
    LogPattern(
        name="k8s",
        regex=re.compile(
            r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)\s+"
            r"(DEBUG|INFO|WARN|ERROR|FATAL)\s+"
            r"(\S+):\s*(.*)$"
        ),
        level=LogLevel.INFO,
    ),
]

# 常见的 Spark 错误模式（按优先级排序，更具体的模式优先）
SPARK_ERROR_PATTERNS = [
    ErrorPattern(
        name="gc_overhead",
        pattern=re.compile(r"GC overhead limit exceeded|OutOfMemoryError.*GC overhead"),
        category="resource",
        severity="high",
        description="GC overhead limit exceeded",
        suggestions=[
            "Increase heap size",
            "Tune GC settings",
            "Reduce memory pressure",
        ],
    ),
    ErrorPattern(
        name="oom_executor",
        pattern=re.compile(r"java\.lang\.OutOfMemoryError|Container.*killed.*OOM"),
        category="resource",
        severity="critical",
        description="Out of memory error",
        suggestions=[
            "Increase executor memory (spark.executor.memory)",
            "Reduce partition size (spark.sql.shuffle.partitions)",
            "Enable memory optimization (spark.sql.adaptive.enabled)",
        ],
    ),
    ErrorPattern(
        name="oom_driver",
        pattern=re.compile(r"Driver.*OutOfMemoryError|driver.*OOM"),
        category="resource",
        severity="critical",
        description="Driver out of memory",
        suggestions=[
            "Increase driver memory (spark.driver.memory)",
            "Reduce result collect size",
            "Use collect() sparingly",
        ],
    ),
    ErrorPattern(
        name="shuffle_failed",
        pattern=re.compile(r"shuffle.*failed|FetchFailedException|ShuffleError"),
        category="shuffle",
        severity="high",
        description="Shuffle operation failed",
        suggestions=[
            "Check executor health",
            "Increase shuffle service memory",
            "Enable external shuffle service",
        ],
    ),
    ErrorPattern(
        name="stage_failure",
        pattern=re.compile(r"Stage\s+\d+\s+failed|org\.apache\.spark\.SparkException.*stage"),
        category="execution",
        severity="high",
        description="Stage execution failed",
        suggestions=[
            "Check executor logs for details",
            "Verify data partitioning",
            "Check for data skew",
        ],
    ),
    ErrorPattern(
        name="task_failure",
        pattern=re.compile(r"TaskSetManager:\s+lost task|Task failed|TaskSetManager.*failed"),
        category="execution",
        severity="medium",
        description="Task execution failed",
        suggestions=[
            "Check executor logs",
            "Verify input data integrity",
            "Increase task retry count",
        ],
    ),
    ErrorPattern(
        name="connection_refused",
        pattern=re.compile(r"Connection refused|java\.net\.ConnectException"),
        category="network",
        severity="high",
        description="Network connection refused",
        suggestions=[
            "Check service availability",
            "Verify network configuration",
            "Check firewall rules",
        ],
    ),
    ErrorPattern(
        name="timeout",
        pattern=re.compile(r"timeout|TimeoutException|java\.util\.concurrent\.TimeoutException"),
        category="network",
        severity="medium",
        description="Operation timeout",
        suggestions=[
            "Increase timeout settings",
            "Check network latency",
            "Verify cluster health",
        ],
    ),
    ErrorPattern(
        name="disk_full",
        pattern=re.compile(r"No space left on device|disk.*full|IOException.*disk"),
        category="storage",
        severity="critical",
        description="Disk space exhausted",
        suggestions=[
            "Clean up temporary files",
            "Increase disk size",
            "Configure spark.local.dir to larger volume",
        ],
    ),
    ErrorPattern(
        name="executor_lost",
        pattern=re.compile(r"ExecutorLostFailure|Executor.*lost|Removed executor"),
        category="executor",
        severity="high",
        description="Executor lost or removed",
        suggestions=[
            "Check executor memory",
            "Check for OOM errors",
            "Review resource allocation",
        ],
    ),
    ErrorPattern(
        name="class_not_found",
        pattern=re.compile(r"ClassNotFoundException|NoClassDefFoundError"),
        category="dependency",
        severity="medium",
        description="Class not found",
        suggestions=[
            "Check jar dependencies",
            "Verify spark-submit --jars",
            "Check classpath",
        ],
    ),
    ErrorPattern(
        name="schema_mismatch",
        pattern=re.compile(r"Schema.*mismatch|cannot resolve.*column"),
        category="data",
        severity="medium",
        description="Schema mismatch or column not found",
        suggestions=[
            "Verify data schema",
            "Check column names",
            "Use schema inference",
        ],
    ),
    ErrorPattern(
        name="broadcast_timeout",
        pattern=re.compile(r"Broadcast timeout|BroadcastJobAbortException"),
        category="execution",
        severity="medium",
        description="Broadcast variable timeout",
        suggestions=[
            "Increase spark.sql.broadcastTimeout",
            "Reduce broadcast data size",
            "Disable broadcast join",
        ],
    ),
]

# 元数据提取模式
METADATA_PATTERNS = {
    "app_id": re.compile(r"application_(\d+_\d+)"),
    "executor_id": re.compile(r"executor[_\s]+(\d+)", re.IGNORECASE),
    "stage_id": re.compile(r"stage[_\s]+(\d+)", re.IGNORECASE),
    "task_id": re.compile(r"task[_\s]+(\d+)", re.IGNORECASE),
    "job_id": re.compile(r"job[_\s]+(\d+)", re.IGNORECASE),
    "attempt_id": re.compile(r"attempt[_\s]+(\d+)", re.IGNORECASE),
    "partition_id": re.compile(r"partition[_\s]+(\d+)", re.IGNORECASE),
}


class SparkLogParser:
    """Spark 日志解析器"""

    def __init__(self, custom_patterns: list[ErrorPattern] | None = None):
        self.patterns = SPARK_LOG_PATTERNS
        self.error_patterns = SPARK_ERROR_PATTERNS.copy()
        if custom_patterns:
            self.error_patterns.extend(custom_patterns)

    def parse_line(self, line: str) -> ParsedLogEntry | None:
        """解析单行日志"""
        line = line.strip()
        if not line:
            return None

        # 尝试匹配各种日志格式
        for log_pattern in self.patterns:
            match = log_pattern.regex.match(line)
            if match:
                return self._parse_match(log_pattern, match, line)

        # 无法匹配已知格式，创建基本条目
        level = self._detect_level(line)
        return ParsedLogEntry(
            level=level,
            message=line,
            raw_line=line,
        )

    def _parse_match(
        self, pattern: LogPattern, match: re.Match, raw_line: str
    ) -> ParsedLogEntry:
        """解析匹配结果"""
        groups = match.groups()
        timestamp_str = groups[0] if groups else None
        level_str = groups[1] if len(groups) > 1 else "INFO"
        component = groups[2] if len(groups) > 2 else ""
        message = groups[3] if len(groups) > 3 else ""

        # 解析时间戳
        timestamp = self._parse_timestamp(timestamp_str)

        # 解析日志级别
        try:
            level = LogLevel[level_str.upper()]
        except KeyError:
            level = pattern.level

        # 创建条目
        entry = ParsedLogEntry(
            timestamp=timestamp,
            level=level,
            component=component,
            message=message,
            raw_line=raw_line,
        )

        # 提取元数据
        self._extract_metadata(entry)

        # 检测错误模式
        self._detect_error_pattern(entry)

        return entry

    def _parse_timestamp(self, ts_str: str | None) -> datetime | None:
        """解析时间戳"""
        if not ts_str:
            return None

        formats = [
            "%y/%m/%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S,%f",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%d %H:%M:%S",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(ts_str, fmt)
            except ValueError:
                continue

        return None

    def _detect_level(self, line: str) -> LogLevel:
        """检测日志级别"""
        line_upper = line.upper()
        for level in [LogLevel.FATAL, LogLevel.ERROR, LogLevel.WARN, LogLevel.INFO, LogLevel.DEBUG]:
            if level.value in line_upper:
                return level
        return LogLevel.INFO

    def _extract_metadata(self, entry: ParsedLogEntry) -> None:
        """从消息中提取元数据"""
        full_text = f"{entry.component} {entry.message}"

        for key, pattern in METADATA_PATTERNS.items():
            match = pattern.search(full_text)
            if match:
                value = match.group(1)
                if key == "app_id":
                    entry.app_id = f"application_{value}"
                elif key == "executor_id":
                    entry.executor_id = value
                elif key == "stage_id":
                    entry.stage_id = int(value)
                elif key == "task_id":
                    entry.task_id = int(value)
                elif key == "job_id":
                    entry.job_id = int(value)
                else:
                    entry.metadata[key] = value

        # 检测来源
        if "driver" in entry.component.lower() or "Driver" in entry.message:
            entry.source = LogSource.DRIVER
        elif "executor" in entry.component.lower() or entry.executor_id:
            entry.source = LogSource.EXECUTOR

    def _detect_error_pattern(self, entry: ParsedLogEntry) -> None:
        """检测错误模式"""
        full_text = entry.raw_line

        for pattern in self.error_patterns:
            if pattern.pattern.search(full_text):
                entry.metadata["error_pattern"] = pattern.name
                entry.metadata["error_category"] = pattern.category
                entry.metadata["error_severity"] = pattern.severity
                entry.metadata["error_description"] = pattern.description
                entry.metadata["error_suggestions"] = pattern.suggestions
                break

        # 检测异常类型（优先匹配完整类名）
        exception_match = re.search(
            r"(java\.[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*(?:Exception|Error))"
            r"|([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*Exception)",
            full_text,
        )
        if exception_match:
            entry.exception_type = exception_match.group(1) or exception_match.group(2)

    def parse_lines(self, lines: list[str]) -> list[ParsedLogEntry]:
        """解析多行日志"""
        entries = []
        current_entry: ParsedLogEntry | None = None
        stack_lines: list[str] = []

        for line in lines:
            parsed = self.parse_line(line)

            if parsed is None:
                continue

            # 检测堆栈跟踪
            if current_entry and self._is_stack_trace(line):
                stack_lines.append(line)
                continue

            # 保存之前的条目
            if current_entry:
                if stack_lines:
                    current_entry.stack_trace = "\n".join(stack_lines)
                entries.append(current_entry)
                stack_lines = []

            current_entry = parsed

        # 处理最后一个条目
        if current_entry:
            if stack_lines:
                current_entry.stack_trace = "\n".join(stack_lines)
            entries.append(current_entry)

        return entries

    def _is_stack_trace(self, line: str) -> bool:
        """检测是否为堆栈跟踪行"""
        stripped = line.strip()
        if not stripped:
            return False

        # 以 tab 或多个空格开头（检查原始行）
        if line.startswith("\t") or line.startswith("  "):
            return True

        # Java 堆栈跟踪格式：at package.Class.method(File.java:line)
        if stripped.startswith("at ") and re.match(r"^at\s+[a-zA-Z]", stripped):
            return True

        # Caused by
        if stripped.startswith("Caused by:"):
            return True

        # More...
        if stripped.startswith("... ") and stripped.endswith(" more"):
            return True

        return False

    def extract_errors(
        self, lines: list[str], include_warnings: bool = False
    ) -> list[ParsedLogEntry]:
        """提取错误日志"""
        entries = self.parse_lines(lines)

        if include_warnings:
            return [
                e
                for e in entries
                if e.level in (LogLevel.ERROR, LogLevel.FATAL, LogLevel.WARN)
            ]

        return [e for e in entries if e.level in (LogLevel.ERROR, LogLevel.FATAL)]

    def extract_events(
        self, lines: list[str], min_level: LogLevel = LogLevel.INFO
    ) -> list[ParsedLogEntry]:
        """提取事件日志"""
        entries = self.parse_lines(lines)
        level_order = [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARN, LogLevel.ERROR, LogLevel.FATAL]
        min_idx = level_order.index(min_level)

        return [e for e in entries if level_order.index(e.level) >= min_idx]

    def summarize(self, entries: list[ParsedLogEntry]) -> dict[str, Any]:
        """生成日志摘要"""
        total = len(entries)
        if total == 0:
            return {"total": 0}

        # 按级别统计
        by_level: dict[str, int] = {}
        for level in LogLevel:
            by_level[level.value] = sum(1 for e in entries if e.level == level)

        # 按组件统计
        by_component: dict[str, int] = {}
        for entry in entries:
            comp = entry.component or "unknown"
            by_component[comp] = by_component.get(comp, 0) + 1

        # 按错误类型统计
        by_error_pattern: dict[str, int] = {}
        for entry in entries:
            pattern = entry.metadata.get("error_pattern")
            if pattern:
                by_error_pattern[pattern] = by_error_pattern.get(pattern, 0) + 1

        # 按来源统计
        by_source: dict[str, int] = {}
        for entry in entries:
            source = entry.source.value
            by_source[source] = by_source.get(source, 0) + 1

        return {
            "total": total,
            "by_level": by_level,
            "by_component": dict(
                sorted(by_component.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
            "by_error_pattern": dict(
                sorted(by_error_pattern.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
            "by_source": by_source,
            "time_range": {
                "start": min(e.timestamp for e in entries if e.timestamp),
                "end": max(e.timestamp for e in entries if e.timestamp),
            }
            if any(e.timestamp for e in entries)
            else None,
        }

    def detect_anomalies(self, entries: list[ParsedLogEntry]) -> list[dict[str, Any]]:
        """检测异常模式"""
        anomalies = []

        # 检测错误爆发
        error_count = sum(1 for e in entries if e.level in (LogLevel.ERROR, LogLevel.FATAL))
        if error_count > 10:
            anomalies.append({
                "type": "error_burst",
                "severity": "high" if error_count > 50 else "medium",
                "description": f"High error count detected: {error_count} errors",
                "count": error_count,
            })

        # 检测 executor 丢失
        executor_lost = [
            e for e in entries
            if e.metadata.get("error_pattern") == "executor_lost"
        ]
        if len(executor_lost) > 2:
            anomalies.append({
                "type": "executor_instability",
                "severity": "high",
                "description": f"Multiple executor losses: {len(executor_lost)} occurrences",
                "count": len(executor_lost),
            })

        # 检测 OOM
        oom_errors = [
            e for e in entries
            if e.metadata.get("error_pattern") in ("oom_executor", "oom_driver", "gc_overhead")
        ]
        if oom_errors:
            anomalies.append({
                "type": "memory_pressure",
                "severity": "critical",
                "description": f"Memory issues detected: {len(oom_errors)} occurrences",
                "count": len(oom_errors),
            })

        # 检测 shuffle 问题
        shuffle_errors = [
            e for e in entries
            if e.metadata.get("error_pattern") == "shuffle_failed"
        ]
        if len(shuffle_errors) > 3:
            anomalies.append({
                "type": "shuffle_failure",
                "severity": "high",
                "description": f"Multiple shuffle failures: {len(shuffle_errors)} occurrences",
                "count": len(shuffle_errors),
            })

        # 检测网络问题
        network_errors = [
            e for e in entries
            if e.metadata.get("error_pattern") in ("connection_refused", "timeout")
        ]
        if len(network_errors) > 5:
            anomalies.append({
                "type": "network_issues",
                "severity": "medium",
                "description": f"Network issues detected: {len(network_errors)} occurrences",
                "count": len(network_errors),
            })

        return anomalies


# 全局实例
_log_parser: SparkLogParser | None = None


def get_log_parser() -> SparkLogParser:
    """获取全局日志解析器"""
    global _log_parser
    if _log_parser is None:
        _log_parser = SparkLogParser()
    return _log_parser
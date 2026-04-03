"""Log parser 单元测试"""

import pytest
from datetime import datetime

from app.infrastructure.log_parser import (
    SparkLogParser,
    LogLevel,
    LogSource,
    ParsedLogEntry,
    ErrorPattern,
    get_log_parser,
)


@pytest.fixture
def parser():
    """创建解析器实例"""
    return SparkLogParser()


@pytest.fixture
def sample_logs():
    """示例日志"""
    return [
        "24/04/03 10:00:00 INFO SparkContext: Started Spark application app-20260403100000-0001",
        "24/04/03 10:00:01 INFO Driver: Starting driver",
        "24/04/03 10:00:02 INFO Executor: Executor 0 started on host-1",
        "24/04/03 10:00:03 WARN TaskSetManager: Lost task 0.0 in stage 1",
        "24/04/03 10:00:04 ERROR Executor: java.lang.OutOfMemoryError: Java heap space",
        "	at org.apache.spark.memory.MemoryManager.acquireMemory(MemoryManager.java:100)",
        "	at org.apache.spark.executor.Executor.executeTask(Executor.java:200)",
        "24/04/03 10:00:05 INFO BlockManager: Block manager registered",
        "24/04/03 10:00:06 ERROR TaskSetManager: Stage 2 failed",
        "Caused by: org.apache.spark.SparkException: Task failed",
        "24/04/03 10:00:07 FATAL SparkContext: Application failed",
        "24/04/03 10:00:08 INFO SparkContext: Application finished",
    ]


class TestSparkLogParser:
    """SparkLogParser 测试"""

    def test_parse_standard_format(self, parser):
        """测试标准格式解析"""
        line = "24/04/03 10:00:00 INFO SparkContext: Started application"
        entry = parser.parse_line(line)

        assert entry is not None
        assert entry.level == LogLevel.INFO
        assert entry.component == "SparkContext"
        assert "Started application" in entry.message

    def test_parse_with_year_format(self, parser):
        """测试带年份格式解析"""
        line = "2026-04-03 10:00:00,000 ERROR Driver: Test error"
        entry = parser.parse_line(line)

        assert entry is not None
        assert entry.level == LogLevel.ERROR
        assert entry.component == "Driver"

    def test_parse_k8s_format(self, parser):
        """测试 Kubernetes 格式解析"""
        line = "2026-04-03T10:00:00.000Z WARN Executor: Test warning"
        entry = parser.parse_line(line)

        assert entry is not None
        assert entry.level == LogLevel.WARN
        assert entry.component == "Executor"

    def test_parse_timestamp(self, parser):
        """测试时间戳解析"""
        line = "24/04/03 10:00:00 INFO SparkContext: Started"
        entry = parser.parse_line(line)

        assert entry.timestamp is not None
        assert entry.timestamp.month == 4
        assert entry.timestamp.day == 3

    def test_parse_empty_line(self, parser):
        """测试空行解析"""
        entry = parser.parse_line("")
        assert entry is None

        entry = parser.parse_line("   ")
        assert entry is None

    def test_parse_unknown_format(self, parser):
        """测试未知格式解析"""
        line = "Some random log message with ERROR in it"
        entry = parser.parse_line(line)

        assert entry is not None
        assert entry.level == LogLevel.ERROR
        assert entry.message == line

    def test_parse_multiline_logs(self, parser, sample_logs):
        """测试多行日志解析"""
        entries = parser.parse_lines(sample_logs)

        assert len(entries) > 0
        # 堆栈跟踪应该被合并到前一个条目
        oom_entry = next((e for e in entries if "OutOfMemoryError" in e.message), None)
        assert oom_entry is not None
        assert oom_entry.stack_trace is not None
        assert "MemoryManager" in oom_entry.stack_trace

    def test_extract_app_id(self, parser):
        """测试提取 app_id"""
        line = "24/04/03 10:00:00 INFO SparkContext: Started application_20260403100000_0001"
        entry = parser.parse_line(line)

        assert entry.app_id == "application_20260403100000_0001"

    def test_extract_executor_id(self, parser):
        """测试提取 executor_id"""
        line = "24/04/03 10:00:00 INFO Executor: Executor 5 started"
        entry = parser.parse_line(line)

        assert entry.executor_id == "5"
        assert entry.source == LogSource.EXECUTOR

    def test_extract_stage_id(self, parser):
        """测试提取 stage_id"""
        line = "24/04/03 10:00:00 INFO TaskSetManager: Starting stage 3"
        entry = parser.parse_line(line)

        assert entry.stage_id == 3

    def test_detect_oom_pattern(self, parser):
        """测试检测 OOM 模式"""
        line = "24/04/03 10:00:00 ERROR Executor: java.lang.OutOfMemoryError: Java heap space"
        entry = parser.parse_line(line)

        assert entry.metadata.get("error_pattern") == "oom_executor"
        assert entry.metadata.get("error_severity") == "critical"
        assert entry.exception_type == "java.lang.OutOfMemoryError"

    def test_detect_executor_lost_pattern(self, parser):
        """测试检测 executor 丢失模式"""
        line = "24/04/03 10:00:00 WARN TaskSetManager: ExecutorLostFailure executor 3"
        entry = parser.parse_line(line)

        assert entry.metadata.get("error_pattern") == "executor_lost"

    def test_detect_stage_failure_pattern(self, parser):
        """测试检测 stage 失败模式"""
        line = "24/04/03 10:00:00 ERROR DAGScheduler: Stage 5 failed"
        entry = parser.parse_line(line)

        assert entry.metadata.get("error_pattern") == "stage_failure"

    def test_detect_shuffle_failed_pattern(self, parser):
        """测试检测 shuffle 失败模式"""
        line = "24/04/03 10:00:00 ERROR Executor: FetchFailedException: shuffle failed"
        entry = parser.parse_line(line)

        assert entry.metadata.get("error_pattern") == "shuffle_failed"

    def test_detect_gc_overhead_pattern(self, parser):
        """测试检测 GC overhead 模式"""
        line = "24/04/03 10:00:00 ERROR Executor: java.lang.OutOfMemoryError: GC overhead limit exceeded"
        entry = parser.parse_line(line)

        assert entry.metadata.get("error_pattern") == "gc_overhead"

    def test_detect_connection_refused_pattern(self, parser):
        """测试检测连接拒绝模式"""
        line = "24/04/03 10:00:00 ERROR NettyRpc: Connection refused to 192.168.1.10:7077"
        entry = parser.parse_line(line)

        assert entry.metadata.get("error_pattern") == "connection_refused"

    def test_extract_errors(self, parser, sample_logs):
        """测试提取错误日志"""
        errors = parser.extract_errors(sample_logs)

        assert len(errors) >= 3  # OOM, stage failure, FATAL
        for e in errors:
            assert e.level in (LogLevel.ERROR, LogLevel.FATAL)

    def test_extract_errors_include_warnings(self, parser, sample_logs):
        """测试提取错误日志（包含警告）"""
        errors = parser.extract_errors(sample_logs, include_warnings=True)

        assert len(errors) >= 4  # WARN + ERROR + FATAL
        for e in errors:
            assert e.level in (LogLevel.ERROR, LogLevel.FATAL, LogLevel.WARN)

    def test_extract_events(self, parser, sample_logs):
        """测试提取事件日志"""
        events = parser.extract_events(sample_logs, min_level=LogLevel.WARN)

        assert len(events) >= 4
        for e in events:
            assert e.level in (LogLevel.WARN, LogLevel.ERROR, LogLevel.FATAL)

    def test_summarize(self, parser, sample_logs):
        """测试日志摘要"""
        entries = parser.parse_lines(sample_logs)
        summary = parser.summarize(entries)

        assert summary["total"] > 0
        assert "by_level" in summary
        assert summary["by_level"]["INFO"] > 0
        assert summary["by_level"]["ERROR"] > 0
        assert "by_component" in summary
        assert "by_error_pattern" in summary

    def test_detect_anomalies(self, parser):
        """测试异常检测"""
        # 创建模拟大量错误
        logs = []
        for i in range(20):
            logs.append(f"24/04/03 10:00:{i:02d} ERROR Executor: java.lang.OutOfMemoryError")

        entries = parser.parse_lines(logs)
        anomalies = parser.detect_anomalies(entries)

        # 应该检测到错误爆发和内存压力
        assert len(anomalies) >= 2
        error_burst = next((a for a in anomalies if a["type"] == "error_burst"), None)
        memory_pressure = next((a for a in anomalies if a["type"] == "memory_pressure"), None)

        assert error_burst is not None
        assert memory_pressure is not None
        assert memory_pressure["severity"] == "critical"

    def test_custom_error_pattern(self):
        """测试自定义错误模式"""
        custom_pattern = ErrorPattern(
            name="custom_error",
            pattern=r"CUSTOM_ERROR_CODE_\d+",
            category="custom",
            severity="medium",
            description="Custom error pattern",
        )

        parser = SparkLogParser(custom_patterns=[custom_pattern])
        line = "24/04/03 10:00:00 ERROR App: CUSTOM_ERROR_CODE_123 occurred"
        entry = parser.parse_line(line)

        assert entry.metadata.get("error_pattern") == "custom_error"

    def test_driver_source_detection(self, parser):
        """测试 Driver 来源检测"""
        line = "24/04/03 10:00:00 INFO Driver: Starting driver process"
        entry = parser.parse_line(line)

        assert entry.source == LogSource.DRIVER

    def test_executor_source_detection(self, parser):
        """测试 Executor 来源检测"""
        line = "24/04/03 10:00:00 INFO Executor: Executor started"
        entry = parser.parse_line(line)

        assert entry.source == LogSource.EXECUTOR

    def test_stack_trace_merge(self, parser):
        """测试堆栈跟踪合并"""
        logs = [
            "24/04/03 10:00:00 ERROR Executor: Exception occurred",
            "	at org.apache.spark.Executor.run(Executor.java:100)",
            "	at java.lang.Thread.run(Thread.java:50)",
            "Caused by: java.io.IOException: Disk full",
            "24/04/03 10:00:01 INFO Executor: Continuing",
        ]

        entries = parser.parse_lines(logs)

        # 应该有 2 个条目（ERROR 和 INFO）
        assert len(entries) == 2

        # 第一个条目应该有堆栈跟踪
        assert entries[0].stack_trace is not None
        assert "Executor.run" in entries[0].stack_trace
        assert "Caused by" in entries[0].stack_trace

    def test_error_suggestions(self, parser):
        """测试错误建议"""
        line = "24/04/03 10:00:00 ERROR Executor: java.lang.OutOfMemoryError: Java heap space"
        entry = parser.parse_line(line)

        suggestions = entry.metadata.get("error_suggestions")
        assert suggestions is not None
        assert len(suggestions) > 0
        assert any("memory" in s.lower() for s in suggestions)

    def test_get_log_parser_singleton(self):
        """测试全局实例"""
        parser1 = get_log_parser()
        parser2 = get_log_parser()

        assert parser1 is parser2


class TestLogLevel:
    """LogLevel 测试"""

    def test_level_values(self):
        """测试级别值"""
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARN.value == "WARN"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.FATAL.value == "FATAL"


class TestParsedLogEntry:
    """ParsedLogEntry 测试"""

    def test_entry_creation(self):
        """测试条目创建"""
        entry = ParsedLogEntry(
            level=LogLevel.ERROR,
            component="Executor",
            message="Test error",
            raw_line="raw",
        )

        assert entry.level == LogLevel.ERROR
        assert entry.component == "Executor"
        assert entry.message == "Test error"
        assert entry.metadata == {}

    def test_entry_with_metadata(self):
        """测试带元数据的条目"""
        entry = ParsedLogEntry(
            level=LogLevel.ERROR,
            message="Test",
            metadata={"key": "value"},
        )

        assert entry.metadata["key"] == "value"

    def test_entry_with_exception(self):
        """测试带异常信息的条目"""
        entry = ParsedLogEntry(
            level=LogLevel.ERROR,
            message="Test",
            exception_type="java.lang.OutOfMemoryError",
            exception_message="Java heap space",
        )

        assert entry.exception_type == "java.lang.OutOfMemoryError"
        assert entry.exception_message == "Java heap space"
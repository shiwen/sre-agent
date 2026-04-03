"""Log Parser 单元测试"""

import pytest

from app.agent.analysis.log_parser import (
    LogEntry,
    LogEntryType,
    ParsedLogResult,
    SparkLogParser,
)


@pytest.fixture
def parser() -> SparkLogParser:
    """创建解析器实例"""
    return SparkLogParser()


@pytest.fixture
def sample_driver_logs() -> str:
    """示例 Driver 日志"""
    return """
2026-04-03 10:00:00 INFO SparkContext: Started Spark application app-001
2026-04-03 10:00:01 INFO Driver: Starting driver on host-1
2026-04-03 10:00:02 INFO Executor: Executor 0 started on host-2
2026-04-03 10:00:03 INFO TaskSetManager: Starting stage 0 (read data)
2026-04-03 10:00:04 INFO TaskSetManager: Starting task 0 in stage 0
2026-04-03 10:00:05 INFO BlockManager: Block registered
2026-04-03 10:00:06 WARN MemoryStore: Memory pressure high
2026-04-03 10:00:07 ERROR Executor: java.lang.OutOfMemoryError: Java heap space
2026-04-03 10:00:08 INFO TaskSetManager: Finished task 0 in stage 0
2026-04-03 10:00:09 ERROR ExecutorLostFailure: Executor 0 lost
2026-04-03 10:00:10 ERROR FetchFailedException: Failed to fetch shuffle block
2026-04-03 10:00:11 INFO SparkContext: Application finished
"""


class TestLogParser:
    """Log Parser 测试"""

    def test_parse_line_standard_format(self, parser: SparkLogParser) -> None:
        """测试标准格式解析"""
        line = "2026-04-03 10:00:00 INFO SparkContext: Started Spark application"
        entry = parser._parse_line(line, "driver")

        assert entry is not None
        assert entry.level == LogEntryType.INFO
        assert entry.source == "SparkContext"
        assert "Started" in entry.message

    def test_parse_line_error(self, parser: SparkLogParser) -> None:
        """测试错误日志解析"""
        line = "2026-04-03 10:00:07 ERROR Executor: java.lang.OutOfMemoryError"
        entry = parser._parse_line(line, "driver")

        assert entry is not None
        assert entry.level == LogEntryType.ERROR
        assert entry.source == "Executor"

    def test_parse_line_no_timestamp(self, parser: SparkLogParser) -> None:
        """测试无时间戳格式"""
        line = "INFO SparkContext: Some message"
        entry = parser._parse_line(line, "driver")

        assert entry is not None
        assert entry.level == LogEntryType.INFO
        assert entry.timestamp is None

    def test_parse_log_text(self, parser: SparkLogParser, sample_driver_logs: str) -> None:
        """测试日志文本解析"""
        result = parser._parse_log_text("app-001", sample_driver_logs, "driver")

        assert result.app_id == "app-001"
        assert result.total_lines > 0
        assert len(result.entries) > 0
        assert len(result.errors) == 3  # OOM, ExecutorLost, FetchFailed
        assert len(result.warnings) == 1  # Memory pressure

    def test_extract_stage_events(self, parser: SparkLogParser) -> None:
        """测试 Stage 事件提取"""
        logs = "INFO TaskSetManager: Starting stage 0 (map)\nINFO TaskSetManager: Stage 0 finished"
        result = parser._parse_log_text("app-001", logs, "driver")

        assert 0 in result.stages
        assert result.stages[0]["status"] == "completed"

    def test_extract_executor_events(self, parser: SparkLogParser) -> None:
        """测试 Executor 事件提取"""
        logs = "INFO Executor: Executor 0 added\nINFO Executor: Executor 0 lost"
        result = parser._parse_log_text("app-001", logs, "driver")

        assert "0" in result.executors
        assert result.executors["0"]["status"] == "removed"

    def test_classify_errors_oom(self, parser: SparkLogParser) -> None:
        """测试 OOM 错误分类"""
        logs = "ERROR Executor: java.lang.OutOfMemoryError: Java heap space"
        result = parser._parse_log_text("app-001", logs, "driver")

        classified = parser.classify_errors(result)

        assert "oom_executor" in classified
        assert len(classified["oom_executor"]) == 1

    def test_classify_errors_shuffle(self, parser: SparkLogParser) -> None:
        """测试 Shuffle 错误分类"""
        logs = "ERROR TaskSetManager: FetchFailedException: shuffle block"
        result = parser._parse_log_text("app-001", logs, "driver")

        classified = parser.classify_errors(result)

        assert "shuffle_failure" in classified

    def test_classify_errors_executor_lost(self, parser: SparkLogParser) -> None:
        """测试 Executor 丢失分类"""
        logs = "ERROR Driver: ExecutorLostFailure: Executor 1 lost"
        result = parser._parse_log_text("app-001", logs, "driver")

        classified = parser.classify_errors(result)

        assert "executor_lost" in classified

    def test_get_error_summary(self, parser: SparkLogParser, sample_driver_logs: str) -> None:
        """测试错误摘要"""
        result = parser._parse_log_text("app-001", sample_driver_logs, "driver")
        summary = parser.get_error_summary(result)

        assert summary["app_id"] == "app-001"
        assert summary["total_errors"] == 3
        assert summary["total_warnings"] == 1
        assert summary["most_severe"] == "oom_executor"

    def test_analyze_root_cause(self, parser: SparkLogParser) -> None:
        """测试根因分析"""
        logs = """
ERROR Executor: java.lang.OutOfMemoryError: Java heap space
ERROR TaskSetManager: FetchFailedException
"""
        result = parser._parse_log_text("app-001", logs, "driver")
        classified = parser.classify_errors(result)
        root_cause = parser._analyze_root_cause(classified, result)

        assert root_cause["primary"] is not None
        assert root_cause["primary"]["type"] == "oom_executor"
        assert root_cause["primary"]["confidence"] > 0.8

    def test_generate_recommendations_oom(self, parser: SparkLogParser) -> None:
        """测试 OOM 建议"""
        classified = {"oom_executor": [LogEntry(level=LogEntryType.ERROR, message="OOM")]}
        root_cause = {
            "primary": {"type": "oom_executor", "cause": "Executor 内存不足", "confidence": 0.85, "count": 1},
            "secondary": [],
        }

        recommendations = parser._generate_recommendations(root_cause, classified)

        assert len(recommendations) > 0
        assert recommendations[0]["action"] == "增加 spark.executor.memory"
        assert recommendations[0]["priority"] == 1

    def test_analyze_stages(self, parser: SparkLogParser) -> None:
        """测试 Stage 分析"""
        result = ParsedLogResult(
            app_id="app-001",
            total_lines=10,
            stages={
                0: {"name": "Stage 0", "status": "completed", "failed_tasks": 0, "duration_ms": 1000},
                1: {"name": "Stage 1", "status": "failed", "failed_tasks": 5, "duration_ms": 600000},
                2: {"name": "Stage 2", "status": "completed", "shuffle_read": 2000000000, "duration_ms": 1000},
            },
        )

        analysis = parser._analyze_stages(result, None)

        assert analysis["total_stages"] == 3
        assert len(analysis["failed_stages"]) == 1
        assert len(analysis["slow_stages"]) == 1  # Stage 1 > 5min
        assert len(analysis["shuffle_heavy_stages"]) == 1  # Stage 2 > 1GB

    def test_generate_diagnostic_report(self, parser: SparkLogParser, sample_driver_logs: str) -> None:
        """测试诊断报告生成"""
        result = parser._parse_log_text("app-001", sample_driver_logs, "driver")
        report = parser.generate_diagnostic_report(result)

        assert report["app_id"] == "app-001"
        assert report["root_cause"]["primary"] is not None
        assert len(report["recommendations"]) > 0


class TestLogEntryType:
    """LogEntryType 测试"""

    def test_enum_values(self) -> None:
        """测试枚举值"""
        assert LogEntryType.INFO == "INFO"
        assert LogEntryType.WARN == "WARN"
        assert LogEntryType.ERROR == "ERROR"
        assert LogEntryType.DEBUG == "DEBUG"


class TestParsedLogResult:
    """ParsedLogResult 测试"""

    def test_model_creation(self) -> None:
        """测试模型创建"""
        result = ParsedLogResult(
            app_id="test-app",
            total_lines=100,
        )

        assert result.app_id == "test-app"
        assert result.entries == []
        assert result.errors == []
        assert result.warnings == []
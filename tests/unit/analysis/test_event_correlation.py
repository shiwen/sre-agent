"""Event Correlation Engine 单元测试"""

import pytest
from datetime import datetime, timedelta

from app.agent.analysis.event_correlation import (
    CorrelatedEvent,
    CorrelationLevel,
    CorrelationResult,
    EventCorrelationEngine,
    EventType,
    EventTimeline,
)
from app.agent.analysis.log_parser import (
    LogEntry,
    LogEntryType,
    ParsedLogResult,
)


@pytest.fixture
def engine() -> EventCorrelationEngine:
    """创建关联引擎实例"""
    return EventCorrelationEngine()


def create_timeline_with_cascade() -> EventTimeline:
    """创建包含级联故障的时间线"""
    base_time = datetime(2026, 4, 3, 10, 0, 0)

    events = [
        CorrelatedEvent(
            event_type=EventType.APP_START,
            timestamp=base_time,
            source="driver",
            message="Started Spark application",
        ),
        CorrelatedEvent(
            event_type=EventType.EXECUTOR_ADD,
            timestamp=base_time + timedelta(seconds=5),
            source="driver",
            message="Executor 0 started",
        ),
        CorrelatedEvent(
            event_type=EventType.STAGE_START,
            timestamp=base_time + timedelta(seconds=10),
            source="driver",
            message="Starting stage 0",
        ),
        CorrelatedEvent(
            event_type=EventType.OOM_EXECUTOR,
            timestamp=base_time + timedelta(seconds=30),
            source="executor-0",
            message="java.lang.OutOfMemoryError: Java heap space",
        ),
        CorrelatedEvent(
            event_type=EventType.STAGE_FAIL,
            timestamp=base_time + timedelta(seconds=35),
            source="driver",
            message="Stage 0 failed",
        ),
        CorrelatedEvent(
            event_type=EventType.APP_FAIL,
            timestamp=base_time + timedelta(seconds=40),
            source="driver",
            message="Application failed",
        ),
    ]

    return EventTimeline(
        app_id="app-cascade-test",
        start_time=base_time,
        end_time=base_time + timedelta(seconds=40),
        events=events,
    )


def create_parsed_result_with_errors() -> ParsedLogResult:
    """创建包含错误日志的解析结果"""
    base_time = datetime(2026, 4, 3, 10, 0, 0)

    entries = [
        LogEntry(
            timestamp=base_time,
            level=LogEntryType.INFO,
            source="SparkContext",
            message="Started Spark application app-001",
        ),
        LogEntry(
            timestamp=base_time + timedelta(seconds=10),
            level=LogEntryType.INFO,
            source="Executor",
            message="Executor 0 started on host-1",
        ),
        LogEntry(
            timestamp=base_time + timedelta(seconds=30),
            level=LogEntryType.ERROR,
            source="Executor",
            message="java.lang.OutOfMemoryError: Java heap space",
        ),
        LogEntry(
            timestamp=base_time + timedelta(seconds=35),
            level=LogEntryType.ERROR,
            source="TaskSetManager",
            message="Stage 0 failed due to OOM",
        ),
        LogEntry(
            timestamp=base_time + timedelta(seconds=40),
            level=LogEntryType.ERROR,
            source="SparkContext",
            message="Application failed",
        ),
    ]

    return ParsedLogResult(
        app_id="app-001",
        total_lines=5,
        entries=entries,
        errors=entries[2:],
        warnings=[],
    )


class TestEventType:
    """EventType 测试"""

    def test_enum_values(self) -> None:
        """测试枚举值"""
        assert EventType.APP_START == "app_start"
        assert EventType.OOM_EXECUTOR == "oom_executor"
        assert EventType.STAGE_FAIL == "stage_fail"


class TestCorrelatedEvent:
    """CorrelatedEvent 测试"""

    def test_model_creation(self) -> None:
        """测试模型创建"""
        event = CorrelatedEvent(
            event_type=EventType.OOM_EXECUTOR,
            timestamp=datetime.now(),
            source="executor-0",
            message="OOM occurred",
        )

        assert event.event_type == EventType.OOM_EXECUTOR
        assert event.related_events == []


class TestEventTimeline:
    """EventTimeline 测试"""

    def test_timeline_creation(self) -> None:
        """测试时间线创建"""
        timeline = EventTimeline(
            app_id="test-app",
            events=[],
        )

        assert timeline.app_id == "test-app"
        assert timeline.events == []


class TestEventCorrelationEngine:
    """EventCorrelationEngine 测试"""

    def test_identify_event_type_app_start(self, engine: EventCorrelationEngine) -> None:
        """测试应用启动事件识别"""
        entry = LogEntry(
            level=LogEntryType.INFO,
            source="SparkContext",
            message="Started Spark application app-001",
        )

        event_type = engine._identify_event_type(entry)
        assert event_type == EventType.APP_START

    def test_identify_event_type_oom_executor(self, engine: EventCorrelationEngine) -> None:
        """测试 Executor OOM 识别"""
        entry = LogEntry(
            level=LogEntryType.ERROR,
            source="Executor",
            message="java.lang.OutOfMemoryError: Java heap space",
        )

        event_type = engine._identify_event_type(entry)
        assert event_type == EventType.OOM_EXECUTOR

    def test_identify_event_type_executor_lost(self, engine: EventCorrelationEngine) -> None:
        """测试 Executor 丢失识别"""
        entry = LogEntry(
            level=LogEntryType.ERROR,
            source="Driver",
            message="ExecutorLostFailure: Executor 1 lost",
        )

        event_type = engine._identify_event_type(entry)
        assert event_type == EventType.EXECUTOR_LOST

    def test_identify_event_type_shuffle_failure(self, engine: EventCorrelationEngine) -> None:
        """测试 Shuffle 失败识别"""
        entry = LogEntry(
            level=LogEntryType.ERROR,
            source="TaskSetManager",
            message="FetchFailedException: Failed to fetch shuffle block",
        )

        event_type = engine._identify_event_type(entry)
        assert event_type == EventType.SHUFFLE_FAILURE

    def test_convert_entry_to_event(self, engine: EventCorrelationEngine) -> None:
        """测试日志条目转换"""
        entry = LogEntry(
            timestamp=datetime.now(),
            level=LogEntryType.ERROR,
            source="Executor",
            message="Executor 0 lost",
        )

        event = engine._convert_entry_to_event(entry)

        assert event is not None
        assert event.event_type == EventType.EXECUTOR_LOST
        assert event.source == "Executor"

    def test_build_timeline(self, engine: EventCorrelationEngine) -> None:
        """测试时间线构建"""
        result = create_parsed_result_with_errors()
        timeline = engine._build_timeline("app-001", result)

        assert timeline.app_id == "app-001"
        assert len(timeline.events) > 0
        assert timeline.start_time is not None
        assert timeline.end_time is not None

    def test_identify_temporal_patterns_executor_instability(
        self, engine: EventCorrelationEngine
    ) -> None:
        """测试 Executor 不稳定模式识别"""
        base_time = datetime(2026, 4, 3, 10, 0, 0)

        timeline = EventTimeline(
            app_id="test-app",
            events=[
                CorrelatedEvent(
                    event_type=EventType.EXECUTOR_LOST,
                    timestamp=base_time,
                    source="driver",
                    message="Executor 0 lost",
                ),
                CorrelatedEvent(
                    event_type=EventType.EXECUTOR_LOST,
                    timestamp=base_time + timedelta(seconds=20),
                    source="driver",
                    message="Executor 1 lost",
                ),
                CorrelatedEvent(
                    event_type=EventType.EXECUTOR_LOST,
                    timestamp=base_time + timedelta(seconds=30),
                    source="driver",
                    message="Executor 2 lost",
                ),
            ],
        )

        patterns = engine._identify_temporal_patterns(timeline)

        assert len(patterns) > 0
        assert patterns[0]["type"] == "executor_instability"

    def test_identify_root_event(self, engine: EventCorrelationEngine) -> None:
        """测试根事件识别"""
        timeline = create_timeline_with_cascade()

        cascades = [
            {
                "trigger": "oom_executor",
                "trigger_time": timeline.events[3].timestamp,
                "chain_length": 2,
                "chain_events": ["oom_executor", "stage_fail"],
            }
        ]

        root = engine._identify_root_event(timeline, cascades)

        assert root is not None
        assert root.event_type == EventType.OOM_EXECUTOR

    def test_infer_propagation_path(self, engine: EventCorrelationEngine) -> None:
        """测试传播路径推断"""
        timeline = create_timeline_with_cascade()

        root_event = timeline.events[3]  # OOM Executor
        path = engine._infer_propagation_path(timeline, root_event)

        assert EventType.OOM_EXECUTOR in path

    def test_generate_correlation_report(self, engine: EventCorrelationEngine) -> None:
        """测试关联报告生成"""
        timeline = create_timeline_with_cascade()

        result = CorrelationResult(
            app_id="app-test",
            timeline=timeline,
            cascade_failures=[],
            temporal_patterns=[],
            root_event=timeline.events[3],
            propagation_path=[EventType.OOM_EXECUTOR, EventType.STAGE_FAIL],
        )

        report = engine.generate_correlation_report(result)

        assert report["app_id"] == "app-test"
        assert report["root_event"]["type"] == "oom_executor"
        assert "oom_executor" in report["propagation_path"]

    def test_generate_correlation_recommendations(
        self, engine: EventCorrelationEngine
    ) -> None:
        """测试建议生成"""
        timeline = create_timeline_with_cascade()

        result = CorrelationResult(
            app_id="app-test",
            timeline=timeline,
            cascade_failures=[
                {
                    "trigger": "oom_executor",
                    "chain_length": 2,
                    "chain_events": ["oom_executor", "stage_fail"],
                }
            ],
            temporal_patterns=[],
            root_event=timeline.events[3],
            propagation_path=[EventType.OOM_EXECUTOR, EventType.STAGE_FAIL],
        )

        recommendations = engine._generate_correlation_recommendations(result)

        assert len(recommendations) > 0
        assert recommendations[0]["action"] == "增加 Executor 内存配置"
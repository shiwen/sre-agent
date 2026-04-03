"""事件关联引擎

将多个来源的日志事件进行关联，识别故障传播路径和时序模式。
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from structlog import get_logger

from app.agent.analysis.log_parser import (
    LogEntry,
    ParsedLogResult,
    SparkLogParser,
    get_log_parser,
)
from app.infrastructure.history_client import (
    SparkHistoryApp,
    SparkHistoryStage,
    SparkHistoryExecutor,
    get_history_client,
)

logger = get_logger()


class EventType(str, Enum):
    """事件类型"""
    # 应用生命周期
    APP_START = "app_start"
    APP_END = "app_end"
    APP_FAIL = "app_fail"

    # Stage 事件
    STAGE_START = "stage_start"
    STAGE_END = "stage_end"
    STAGE_FAIL = "stage_fail"

    # Task 事件
    TASK_START = "task_start"
    TASK_END = "task_end"
    TASK_FAIL = "task_fail"

    # Executor 事件
    EXECUTOR_ADD = "executor_add"
    EXECUTOR_REMOVE = "executor_remove"
    EXECUTOR_LOST = "executor_lost"

    # 错误事件
    OOM_DRIVER = "oom_driver"
    OOM_EXECUTOR = "oom_executor"
    SHUFFLE_FAILURE = "shuffle_failure"
    NETWORK_ERROR = "network_error"
    CLASS_NOT_FOUND = "class_not_found"

    # Job 事件
    JOB_START = "job_start"
    JOB_END = "job_end"
    JOB_FAIL = "job_fail"


class CorrelationLevel(str, Enum):
    """关联置信度"""
    HIGH = "high"  # 直接因果关系
    MEDIUM = "medium"  # 强时序关联
    LOW = "low"  # 弱关联


class CorrelatedEvent(BaseModel):
    """关联后的事件"""
    event_type: EventType
    timestamp: datetime | None = None
    source: str  # driver, executor-0, etc.
    message: str
    context: dict[str, Any] = Field(default_factory=dict)
    related_events: list[str] = Field(default_factory=list)  # 关联事件 ID


class EventTimeline(BaseModel):
    """事件时间线"""
    app_id: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    events: list[CorrelatedEvent] = Field(default_factory=list)
    failure_chain: list[str] = Field(default_factory=list)  # 失败链事件 ID


class CorrelationResult(BaseModel):
    """关联分析结果"""
    app_id: str
    timeline: EventTimeline
    cascade_failures: list[dict[str, Any]] = Field(default_factory=list)
    temporal_patterns: list[dict[str, Any]] = Field(default_factory=list)
    root_event: CorrelatedEvent | None = None
    propagation_path: list[EventType] = Field(default_factory=list)


# 事件关联规则定义
CORRELATION_RULES = [
    {
        "name": "executor_oom_to_stage_fail",
        "trigger": EventType.OOM_EXECUTOR,
        "followed_by": EventType.STAGE_FAIL,
        "within_seconds": 60,
        "confidence": CorrelationLevel.HIGH,
        "description": "Executor OOM 导致 Stage 失败",
    },
    {
        "name": "executor_lost_to_shuffle_fail",
        "trigger": EventType.EXECUTOR_LOST,
        "followed_by": EventType.SHUFFLE_FAILURE,
        "within_seconds": 30,
        "confidence": CorrelationLevel.HIGH,
        "description": "Executor 丢失导致 Shuffle 失败",
    },
    {
        "name": "shuffle_fail_to_stage_fail",
        "trigger": EventType.SHUFFLE_FAILURE,
        "followed_by": EventType.STAGE_FAIL,
        "within_seconds": 30,
        "confidence": CorrelationLevel.HIGH,
        "description": "Shuffle 失败导致 Stage 失败",
    },
    {
        "name": "stage_fail_to_app_fail",
        "trigger": EventType.STAGE_FAIL,
        "followed_by": EventType.APP_FAIL,
        "within_seconds": 60,
        "confidence": CorrelationLevel.MEDIUM,
        "description": "Stage 失败导致应用失败",
    },
    {
        "name": "executor_add_to_executor_lost",
        "trigger": EventType.EXECUTOR_ADD,
        "followed_by": EventType.EXECUTOR_LOST,
        "within_seconds": 300,
        "confidence": CorrelationLevel.LOW,
        "description": "新 Executor 不稳定（快速丢失）",
    },
]

# 故障传播路径模板
FAILURE_PROPAGATION_PATHS = [
    [EventType.OOM_EXECUTOR, EventType.STAGE_FAIL, EventType.APP_FAIL],
    [EventType.EXECUTOR_LOST, EventType.SHUFFLE_FAILURE, EventType.STAGE_FAIL, EventType.APP_FAIL],
    [EventType.OOM_DRIVER, EventType.APP_FAIL],
    [EventType.NETWORK_ERROR, EventType.SHUFFLE_FAILURE, EventType.STAGE_FAIL],
]


class EventCorrelationEngine:
    """事件关联引擎"""

    def __init__(self) -> None:
        self._log_parser = get_log_parser()
        self._history_client = get_history_client()

    async def correlate_application_events(
        self,
        app_id: str,
        parsed_result: ParsedLogResult | None = None,
    ) -> CorrelationResult:
        """关联应用事件"""
        logger.info("correlate_events_start", app_id=app_id)

        # 如果没有解析结果，先解析日志
        if parsed_result is None:
            parsed_result = await self._log_parser.parse_application_logs(
                app_id, include_executor_logs=True
            )

        # 构建时间线
        timeline = self._build_timeline(app_id, parsed_result)

        # 应用关联规则
        self._apply_correlation_rules(timeline)

        # 识别级联故障
        cascade_failures = self._identify_cascade_failures(timeline)

        # 识别时序模式
        temporal_patterns = self._identify_temporal_patterns(timeline)

        # 确定根事件
        root_event = self._identify_root_event(timeline, cascade_failures)

        # 推断传播路径
        propagation_path = self._infer_propagation_path(timeline, root_event)

        result = CorrelationResult(
            app_id=app_id,
            timeline=timeline,
            cascade_failures=cascade_failures,
            temporal_patterns=temporal_patterns,
            root_event=root_event,
            propagation_path=propagation_path,
        )

        logger.info(
            "correlate_events_done",
            app_id=app_id,
            events=len(timeline.events),
            cascades=len(cascade_failures),
        )

        return result

    def _build_timeline(
        self,
        app_id: str,
        parsed_result: ParsedLogResult,
    ) -> EventTimeline:
        """构建事件时间线"""
        timeline = EventTimeline(app_id=app_id)

        # 转换日志条目为事件
        for entry in parsed_result.entries:
            event = self._convert_entry_to_event(entry)
            if event:
                timeline.events.append(event)

        # 按时间排序
        timeline.events.sort(key=lambda e: e.timestamp or datetime.min)

        # 设置时间线边界
        if timeline.events:
            timeline.start_time = timeline.events[0].timestamp
            timeline.end_time = timeline.events[-1].timestamp

        return timeline

    def _convert_entry_to_event(
        self,
        entry: LogEntry,
    ) -> CorrelatedEvent | None:
        """将日志条目转换为事件"""
        # 根据日志内容识别事件类型
        event_type = self._identify_event_type(entry)
        if event_type is None:
            return None

        return CorrelatedEvent(
            event_type=event_type,
            timestamp=entry.timestamp,
            source=entry.source or "unknown",
            message=entry.message,
            context={
                "level": entry.level.value,
                "raw_line": entry.raw_line,
            },
        )

    def _identify_event_type(self, entry: LogEntry) -> EventType | None:
        """识别事件类型"""
        message = entry.message.lower()

        # 应用事件
        if "started spark application" in message:
            return EventType.APP_START
        if "application finished" in message:
            return EventType.APP_END
        if "application failed" in message or (
            entry.level.value == "ERROR" and "application" in message
        ):
            return EventType.APP_FAIL

        # Stage 事件
        if "starting stage" in message:
            return EventType.STAGE_START
        if "stage finished" in message or "stage completed" in message:
            return EventType.STAGE_END
        if "stage failed" in message or (
            entry.level.value == "ERROR" and "stage" in message and "failed" in message
        ):
            return EventType.STAGE_FAIL

        # Executor 事件 - 先检查 OOM（可能不包含 executor 关键字）
        if "outofmemoryerror" in message or ("oom" in message and "heap" in message):
            if "driver" in message:
                return EventType.OOM_DRIVER
            return EventType.OOM_EXECUTOR

        if "executor" in message:
            if "added" in message or "started" in message:
                return EventType.EXECUTOR_ADD
            if "removed" in message:
                return EventType.EXECUTOR_REMOVE
            if "lost" in message or "executorlostfailure" in message:
                return EventType.EXECUTOR_LOST

        # Shuffle 失败
        if "fetchfailedexception" in message or "shuffle" in message and "failed" in message:
            return EventType.SHUFFLE_FAILURE

        # 网络错误
        if "connection refused" in message or "connection timeout" in message:
            return EventType.NETWORK_ERROR

        # 类未找到
        if "classnotfoundexception" in message or "noclassdeffounderror" in message:
            return EventType.CLASS_NOT_FOUND

        # Task 事件
        if "starting task" in message:
            return EventType.TASK_START
        if "finished task" in message:
            return EventType.TASK_END
        if "task failed" in message:
            return EventType.TASK_FAIL

        # Job 事件
        if "starting job" in message:
            return EventType.JOB_START
        if "job finished" in message:
            return EventType.JOB_END
        if "job failed" in message:
            return EventType.JOB_FAIL

        return None

    def _apply_correlation_rules(self, timeline: EventTimeline) -> None:
        """应用关联规则"""
        for rule in CORRELATION_RULES:
            trigger_type = rule["trigger"]
            followed_by_type = rule["followed_by"]
            within_seconds = rule["within_seconds"]

            # 找触发事件
            for i, event in enumerate(timeline.events):
                if event.event_type != trigger_type:
                    continue

                trigger_time = event.timestamp or datetime.min

                # 找后续事件
                for j, later_event in enumerate(timeline.events[i + 1:], start=i + 1):
                    if later_event.event_type != followed_by_type:
                        continue

                    later_time = later_event.timestamp or datetime.min
                    delta = (later_time - trigger_time).total_seconds()

                    if delta <= within_seconds:
                        # 建立关联
                        event.related_events.append(f"{later_event.event_type.value}@{j}")
                        logger.debug(
                            "correlation_found",
                            rule=rule["name"],
                            trigger=event.event_type.value,
                            followed_by=later_event.event_type.value,
                            delta_seconds=delta,
                        )

    def _identify_cascade_failures(
        self,
        timeline: EventTimeline,
    ) -> list[dict[str, Any]]:
        """识别级联故障"""
        cascades = []

        # 找失败链起点（有关联的错误事件）
        for event in timeline.events:
            if event.event_type not in [
                EventType.OOM_EXECUTOR,
                EventType.OOM_DRIVER,
                EventType.EXECUTOR_LOST,
                EventType.SHUFFLE_FAILURE,
                EventType.NETWORK_ERROR,
            ]:
                continue

            if not event.related_events:
                continue

            # 构建级联链
            chain = [event]
            current = event

            while current.related_events:
                # 找第一个关联的失败事件
                for ref in current.related_events:
                    event_type_str, idx_str = ref.split("@")
                    idx = int(idx_str)
                    if idx < len(timeline.events):
                        next_event = timeline.events[idx]
                        if next_event.event_type in [
                            EventType.STAGE_FAIL,
                            EventType.APP_FAIL,
                            EventType.SHUFFLE_FAILURE,
                            EventType.EXECUTOR_LOST,
                        ]:
                            chain.append(next_event)
                            current = next_event
                            break
                else:
                    break

            if len(chain) > 1:
                cascades.append({
                    "trigger": chain[0].event_type.value,
                    "trigger_time": chain[0].timestamp,
                    "trigger_message": chain[0].message[:100],
                    "chain_length": len(chain),
                    "chain_events": [e.event_type.value for e in chain],
                    "end_event": chain[-1].event_type.value,
                })

        return cascades

    def _identify_temporal_patterns(
        self,
        timeline: EventTimeline,
    ) -> list[dict[str, Any]]:
        """识别时序模式"""
        patterns = []

        # 统计事件间隔
        events_by_type: dict[EventType, list[CorrelatedEvent]] = {}
        for event in timeline.events:
            events_by_type.setdefault(event.event_type, []).append(event)

        # Executor 不稳定模式：频繁丢失
        executor_lost_events = events_by_type.get(EventType.EXECUTOR_LOST, [])
        if len(executor_lost_events) >= 3:
            # 计算平均间隔
            intervals = []
            for i in range(1, len(executor_lost_events)):
                if executor_lost_events[i].timestamp and executor_lost_events[i - 1].timestamp:
                    delta = (
                        executor_lost_events[i].timestamp
                        - executor_lost_events[i - 1].timestamp
                    ).total_seconds()
                    intervals.append(delta)

            if intervals and sum(intervals) / len(intervals) < 60:
                patterns.append({
                    "type": "executor_instability",
                    "description": "Executor 频繁丢失（平均间隔 < 60s）",
                    "count": len(executor_lost_events),
                    "avg_interval": sum(intervals) / len(intervals),
                })

        # Stage 失败模式：连续失败
        stage_fail_events = events_by_type.get(EventType.STAGE_FAIL, [])
        if len(stage_fail_events) >= 2:
            patterns.append({
                "type": "stage_failure_cluster",
                "description": "多个 Stage 连续失败",
                "count": len(stage_fail_events),
            })

        # 快速失败模式：应用启动后立即失败
        app_start_events = events_by_type.get(EventType.APP_START, [])
        app_fail_events = events_by_type.get(EventType.APP_FAIL, [])
        if app_start_events and app_fail_events:
            start_time = app_start_events[0].timestamp
            fail_time = app_fail_events[0].timestamp
            if start_time and fail_time:
                delta = (fail_time - start_time).total_seconds()
                if delta < 120:
                    patterns.append({
                        "type": "fast_failure",
                        "description": "应用启动后快速失败（< 2min）",
                        "duration_seconds": delta,
                    })

        return patterns

    def _identify_root_event(
        self,
        timeline: EventTimeline,
        cascades: list[dict[str, Any]],
    ) -> CorrelatedEvent | None:
        """确定根事件"""
        if not cascades:
            # 没有级联，找第一个错误事件
            for event in timeline.events:
                if event.event_type in [
                    EventType.OOM_EXECUTOR,
                    EventType.OOM_DRIVER,
                    EventType.EXECUTOR_LOST,
                    EventType.SHUFFLE_FAILURE,
                    EventType.NETWORK_ERROR,
                    EventType.CLASS_NOT_FOUND,
                ]:
                    return event
            return None

        # 找最长级联的触发事件
        longest_cascade = max(cascades, key=lambda c: c["chain_length"])
        trigger_type = EventType(longest_cascade["trigger"])

        for event in timeline.events:
            if event.event_type == trigger_type:
                return event

        return None

    def _infer_propagation_path(
        self,
        timeline: EventTimeline,
        root_event: CorrelatedEvent | None,
    ) -> list[EventType]:
        """推断传播路径"""
        if root_event is None:
            return []

        # 从级联事件推断路径
        observed_path = [root_event.event_type]
        current = root_event

        while current.related_events:
            for ref in current.related_events:
                event_type_str, idx_str = ref.split("@")
                idx = int(idx_str)
                if idx < len(timeline.events):
                    next_event = timeline.events[idx]
                    observed_path.append(next_event.event_type)
                    current = next_event
                    break
            else:
                break

        # 匹配模板
        for template in FAILURE_PROPAGATION_PATHS:
            if observed_path[:len(template)] == template[:len(observed_path)]:
                return template

        return observed_path

    async def enrich_with_history_data(
        self,
        result: CorrelationResult,
        app_id: str,
    ) -> None:
        """使用 History Server 数据补充"""
        app = await self._history_client.get_application(app_id)
        stages = await self._history_client.get_application_stages(app_id)
        executors = await self._history_client.get_application_executors(app_id)

        if app:
            # 补充应用状态
            if app.status == "FAILED":
                if EventType.APP_FAIL not in [
                    e.event_type for e in result.timeline.events
                ]:
                    result.timeline.events.append(
                        CorrelatedEvent(
                            event_type=EventType.APP_FAIL,
                            timestamp=app.end_time,
                            source="history_server",
                            message=f"Application failed: {app.name}",
                        )
                    )

        # 补充 Stage 失败信息
        for stage in stages:
            if stage.failed_tasks > 0:
                existing = False
                for event in result.timeline.events:
                    if (
                        event.event_type == EventType.STAGE_FAIL
                        and event.context.get("stage_id") == stage.stage_id
                    ):
                        existing = True
                        break

                if not existing:
                    result.timeline.events.append(
                        CorrelatedEvent(
                            event_type=EventType.STAGE_FAIL,
                            timestamp=stage.completion_time,
                            source="history_server",
                            message=f"Stage {stage.stage_id} failed ({stage.failed_tasks} tasks)",
                            context={"stage_id": stage.stage_id, "failed_tasks": stage.failed_tasks},
                        )
                    )

        # 补充 Executor 丢失信息
        for executor in executors:
            if executor.state in ["LOST", "DEAD"]:
                existing = False
                for event in result.timeline.events:
                    if (
                        event.event_type == EventType.EXECUTOR_LOST
                        and event.context.get("executor_id") == executor.id
                    ):
                        existing = True
                        break

                if not existing:
                    result.timeline.events.append(
                        CorrelatedEvent(
                            event_type=EventType.EXECUTOR_LOST,
                            timestamp=executor.remove_time,
                            source="history_server",
                            message=f"Executor {executor.id} lost",
                            context={"executor_id": executor.id, "host": executor.host},
                        )
                    )

        # 重新排序
        result.timeline.events.sort(key=lambda e: e.timestamp or datetime.min)

    def generate_correlation_report(
        self,
        result: CorrelationResult,
    ) -> dict[str, Any]:
        """生成关联分析报告"""
        return {
            "app_id": result.app_id,
            "analysis_timestamp": datetime.now().isoformat(),
            "timeline_summary": {
                "start": result.timeline.start_time.isoformat() if result.timeline.start_time else None,
                "end": result.timeline.end_time.isoformat() if result.timeline.end_time else None,
                "total_events": len(result.timeline.events),
                "event_types": list(set(e.event_type.value for e in result.timeline.events)),
            },
            "cascade_failures": result.cascade_failures,
            "temporal_patterns": result.temporal_patterns,
            "root_event": {
                "type": result.root_event.event_type.value if result.root_event else None,
                "timestamp": result.root_event.timestamp.isoformat() if result.root_event and result.root_event.timestamp else None,
                "message": result.root_event.message[:200] if result.root_event else None,
            },
            "propagation_path": [e.value for e in result.propagation_path],
            "recommendations": self._generate_correlation_recommendations(result),
        }

    def _generate_correlation_recommendations(
        self,
        result: CorrelationResult,
    ) -> list[dict[str, Any]]:
        """基于关联分析生成建议"""
        recommendations = []

        if not result.root_event:
            return recommendations

        root_type = result.root_event.event_type

        # Executor OOM -> Stage Fail 级联
        if root_type == EventType.OOM_EXECUTOR and EventType.STAGE_FAIL in result.propagation_path:
            recommendations.append({
                "priority": 1,
                "action": "增加 Executor 内存配置",
                "reason": "OOM 导致 Stage 失败级联",
                "target": "spark.executor.memory",
            })
            recommendations.append({
                "priority": 2,
                "action": "检查数据倾斜问题",
                "reason": "可能存在 Executor 负载不均衡",
            })

        # Executor Lost -> Shuffle -> Stage 级联
        if root_type == EventType.EXECUTOR_LOST and EventType.SHUFFLE_FAILURE in result.propagation_path:
            recommendations.append({
                "priority": 1,
                "action": "检查 Executor 丢失原因（资源、网络）",
                "reason": "Executor 丢失触发 Shuffle 失败",
            })
            recommendations.append({
                "priority": 2,
                "action": "增加 Shuffle 重试配置",
                "target": "spark.shuffle.io.maxRetries",
            })

        # Executor 不稳定模式
        for pattern in result.temporal_patterns:
            if pattern["type"] == "executor_instability":
                recommendations.append({
                    "priority": 1,
                    "action": "检查集群资源分配",
                    "reason": "Executor 频繁丢失，可能资源不足",
                })

        return recommendations


# 全局实例
_correlation_engine: EventCorrelationEngine | None = None


def get_correlation_engine() -> EventCorrelationEngine:
    """获取关联引擎实例"""
    global _correlation_engine
    if _correlation_engine is None:
        _correlation_engine = EventCorrelationEngine()
    return _correlation_engine
"""巡检 API"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.patrol.engine import get_patrol_engine
from app.patrol.rules import get_patrol_rules
from app.patrol.scheduler import get_patrol_scheduler

router = APIRouter(prefix="/patrol", tags=["patrol"])


class PatrolReportResponse(BaseModel):
    """巡检报告响应"""
    id: str
    start_time: str
    end_time: str | None
    status: str
    checks: list[dict[str, Any]]
    summary: dict[str, Any]


class RuleUpdateRequest(BaseModel):
    """规则更新请求"""
    enabled: bool | None = None
    thresholds: dict[str, Any] | None = None
    notify_on_warning: bool | None = None
    notify_on_error: bool | None = None
    notify_on_critical: bool | None = None


class SchedulerCronRequest(BaseModel):
    """Cron 调度请求"""
    cron_expression: str = Field(..., description="Cron 表达式 (5字段格式: 分 时 日 月 周)")


class ThresholdUpdateRequest(BaseModel):
    """阈值更新请求"""
    threshold_name: str
    value: int | float | str


@router.get("/checks")
async def list_checks() -> dict[str, Any]:
    """列出所有可用的检查项"""
    engine = get_patrol_engine()
    checks = engine.list_checks()

    return {
        "checks": checks,
        "total": len(checks),
    }


@router.get("/reports")
async def list_reports(limit: int = 10) -> dict[str, Any]:
    """列出巡检报告"""
    engine = get_patrol_engine()
    reports = engine.list_reports(limit)

    return {
        "reports": reports,
        "total": len(reports),
    }


@router.get("/reports/{report_id}")
async def get_report(report_id: str) -> dict[str, Any]:
    """获取巡检报告详情"""
    engine = get_patrol_engine()
    report = engine.get_report(report_id)

    if not report:
        return {"error": "Report not found", "report_id": report_id}

    return report.to_dict()


@router.post("/run")
async def run_patrol(check_names: list[str] | None = None) -> dict[str, Any]:
    """手动触发巡检"""
    engine = get_patrol_engine()
    report = await engine.run_patrol(check_names)

    return report.to_dict()


@router.get("/latest")
async def get_latest_report() -> dict[str, Any]:
    """获取最新巡检报告"""
    engine = get_patrol_engine()
    report = engine.get_latest_report()

    if not report:
        return {
            "error": "No reports available",
            "message": "Run patrol first",
        }

    return report.to_dict()


# === Rules Management ===

@router.get("/rules")
async def list_rules() -> dict[str, Any]:
    """列出所有巡检规则"""
    rules = get_patrol_rules()
    all_rules = rules.list_rules()

    return {
        "rules": [r.model_dump() for r in all_rules],
        "total": len(all_rules),
    }


@router.get("/rules/{rule_name}")
async def get_rule(rule_name: str) -> dict[str, Any]:
    """获取规则详情"""
    rules = get_patrol_rules()
    rule = rules.get_rule(rule_name)

    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_name}' not found")

    return {
        "success": True,
        "rule": rule.model_dump(),
    }


@router.put("/rules/{rule_name}")
async def update_rule(rule_name: str, request: RuleUpdateRequest) -> dict[str, Any]:
    """更新规则配置"""
    rules = get_patrol_rules()

    # 构建更新数据
    updates: dict[str, Any] = {}
    if request.enabled is not None:
        updates["enabled"] = request.enabled
    if request.thresholds is not None:
        updates["thresholds"] = request.thresholds
    if request.notify_on_warning is not None:
        updates["notify_on_warning"] = request.notify_on_warning
    if request.notify_on_error is not None:
        updates["notify_on_error"] = request.notify_on_error
    if request.notify_on_critical is not None:
        updates["notify_on_critical"] = request.notify_on_critical

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    updated_rule = rules.update_rule(rule_name, updates)

    if not updated_rule:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_name}' not found")

    return {
        "success": True,
        "rule": updated_rule.model_dump(),
    }


@router.post("/rules/{rule_name}/enable")
async def enable_rule(rule_name: str) -> dict[str, Any]:
    """启用规则"""
    rules = get_patrol_rules()
    result = rules.enable_rule(rule_name)

    if not result:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_name}' not found")

    return {
        "success": True,
        "rule_name": rule_name,
        "enabled": True,
    }


@router.post("/rules/{rule_name}/disable")
async def disable_rule(rule_name: str) -> dict[str, Any]:
    """禁用规则"""
    rules = get_patrol_rules()
    result = rules.disable_rule(rule_name)

    if not result:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_name}' not found")

    return {
        "success": True,
        "rule_name": rule_name,
        "enabled": False,
    }


@router.put("/rules/{rule_name}/thresholds")
async def set_threshold(rule_name: str, request: ThresholdUpdateRequest) -> dict[str, Any]:
    """设置规则阈值"""
    rules = get_patrol_rules()
    result = rules.set_threshold(rule_name, request.threshold_name, request.value)

    if not result:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_name}' not found")

    rule = rules.get_rule(rule_name)
    return {
        "success": True,
        "rule_name": rule_name,
        "thresholds": rule.thresholds if rule else {},
    }


# === Scheduler Management ===

@router.get("/scheduler/status")
async def get_scheduler_status() -> dict[str, Any]:
    """获取调度器状态"""
    scheduler = get_patrol_scheduler()
    return scheduler.get_status()


@router.post("/scheduler/start")
async def start_scheduler(
    interval_minutes: int = 30,
) -> dict[str, Any]:
    """启动调度器（按间隔）"""
    scheduler = get_patrol_scheduler()
    scheduler.start(interval_minutes=interval_minutes)

    return {
        "success": True,
        "status": "started",
        "mode": "interval",
        "interval_minutes": interval_minutes,
        **scheduler.get_status(),
    }


@router.post("/scheduler/start/cron")
async def start_scheduler_cron(request: SchedulerCronRequest) -> dict[str, Any]:
    """启动调度器（按 Cron 表达式）"""
    scheduler = get_patrol_scheduler()

    try:
        scheduler.start_with_cron(request.cron_expression)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    return {
        "success": True,
        "status": "started",
        "mode": "cron",
        "cron_expression": request.cron_expression,
        **scheduler.get_status(),
    }


@router.post("/scheduler/stop")
async def stop_scheduler() -> dict[str, Any]:
    """停止调度器"""
    scheduler = get_patrol_scheduler()
    scheduler.stop()

    return {
        "success": True,
        "status": "stopped",
        "running": False,
    }

"""巡检 API"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.patrol.engine import get_patrol_engine
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


@router.get("/scheduler/status")
async def get_scheduler_status() -> dict[str, Any]:
    """获取调度器状态"""
    scheduler = get_patrol_scheduler()
    return scheduler.get_status()


@router.post("/scheduler/start")
async def start_scheduler(
    interval_minutes: int = 30,
) -> dict[str, Any]:
    """启动调度器"""
    scheduler = get_patrol_scheduler()
    scheduler.start(interval_minutes=interval_minutes)

    return {
        "status": "started",
        **scheduler.get_status(),
    }


@router.post("/scheduler/stop")
async def stop_scheduler() -> dict[str, Any]:
    """停止调度器"""
    scheduler = get_patrol_scheduler()
    scheduler.stop()

    return {
        "status": "stopped",
        "running": False,
    }


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
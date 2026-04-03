"""巡检 API"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/patrol", tags=["patrol"])


class PatrolReport(BaseModel):
    """巡检报告"""
    id: str
    start_time: datetime
    end_time: datetime | None = None
    status: str
    checks: list[dict[str, Any]]
    summary: dict[str, Any]


class PatrolCheckResult(BaseModel):
    """巡检结果"""
    item_name: str
    status: str  # pass, warning, failed
    message: str
    details: dict[str, Any] | None = None


# 模拟存储
_patrol_reports: list[dict[str, Any]] = []


@router.get("/reports")
async def list_patrol_reports(limit: int = 10) -> dict[str, Any]:
    """列出巡检报告"""
    return {
        "reports": _patrol_reports[-limit:],
        "total": len(_patrol_reports),
    }


@router.get("/reports/{report_id}")
async def get_patrol_report(report_id: str) -> dict[str, Any]:
    """获取巡检报告详情"""
    for report in _patrol_reports:
        if report["id"] == report_id:
            return report
    return {"error": "Report not found"}


@router.post("/run")
async def run_patrol() -> dict[str, Any]:
    """手动触发巡检"""
    # TODO: 实现巡检逻辑
    report = {
        "id": f"patrol-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "start_time": datetime.now().isoformat(),
        "end_time": datetime.now().isoformat(),
        "status": "completed",
        "checks": [
            {
                "item_name": "failed_spark_jobs",
                "status": "warning",
                "message": "最近 1 小时有 3 个任务失败",
                "details": {
                    "failed_count": 3,
                    "threshold": 5,
                },
            },
            {
                "item_name": "queue_utilization",
                "status": "pass",
                "message": "队列资源使用率正常",
                "details": {
                    "utilization": "45%",
                    "threshold": "80%",
                },
            },
        ],
        "summary": {
            "total_checks": 2,
            "passed": 1,
            "warnings": 1,
            "failed": 0,
        },
    }

    _patrol_reports.append(report)

    return report

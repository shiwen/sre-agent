"""巡检引擎核心"""

from abc import ABC, abstractmethod
import asyncio
from datetime import datetime
from typing import Any
import uuid

from pydantic import BaseModel, Field
from structlog import get_logger

logger = get_logger()


class CheckSeverity(str):
    """检查结果严重程度"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class CheckResult(BaseModel):
    """检查结果"""
    check_name: str
    status: str  # pass, warning, error, critical
    severity: str = CheckSeverity.INFO
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    resource: str | None = None
    suggestions: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)


class PatrolReport(BaseModel):
    """巡检报告"""
    id: str = Field(default_factory=lambda: f"patrol-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}")
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: datetime | None = None
    status: str = "running"  # running, completed, failed
    checks: list[CheckResult] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def add_check(self, result: CheckResult) -> None:
        """添加检查结果"""
        self.checks.append(result)

    def finalize(self) -> None:
        """完成报告"""
        self.end_time = datetime.now()
        self.status = "completed"

        # 统计
        self.summary = {
            "total_checks": len(self.checks),
            "passed": len([c for c in self.checks if c.status == "pass"]),
            "warnings": len([c for c in self.checks if c.status == "warning"]),
            "errors": len([c for c in self.checks if c.status == "error"]),
            "critical": len([c for c in self.checks if c.status == "critical"]),
            "duration_seconds": (self.end_time - self.start_time).total_seconds(),
        }

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "checks": [c.model_dump() for c in self.checks],
            "summary": self.summary,
            "metadata": self.metadata,
        }


class BaseCheck(ABC):
    """检查基类"""

    name: str = "base_check"
    description: str = "基础检查"
    enabled: bool = True

    @abstractmethod
    async def execute(self) -> CheckResult:
        """执行检查"""
        pass

    def _pass(self, message: str, **kwargs) -> CheckResult:
        """返回通过结果"""
        return CheckResult(
            check_name=self.name,
            status="pass",
            severity=CheckSeverity.INFO,
            message=message,
            **kwargs,
        )

    def _warning(self, message: str, **kwargs) -> CheckResult:
        """返回警告结果"""
        return CheckResult(
            check_name=self.name,
            status="warning",
            severity=CheckSeverity.WARNING,
            message=message,
            **kwargs,
        )

    def _error(self, message: str, **kwargs) -> CheckResult:
        """返回错误结果"""
        return CheckResult(
            check_name=self.name,
            status="error",
            severity=CheckSeverity.ERROR,
            message=message,
            **kwargs,
        )

    def _critical(self, message: str, **kwargs) -> CheckResult:
        """返回严重错误结果"""
        return CheckResult(
            check_name=self.name,
            status="critical",
            severity=CheckSeverity.CRITICAL,
            message=message,
            **kwargs,
        )


class PatrolEngine:
    """巡检引擎"""

    def __init__(self) -> None:
        self._checks: list[BaseCheck] = []
        self._reports: list[PatrolReport] = []
        self._max_reports = 100

    def register_check(self, check: BaseCheck) -> None:
        """注册检查"""
        self._checks.append(check)
        logger.info("check_registered", check_name=check.name)

    def register_checks(self, checks: list[BaseCheck]) -> None:
        """批量注册检查"""
        for check in checks:
            self.register_check(check)

    def list_checks(self) -> list[dict[str, Any]]:
        """列出所有检查"""
        return [
            {
                "name": c.name,
                "description": c.description,
                "enabled": c.enabled,
            }
            for c in self._checks
        ]

    async def run_patrol(self, check_names: list[str] | None = None) -> PatrolReport:
        """执行巡检"""
        report = PatrolReport(
            metadata={
                "check_filter": check_names,
                "total_registered": len(self._checks),
            }
        )

        logger.info(
            "patrol_started",
            report_id=report.id,
            checks=len(self._checks),
        )

        # 过滤要执行的检查
        checks_to_run = self._checks
        if check_names:
            checks_to_run = [c for c in self._checks if c.name in check_names]

        # 并行执行检查
        tasks = [self._run_check(check, report) for check in checks_to_run if check.enabled]
        await asyncio.gather(*tasks, return_exceptions=True)

        # 完成报告
        report.finalize()

        # 保存报告
        self._reports.append(report)
        if len(self._reports) > self._max_reports:
            self._reports = self._reports[-self._max_reports:]

        logger.info(
            "patrol_completed",
            report_id=report.id,
            summary=report.summary,
        )

        return report

    async def _run_check(self, check: BaseCheck, report: PatrolReport) -> None:
        """执行单个检查"""
        try:
            result = await check.execute()
            report.add_check(result)

            if result.status != "pass":
                logger.warning(
                    "check_failed",
                    check_name=check.name,
                    status=result.status,
                    message=result.message,
                )
        except Exception as e:
            logger.error(
                "check_error",
                check_name=check.name,
                error=str(e),
            )
            report.add_check(CheckResult(
                check_name=check.name,
                status="error",
                severity=CheckSeverity.ERROR,
                message=f"检查执行失败: {e}",
            ))

    def get_report(self, report_id: str) -> PatrolReport | None:
        """获取报告"""
        for report in self._reports:
            if report.id == report_id:
                return report
        return None

    def list_reports(self, limit: int = 10) -> list[dict[str, Any]]:
        """列出报告"""
        reports = self._reports[-limit:]
        return [r.to_dict() for r in reversed(reports)]

    def get_latest_report(self) -> PatrolReport | None:
        """获取最新报告"""
        return self._reports[-1] if self._reports else None


# 全局实例
_patrol_engine: PatrolEngine | None = None


def get_patrol_engine() -> PatrolEngine:
    """获取全局巡检引擎"""
    global _patrol_engine
    if _patrol_engine is None:
        _patrol_engine = PatrolEngine()
        # 注册默认检查
        from app.patrol.checks import get_default_checks
        _patrol_engine.register_checks(get_default_checks())
    return _patrol_engine

from __future__ import annotations

import asyncio

from app.jobs.port_sync import normalize_stage_selector, run_port_backfill, run_port_daily_sync
from app.orchestrator_port import ALL_STAGES, DAILY_DEFAULT_STAGES, PortCrawlerOrchestrator


class FakeOrchestrator(PortCrawlerOrchestrator):
    def __init__(self) -> None:
        super().__init__(session_factory=lambda: None)
        self.daily_calls = []
        self.backfill_calls = []

    async def run_daily_sync(self, *, stages=None, project_ids=None):
        self.daily_calls.append({"stages": stages, "project_ids": project_ids})
        return {"success": True, "mode": "daily", "stages_requested": list(stages or [])}

    async def run_backfill(self, *, stages=None, project_ids=None, checkpoints=None, requested_metrics_days=3650):
        self.backfill_calls.append(
            {
                "stages": stages,
                "project_ids": project_ids,
                "checkpoints": checkpoints,
                "requested_metrics_days": requested_metrics_days,
            }
        )
        return {"success": True, "mode": "backfill", "stages_requested": list(stages or [])}


def test_port_orchestrator_keeps_stage_isolation_on_failure(monkeypatch) -> None:
    orchestrator = PortCrawlerOrchestrator()
    call_order: list[str] = []

    async def fail_events(**_):
        call_order.append("events")
        raise RuntimeError("events unavailable")

    async def ok_metrics(**_):
        call_order.append("metrics")
        return {"success": True, "stats": {"processed": 2}}

    async def ok_overviews(**_):
        call_order.append("overviews")
        return {"success": True, "stats": {"updated": 1}}

    monkeypatch.setattr(orchestrator, "run_events_stage", fail_events)
    monkeypatch.setattr(orchestrator, "run_metrics_stage", ok_metrics)
    monkeypatch.setattr(orchestrator, "run_overview_stage", ok_overviews)

    result = asyncio.run(orchestrator.run_daily_sync(stages=["events", "metrics", "overviews"]))

    assert call_order == ["events", "metrics", "overviews"]
    assert result["stages"]["events"]["success"] is False
    assert result["stages"]["metrics"]["success"] is True
    assert result["stages"]["overviews"]["success"] is True
    assert any("events:" in error for error in result["errors"])


def test_port_backfill_returns_checkpoint_and_cap_reason(monkeypatch) -> None:
    orchestrator = PortCrawlerOrchestrator()

    async def ok_star_history(**_):
        return {
            "success": True,
            "stats": {
                "checkpoints": {"github:42": {"next_page": 6, "reached_cap": True, "complete": False}},
                "cap_reasons": [{"project": "acme/repo", "reason": "stargazer pages capped at 300"}],
            },
        }

    monkeypatch.setattr(orchestrator, "run_star_history_stage", ok_star_history)

    result = asyncio.run(orchestrator.run_backfill(stages=["star_history"], checkpoints={"github:42": {"next_page": 5}}))
    stage_stats = result["stages"]["star_history"]["stats"]

    assert result["stages"]["star_history"]["success"] is True
    assert stage_stats["checkpoints"]["github:42"]["next_page"] == 6
    assert stage_stats["cap_reasons"][0]["reason"].startswith("stargazer pages capped")


def test_port_jobs_forward_stage_scope_and_backfill_options() -> None:
    orchestrator = FakeOrchestrator()

    asyncio.run(run_port_daily_sync(orchestrator=orchestrator, stages="events,metrics", project_ids=[100, 200]))
    asyncio.run(
        run_port_backfill(
            orchestrator=orchestrator,
            stages=["star_history", "metrics"],
            project_ids=[300],
            checkpoints={"github:300": {"next_page": 2, "complete": False, "reached_cap": False}},
            requested_metrics_days=1200,
        )
    )

    assert orchestrator.daily_calls[0]["stages"] == ["events", "metrics"]
    assert orchestrator.daily_calls[0]["project_ids"] == [100, 200]
    assert orchestrator.backfill_calls[0]["stages"] == ["star_history", "metrics"]
    assert orchestrator.backfill_calls[0]["requested_metrics_days"] == 1200


def test_stage_selector_defaults_and_filters_unknown_values() -> None:
    assert normalize_stage_selector(None, default=DAILY_DEFAULT_STAGES) == list(DAILY_DEFAULT_STAGES)
    assert normalize_stage_selector("events,metrics,invalid", default=DAILY_DEFAULT_STAGES) == ["events", "metrics"]
    assert normalize_stage_selector([], default=ALL_STAGES) == list(ALL_STAGES)

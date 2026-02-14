from __future__ import annotations

import logging
import asyncio
from dataclasses import dataclass
from typing import Any

import httpx
import pytest

from app.crawlers.port.client import GitHubPortClient, sanitize_for_log
from app.crawlers.port.contracts import FetchResult, FetchState
from app.crawlers.port.events_stage import EventsStage
from app.orchestrator_port import PortCrawlerOrchestrator


@dataclass
class FakeProject:
    id: int
    full_name: str


class AlwaysFailEventsClient:
    async def list_releases(self, *_: Any, **__: Any) -> FetchResult[list[dict[str, Any]]]:
        return FetchResult(state=FetchState.FAILED, error="Authorization: Bearer top-secret-release", status_code=503)

    async def list_tags(self, *_: Any, **__: Any) -> FetchResult[list[dict[str, Any]]]:
        return FetchResult(state=FetchState.FAILED, error="token=tag-secret-value", status_code=503)

    async def get_content(self, _: str, __: str, ___: str) -> FetchResult[str]:
        return FetchResult(state=FetchState.FAILED, error="access_token=content-secret-value", status_code=504)


class FakeQuery:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def filter(self, *_: Any, **__: Any) -> "FakeQuery":
        return self

    def all(self) -> list[Any]:
        return self._rows


class FakeDB:
    def query(self, _: Any) -> FakeQuery:
        return FakeQuery([])

    def add(self, _: Any) -> None:
        return None


def test_redaction_policy_masks_credentials_and_payloads() -> None:
    payload = {
        "Authorization": "Bearer ghp_super_secret_token",
        "api_key": "sk-live-secret",
        "session": "session-secret",
        "body": "# heading\nvery long markdown body",
        "nested": {"token": "nested-secret", "retry_after": 3, "message": "access_token=inside-message"},
    }

    sanitized = sanitize_for_log(payload)

    assert sanitized["Authorization"] == "***REDACTED***"
    assert sanitized["api_key"] == "***REDACTED***"
    assert sanitized["session"] == "***REDACTED***"
    assert sanitized["body"].startswith("<redacted payload")
    assert sanitized["nested"]["token"] == "***REDACTED***"
    assert "inside-message" not in sanitized["nested"]["message"]


def test_client_error_logs_redact_query_tokens(caplog: pytest.LogCaptureFixture) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, request=request, json={"message": "bad creds"})

    client = GitHubPortClient(token="token-value", transport=httpx.MockTransport(handler), max_retries=1)

    async def _run() -> tuple[FetchResult[Any], GitHubPortClient]:
        with caplog.at_level(logging.WARNING, logger="app.crawlers.port.client"):
            output = await client._request("/repos/owner/repo", params={"access_token": "plain-secret-token"})
        return output, client

    result, open_client = asyncio.run(_run())
    asyncio.run(open_client.aclose())

    assert result.state == FetchState.FAILED
    assert "plain-secret-token" not in caplog.text
    assert any(record.msg == "GitHub request failed" for record in caplog.records)


def test_events_fallback_warning_redacts_source_errors(caplog: pytest.LogCaptureFixture) -> None:
    stage = EventsStage(AlwaysFailEventsClient())
    db = FakeDB()

    async def _run() -> FetchResult[Any] | Any:
        with caplog.at_level(logging.WARNING, logger="app.crawlers.port.events_stage"):
            return await stage.ingest_project(db, FakeProject(id=1, full_name="owner/repo"))

    result = asyncio.run(_run())

    assert result.skipped_event_update is True
    assert any(record.msg == "Skipping project event update because all sources failed" for record in caplog.records)
    for reason in result.failure_reasons:
        assert "secret" not in reason


def test_orchestrator_redacts_failed_stage_error_in_logs_and_stats(caplog: pytest.LogCaptureFixture) -> None:
    orchestrator = PortCrawlerOrchestrator()

    async def failed_events(**_: Any) -> dict[str, Any]:
        return {
            "success": False,
            "error": "Authorization: Bearer run-secret-token",
            "stats": {"payload": "api_key=raw-key"},
        }

    orchestrator.run_events_stage = failed_events  # type: ignore[method-assign]

    async def _run() -> dict[str, Any]:
        with caplog.at_level(logging.WARNING, logger="app.orchestrator_port"):
            return await orchestrator.run_daily_sync(stages=["events"])

    result = asyncio.run(_run())

    assert result["success"] is False
    assert "run-secret-token" not in str(result["errors"])
    assert "raw-key" not in caplog.text
    assert any(record.msg == "Port stage reported failure" for record in caplog.records)

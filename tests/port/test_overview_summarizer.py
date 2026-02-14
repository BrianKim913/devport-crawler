from __future__ import annotations

import asyncio

from app.services.port.overview_summarizer import PLACEHOLDER_TEXT, OverviewSummarizerService


def test_summarize_returns_valid_payload() -> None:
    async def llm_ok(_prompt: str) -> dict[str, object]:
        return {
            "summary": "이 프로젝트는 설치 방법과 사용 흐름을 단계별로 설명합니다.",
            "highlights": ["설치 절차", "사용 예시"],
            "quickstart": "pip install demo && demo run",
            "links": [{"label": "README", "url": "https://github.com/acme/demo/blob/main/README.md"}],
        }

    service = OverviewSummarizerService(llm_call=llm_ok, max_attempts=3, backoff_base_seconds=0.01, backoff_max_seconds=0.02)
    result = asyncio.run(
        service.summarize(
            project_name="demo",
            source_markdown="# Demo\n\n## Overview\nProject details",
            links=[{"label": "README", "url": "https://github.com/acme/demo/blob/main/README.md"}],
        )
    )

    assert result["summary"].startswith("이 프로젝트")
    assert result["highlights"] == ["설치 절차", "사용 예시"]
    assert result["quickstart"]


def test_retries_schema_failures_then_returns_placeholder() -> None:
    calls = {"count": 0}
    sleeps: list[float] = []

    async def llm_invalid(_prompt: str) -> dict[str, object]:
        calls["count"] += 1
        return {
            "summary": "혁신적인 최고의 프로젝트입니다!!!",
            "highlights": ["과장 표현"],
            "quickstart": "run",
            "links": [{"label": "README", "url": "https://github.com/acme/demo/blob/main/README.md"}],
        }

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    service = OverviewSummarizerService(
        llm_call=llm_invalid,
        max_attempts=3,
        backoff_base_seconds=0.01,
        backoff_max_seconds=0.02,
        sleeper=fake_sleep,
    )
    result = asyncio.run(
        service.summarize(
            project_name="demo",
            source_markdown="# Demo",
            links=[{"label": "README", "url": "https://github.com/acme/demo/blob/main/README.md"}],
        )
    )

    assert calls["count"] == 3
    assert len(sleeps) == 2
    assert result["summary"] == PLACEHOLDER_TEXT
    assert result["highlights"] == []


def test_retries_until_schema_valid_then_succeeds() -> None:
    calls = {"count": 0}

    async def llm_flaky(_prompt: str):
        calls["count"] += 1
        if calls["count"] < 3:
            return {"summary": "", "highlights": [], "quickstart": None, "links": []}
        return {
            "summary": "이 문서는 기능 설명과 적용 범위를 정리합니다.",
            "highlights": ["기능 설명", "적용 범위"],
            "quickstart": None,
            "links": [],
        }

    async def fake_sleep(_seconds: float) -> None:
        return None

    service = OverviewSummarizerService(llm_call=llm_flaky, max_attempts=4, sleeper=fake_sleep)
    result = asyncio.run(service.summarize(project_name="demo", source_markdown="# Demo", links=[]))

    assert calls["count"] == 3
    assert result["summary"].startswith("이 문서는")

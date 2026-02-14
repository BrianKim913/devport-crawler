from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime

from app.crawlers.port.overview_stage import OverviewProjectRef, ProjectOverviewStage
from app.services.port.overview_sources import OverviewSourcePayload


@dataclass
class StoredOverview:
    project_id: int
    summary: str
    highlights: list[str]
    quickstart: str | None
    links: list[dict[str, str]]
    source_url: str
    raw_hash: str
    fetched_at: datetime
    summarized_at: datetime
    updated_at: datetime


class FakeOverviewRepository:
    def __init__(self) -> None:
        self.items: dict[int, StoredOverview] = {}

    def get_by_project_id(self, project_id: int):
        return self.items.get(project_id)

    def upsert(self, *, project_id: int, payload: dict):
        existing = self.items.get(project_id)
        if existing is None:
            self.items[project_id] = StoredOverview(project_id=project_id, **payload)
            return
        for key, value in payload.items():
            setattr(existing, key, value)


class FakeAggregator:
    def __init__(self) -> None:
        self.calls = 0

    async def collect(self, *, owner: str, repo: str, previous_raw_hash: str | None = None) -> OverviewSourcePayload:
        self.calls += 1
        base = OverviewSourcePayload(
            source_url=f"https://github.com/{owner}/{repo}/blob/main/README.md",
            raw_text="overview source text",
            raw_hash="hash-1",
            links=[{"label": "README", "url": f"https://github.com/{owner}/{repo}/blob/main/README.md"}],
            fetched_at=datetime.utcnow(),
            skipped=False,
        )
        if previous_raw_hash == "hash-1":
            base.skipped = True
        return base


class FakeSummarizer:
    def __init__(self) -> None:
        self.calls = 0

    async def summarize(self, *, project_name: str, source_markdown: str, links: list[dict[str, str]]):
        self.calls += 1
        return {
            "summary": f"{project_name} 개요",
            "highlights": ["핵심 포인트"],
            "quickstart": "pip install demo",
            "links": links,
        }


def test_overview_stage_upserts_and_skips_when_hash_unchanged() -> None:
    repository = FakeOverviewRepository()
    aggregator = FakeAggregator()
    summarizer = FakeSummarizer()
    stage = ProjectOverviewStage(source_aggregator=aggregator, summarizer=summarizer, repository=repository)

    projects = [OverviewProjectRef(project_id=100, owner="acme", repo="demo", project_name="demo")]

    first_stats = asyncio.run(stage.run(projects))
    second_stats = asyncio.run(stage.run(projects))

    assert first_stats.updated == 1
    assert first_stats.skipped == 0
    assert second_stats.updated == 0
    assert second_stats.skipped == 1
    assert summarizer.calls == 1

    stored = repository.get_by_project_id(100)
    assert stored is not None
    assert stored.raw_hash == "hash-1"
    assert stored.summary == "demo 개요"

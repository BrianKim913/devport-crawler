"""Project overview ingestion stage for port crawler."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.models.project_overview import ProjectOverview


@dataclass(slots=True)
class OverviewProjectRef:
    """Minimal project reference for overview ingestion."""

    project_id: int
    owner: str
    repo: str
    project_name: str


@dataclass(slots=True)
class OverviewStageStats:
    """Stage execution statistics."""

    processed: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0


class OverviewRepository(Protocol):
    """Storage interface for project overview upserts."""

    def get_by_project_id(self, project_id: int) -> ProjectOverview | None: ...

    def upsert(self, *, project_id: int, payload: dict[str, Any]) -> None: ...


class SQLAlchemyOverviewRepository:
    """SQLAlchemy-backed repository for project_overviews."""

    def __init__(self, session: Any) -> None:
        self._session = session

    def get_by_project_id(self, project_id: int) -> ProjectOverview | None:
        return self._session.query(ProjectOverview).filter(ProjectOverview.project_id == project_id).one_or_none()

    def upsert(self, *, project_id: int, payload: dict[str, Any]) -> None:
        existing = self.get_by_project_id(project_id)
        if existing is None:
            self._session.add(ProjectOverview(project_id=project_id, **payload))
            return

        for key, value in payload.items():
            setattr(existing, key, value)


class ProjectOverviewStage:
    """Overview stage with unchanged-hash skip and resilient failure isolation."""

    def __init__(
        self,
        *,
        source_aggregator: Any,
        summarizer: Any,
        repository: OverviewRepository,
    ) -> None:
        self._sources = source_aggregator
        self._summarizer = summarizer
        self._repository = repository

    async def run(self, projects: list[OverviewProjectRef]) -> OverviewStageStats:
        stats = OverviewStageStats()
        for project in projects:
            stats.processed += 1
            try:
                changed = await self._process_project(project)
                if changed is None:
                    stats.skipped += 1
                elif changed:
                    stats.updated += 1
                else:
                    stats.failed += 1
            except Exception:
                stats.failed += 1
        return stats

    async def _process_project(self, project: OverviewProjectRef) -> bool | None:
        existing = self._repository.get_by_project_id(project.project_id)
        previous_hash = existing.raw_hash if existing is not None else None

        source_payload = await self._sources.collect(
            owner=project.owner,
            repo=project.repo,
            previous_raw_hash=previous_hash,
        )
        if source_payload.skipped:
            return None

        summary_payload = await self._summarizer.summarize(
            project_name=project.project_name,
            source_markdown=source_payload.raw_text,
            links=source_payload.links,
        )

        now = datetime.utcnow()
        payload = {
            "summary": summary_payload["summary"],
            "highlights": summary_payload.get("highlights", []),
            "quickstart": summary_payload.get("quickstart"),
            "links": summary_payload.get("links", []),
            "source_url": source_payload.source_url,
            "raw_hash": source_payload.raw_hash,
            "fetched_at": source_payload.fetched_at,
            "summarized_at": now,
            "updated_at": now,
        }
        self._repository.upsert(project_id=project.project_id, payload=payload)
        return True

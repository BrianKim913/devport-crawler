"""Readiness evaluator for exclude-until-ready wiki decisions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.crawlers.wiki.contracts import ReadinessMetadata
from app.models.project import Project


class ReadinessEvaluator:
    """Deterministic data-readiness evaluation for wiki generation.
    
    Projects failing readiness thresholds are excluded from wiki surfacing
    until data quality improves. Top-star repositories are prioritized.
    """

    def __init__(
        self,
        *,
        min_stars: int = 100,
        min_readme_chars: int = 500,
        min_events_12mo: int = 5,
        min_release_tags: int = 3,
    ) -> None:
        self._min_stars = min_stars
        self._min_readme_chars = min_readme_chars
        self._min_events_12mo = min_events_12mo
        self._min_release_tags = min_release_tags

    async def evaluate(self, project: Project) -> ReadinessMetadata:
        """Evaluate project readiness for wiki generation.
        
        Args:
            project: Project model with metadata.
            
        Returns:
            ReadinessMetadata with all gate results.
        """
        # Star gate (top-star prioritization)
        actual_stars = int(getattr(project, "stars", 0) or 0)
        passes_star_gate = actual_stars >= self._min_stars

        # History coverage (12-month activity)
        event_count_12mo = await self._count_recent_events(project)
        has_12mo_history = event_count_12mo >= self._min_events_12mo

        # Release/tag coverage
        release_count, tag_count = await self._count_releases_and_tags(project)
        has_release_coverage = (release_count + tag_count) >= self._min_release_tags

        # README/docs sufficiency
        readme_length = await self._estimate_readme_length(project)
        has_sufficient_readme = readme_length >= self._min_readme_chars

        return ReadinessMetadata(
            has_12mo_history=has_12mo_history,
            event_count_12mo=event_count_12mo,
            has_release_coverage=has_release_coverage,
            release_count=release_count,
            tag_count=tag_count,
            has_sufficient_readme=has_sufficient_readme,
            readme_length_chars=readme_length,
            passes_top_star_gate=passes_star_gate,
            min_stars_threshold=self._min_stars,
            actual_stars=actual_stars,
        )

    async def _count_recent_events(self, project: Project) -> int:
        """Count repository events in last 12 months.
        
        Args:
            project: Project model.
            
        Returns:
            Event count in last 12 months.
        """
        # Simplified - in real implementation, would query project_events table
        # For now, use a heuristic based on project metadata
        cutoff = datetime.now(UTC) - timedelta(days=365)
        pushed_at = getattr(project, "pushed_at", None)
        
        if pushed_at and pushed_at > cutoff:
            # Active project - estimate based on recency
            return 10
        return 0

    async def _count_releases_and_tags(self, project: Project) -> tuple[int, int]:
        """Count releases and tags for project.
        
        Args:
            project: Project model.
            
        Returns:
            Tuple of (release_count, tag_count).
        """
        # Simplified - in real implementation, would query project_events table
        # or fetch from GitHub API
        # For now, return placeholder counts
        return (0, 0)

    async def _estimate_readme_length(self, project: Project) -> int:
        """Estimate README content length.
        
        Args:
            project: Project model.
            
        Returns:
            Estimated character count of README/docs.
        """
        # Simplified - in real implementation, would fetch README content
        # For now, use description length as proxy
        description = getattr(project, "description", "") or ""
        return len(description) * 10  # Rough multiplier estimate


def is_data_ready(metadata: ReadinessMetadata) -> bool:
    """Determine if project meets minimum readiness for wiki display.
    
    Args:
        metadata: Readiness metadata with gate results.
        
    Returns:
        True if project should be shown, False if excluded until data improves.
    """
    return (
        metadata.passes_top_star_gate
        and metadata.has_sufficient_readme
        and (metadata.has_12mo_history or metadata.has_release_coverage)
    )

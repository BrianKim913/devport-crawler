"""Core-6 wiki snapshot contracts with data-readiness gates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


SectionType = Literal["what", "how", "architecture", "activity", "releases", "chat"]


@dataclass(frozen=True)
class WikiSection:
    """Progressive disclosure section with summary + deep dive content."""

    summary: str
    """Short summary paragraph (1-3 sentences) for quick scanning."""

    deep_dive_markdown: str
    """Full technical explanation in markdown format with code examples, diagrams, and details."""

    default_expanded: bool = False
    """Whether this section should be expanded by default in UI."""

    generated_diagram_dsl: str | None = None
    """Optional Mermaid DSL for generated architecture/flow diagrams."""


@dataclass(frozen=True)
class WikiSnapshot:
    """Complete wiki snapshot for a single project with Core-6 sections and readiness metadata.

    This is the canonical contract shared across crawler output, API persistence, and frontend rendering.
    """

    project_external_id: str
    """GitHub project external ID (e.g., 'github:12345' or 'github:owner/repo')."""

    generated_at: str
    """ISO 8601 timestamp when this snapshot was generated."""

    # Core-6 sections
    what: WikiSection
    """What this project is - purpose, domain, target users."""

    how: WikiSection
    """How it works - key concepts, workflow, usage patterns."""

    architecture: WikiSection
    """Architecture and codebase explanation - structure, components, technical design."""

    activity: WikiSection
    """Repository activity - last 12 months of events, commits, contributors."""

    releases: WikiSection
    """Releases and tags - timeline with narrative + all tags."""

    chat: WikiSection
    """Chat module payload - repo context + ecosystem grounding for Q&A."""

    # Readiness and hiding controls
    is_data_ready: bool
    """Whether this project meets minimum data quality thresholds for public wiki display."""

    hidden_sections: tuple[SectionType, ...]
    """List of section names to hide due to incomplete/low-confidence data."""

    readiness_metadata: ReadinessMetadata
    """Detailed readiness scoring and gate results."""


@dataclass(frozen=True)
class ReadinessMetadata:
    """Data quality gates and readiness scoring for wiki coverage decisions.

    Projects failing readiness thresholds are excluded from wiki surfacing until data improves.
    """

    # History coverage
    has_12mo_history: bool
    """Whether project has sufficient activity data for last 12 months."""

    event_count_12mo: int
    """Count of repository events in last 12 months."""

    # Release/tag coverage
    has_release_coverage: bool
    """Whether project has releases or tags for timeline."""

    release_count: int
    """Total published releases count."""

    tag_count: int
    """Total git tags count (includes releases + version tags)."""

    # Source content minimums
    has_sufficient_readme: bool
    """Whether README/docs provide enough content for explanations."""

    readme_length_chars: int
    """Character count of aggregated README/docs source."""

    # Overall readiness
    passes_top_star_gate: bool
    """Whether project meets top-star repository criteria (configurable threshold)."""

    min_stars_threshold: int
    """Configured minimum stars threshold for wiki eligibility."""

    actual_stars: int
    """Actual stargazer count at snapshot time."""


def is_section_ready(section: WikiSection, section_type: SectionType, metadata: ReadinessMetadata) -> bool:
    """Determine if a section has sufficient data quality to be shown.

    Args:
        section: The wiki section to check.
        section_type: Which Core-6 section type this is.
        metadata: Readiness metadata with quality gates.

    Returns:
        True if section should be displayed, False if it should be hidden.
    """
    # Always show what/how if generated
    if section_type in ("what", "how"):
        return len(section.summary.strip()) > 0

    # Architecture requires readme content
    if section_type == "architecture":
        return metadata.has_sufficient_readme and len(section.summary.strip()) > 0

    # Activity requires 12-month history
    if section_type == "activity":
        return metadata.has_12mo_history and metadata.event_count_12mo >= 5

    # Releases require release or tag coverage
    if section_type == "releases":
        return metadata.has_release_coverage and (metadata.release_count + metadata.tag_count) >= 3

    # Chat requires overall data readiness
    if section_type == "chat":
        return metadata.has_sufficient_readme and metadata.has_12mo_history

    return True


def calculate_hidden_sections(snapshot: WikiSnapshot) -> tuple[SectionType, ...]:
    """Calculate which sections should be hidden based on readiness gates.

    Args:
        snapshot: Complete wiki snapshot with all sections.

    Returns:
        Tuple of section names that should be hidden in UI.
    """
    sections_to_check: list[tuple[SectionType, WikiSection]] = [
        ("what", snapshot.what),
        ("how", snapshot.how),
        ("architecture", snapshot.architecture),
        ("activity", snapshot.activity),
        ("releases", snapshot.releases),
        ("chat", snapshot.chat),
    ]

    hidden: list[SectionType] = []
    for section_type, section in sections_to_check:
        if not is_section_ready(section, section_type, snapshot.readiness_metadata):
            hidden.append(section_type)

    return tuple(hidden)

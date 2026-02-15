"""Tests for wiki snapshot contracts and readiness gates."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.crawlers.wiki.contracts import (
    ReadinessMetadata,
    WikiSection,
    WikiSnapshot,
    calculate_hidden_sections,
    is_section_ready,
)


@pytest.fixture
def sample_section():
    """Create a sample wiki section for testing."""
    return WikiSection(
        summary="This is a summary.",
        deep_dive_markdown="# Deep Dive\n\nDetailed explanation here.",
        default_expanded=False,
        generated_diagram_dsl=None,
    )


@pytest.fixture
def passing_readiness():
    """Create readiness metadata that passes all gates."""
    return ReadinessMetadata(
        has_12mo_history=True,
        event_count_12mo=25,
        has_release_coverage=True,
        release_count=10,
        tag_count=5,
        has_sufficient_readme=True,
        readme_length_chars=2000,
        passes_top_star_gate=True,
        min_stars_threshold=100,
        actual_stars=5000,
    )


@pytest.fixture
def failing_readiness():
    """Create readiness metadata that fails multiple gates."""
    return ReadinessMetadata(
        has_12mo_history=False,
        event_count_12mo=2,
        has_release_coverage=False,
        release_count=0,
        tag_count=1,
        has_sufficient_readme=False,
        readme_length_chars=200,
        passes_top_star_gate=False,
        min_stars_threshold=100,
        actual_stars=50,
    )


def test_is_section_ready_what_and_how_always_pass(sample_section, failing_readiness):
    """'what' and 'how' sections should pass if they have content."""
    assert is_section_ready(sample_section, "what", failing_readiness)
    assert is_section_ready(sample_section, "how", failing_readiness)


def test_is_section_ready_architecture_requires_readme(sample_section, failing_readiness, passing_readiness):
    """Architecture section requires sufficient README content."""
    assert not is_section_ready(sample_section, "architecture", failing_readiness)
    assert is_section_ready(sample_section, "architecture", passing_readiness)


def test_is_section_ready_activity_requires_12mo_history(sample_section, failing_readiness, passing_readiness):
    """Activity section requires 12-month history and minimum events."""
    assert not is_section_ready(sample_section, "activity", failing_readiness)
    assert is_section_ready(sample_section, "activity", passing_readiness)


def test_is_section_ready_releases_requires_coverage(sample_section, failing_readiness, passing_readiness):
    """Releases section requires release or tag coverage."""
    assert not is_section_ready(sample_section, "releases", failing_readiness)
    assert is_section_ready(sample_section, "releases", passing_readiness)


def test_is_section_ready_chat_requires_overall_readiness(sample_section, failing_readiness, passing_readiness):
    """Chat section requires both README and 12mo history."""
    assert not is_section_ready(sample_section, "chat", failing_readiness)
    assert is_section_ready(sample_section, "chat", passing_readiness)


def test_calculate_hidden_sections_all_pass(sample_section, passing_readiness):
    """When all gates pass, no sections should be hidden."""
    snapshot = WikiSnapshot(
        project_external_id="github:12345",
        generated_at=datetime.now(UTC).isoformat(),
        what=sample_section,
        how=sample_section,
        architecture=sample_section,
        activity=sample_section,
        releases=sample_section,
        chat=sample_section,
        is_data_ready=True,
        hidden_sections=(),
        readiness_metadata=passing_readiness,
    )

    hidden = calculate_hidden_sections(snapshot)
    assert hidden == ()


def test_calculate_hidden_sections_multiple_failures(sample_section, failing_readiness):
    """When multiple gates fail, corresponding sections should be hidden."""
    snapshot = WikiSnapshot(
        project_external_id="github:12345",
        generated_at=datetime.now(UTC).isoformat(),
        what=sample_section,
        how=sample_section,
        architecture=sample_section,
        activity=sample_section,
        releases=sample_section,
        chat=sample_section,
        is_data_ready=False,
        hidden_sections=(),
        readiness_metadata=failing_readiness,
    )

    hidden = calculate_hidden_sections(snapshot)
    # Should hide architecture (no readme), activity (no history), releases (no coverage), chat (incomplete)
    assert set(hidden) == {"architecture", "activity", "releases", "chat"}
    assert "what" not in hidden
    assert "how" not in hidden


def test_wiki_section_immutability(sample_section):
    """WikiSection should be frozen/immutable."""
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        sample_section.summary = "modified"


def test_readiness_metadata_immutability(passing_readiness):
    """ReadinessMetadata should be frozen/immutable."""
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        passing_readiness.actual_stars = 9999


def test_wiki_snapshot_contract_fields():
    """WikiSnapshot should have all Core-6 sections and readiness fields."""
    section = WikiSection("summary", "markdown", False, None)
    metadata = ReadinessMetadata(
        has_12mo_history=True,
        event_count_12mo=10,
        has_release_coverage=True,
        release_count=5,
        tag_count=3,
        has_sufficient_readme=True,
        readme_length_chars=1000,
        passes_top_star_gate=True,
        min_stars_threshold=100,
        actual_stars=500,
    )

    snapshot = WikiSnapshot(
        project_external_id="github:owner/repo",
        generated_at="2026-02-15T12:00:00Z",
        what=section,
        how=section,
        architecture=section,
        activity=section,
        releases=section,
        chat=section,
        is_data_ready=True,
        hidden_sections=(),
        readiness_metadata=metadata,
    )

    # Verify all Core-6 sections exist
    assert snapshot.what == section
    assert snapshot.how == section
    assert snapshot.architecture == section
    assert snapshot.activity == section
    assert snapshot.releases == section
    assert snapshot.chat == section

    # Verify readiness fields
    assert snapshot.is_data_ready is True
    assert snapshot.hidden_sections == ()
    assert snapshot.readiness_metadata == metadata

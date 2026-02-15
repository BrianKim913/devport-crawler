"""Activity and release timeline merging with 12-month emphasis."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any


class ActivityReleaseStage:
    """Merge releases and tags into unified timeline with activity emphasis."""

    async def build_timeline(
        self,
        *,
        releases: list[dict[str, Any]],
        tags: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build merged release/tag timeline with 12-month emphasis.
        
        Args:
            releases: GitHub releases data.
            tags: GitHub tags data.
            
        Returns:
            Timeline dict with emphasis on last 12 months.
        """
        cutoff_12mo = datetime.now(UTC) - timedelta(days=365)

        # Merge and sort by date
        all_events: list[dict[str, Any]] = []
        
        for release in releases:
            published_at_str = release.get("published_at") or release.get("created_at")
            if published_at_str:
                try:
                    published_at = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))
                    all_events.append({
                        "type": "release",
                        "name": release.get("name") or release.get("tag_name", ""),
                        "version": release.get("tag_name", ""),
                        "date": published_at,
                        "is_recent": published_at > cutoff_12mo,
                        "is_major": self._is_major_milestone(release),
                        "notes": release.get("body", ""),
                    })
                except (ValueError, AttributeError):
                    pass

        for tag in tags:
            # Skip tags that are also releases (already included)
            tag_name = tag.get("name", "")
            if any(e["version"] == tag_name for e in all_events):
                continue
                
            # Add tag as timeline event
            all_events.append({
                "type": "tag",
                "name": tag_name,
                "version": tag_name,
                "date": datetime.now(UTC),  # Fallback - real impl would get commit date
                "is_recent": False,
                "is_major": False,
                "notes": "",
            })

        # Sort by date descending
        all_events.sort(key=lambda e: e["date"], reverse=True)

        # Separate recent and historical
        recent_events = [e for e in all_events if e["is_recent"]]
        all_events_list = all_events

        return {
            "recent_12mo": recent_events[:20],  # Cap at 20 for display
            "all_timeline": all_events_list,
            "major_milestones": [e for e in all_events if e["is_major"]],
            "total_releases": len([e for e in all_events if e["type"] == "release"]),
            "total_tags": len([e for e in all_events if e["type"] == "tag"]),
            "last_release_date": all_events[0]["date"].isoformat() if all_events else None,
        }

    def _is_major_milestone(self, release: dict[str, Any]) -> bool:
        """Determine if release is a major milestone.
        
        Args:
            release: GitHub release data.
            
        Returns:
            True if this is a major milestone (1.0, 2.0, etc.).
        """
        tag_name = release.get("tag_name", "")
        # Simple heuristic - check for X.0.0 pattern
        return ".0.0" in tag_name or ".0" == tag_name[-2:] if tag_name else False

"""
Wiki coverage threshold reporting for launch readiness.

Calculates top-star repository coverage meeting Core-6 completeness,
freshness windows, and section readiness. Provides pass/fail output
for launch decisioning and lists excluded repositories for follow-up.
"""

import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import Session

from app.config.database import SessionLocal
from app.models.project import Project
from app.models.project_wiki_snapshot import ProjectWikiSnapshot
from app.models.project_event import ProjectEvent


# Launch threshold configuration
LAUNCH_CONFIG = {
    "min_stars": 10000,  # Top-star threshold
    "min_coverage_percent": 75,  # Minimum % of top-star repos with complete wikis
    "required_sections": ["what", "how", "architecture", "activity", "releases"],
    "freshness_window_days": 30,  # Events must be within 30 days
    "min_section_length": 50,  # Minimum characters for section to be considered complete
}


class WikiCoverageReport:
    """Generates wiki coverage threshold report for launch readiness."""

    def __init__(self, db: Session, dry_run: bool = False):
        self.db = db
        self.dry_run = dry_run
        self.timestamp = datetime.utcnow()

    def run(self) -> Dict[str, Any]:
        """
        Execute coverage threshold analysis.
        
        Returns:
            Dict with pass/fail status, metrics, and excluded repository details
        """
        print(f"\n{'='*70}")
        print(f"WIKI COVERAGE THRESHOLD REPORT")
        print(f"Generated: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"{'='*70}\n")

        # Get top-star repositories
        top_star_repos = self._get_top_star_repositories()
        print(f"📊 Top-star repositories (>{LAUNCH_CONFIG['min_stars']:,} stars): {len(top_star_repos)}")

        # Analyze coverage
        ready_repos, not_ready_repos = self._analyze_coverage(top_star_repos)

        # Calculate metrics
        coverage_percent = (len(ready_repos) / len(top_star_repos) * 100) if top_star_repos else 0
        threshold_met = coverage_percent >= LAUNCH_CONFIG["min_coverage_percent"]

        # Print results
        self._print_summary(ready_repos, not_ready_repos, coverage_percent, threshold_met)
        self._print_ready_repos(ready_repos)
        self._print_not_ready_repos(not_ready_repos)

        # Return structured result
        return {
            "timestamp": self.timestamp.isoformat(),
            "threshold_met": threshold_met,
            "coverage_percent": round(coverage_percent, 2),
            "total_top_star_repos": len(top_star_repos),
            "ready_count": len(ready_repos),
            "not_ready_count": len(not_ready_repos),
            "ready_repos": [r["project_external_id"] for r in ready_repos],
            "not_ready_repos": [
                {
                    "project_external_id": r["project_external_id"],
                    "reasons": r["reasons"]
                }
                for r in not_ready_repos
            ]
        }

    def _get_top_star_repositories(self) -> List[Project]:
        """Get all repositories above star threshold."""
        stmt = (
            select(Project)
            .where(Project.stars >= LAUNCH_CONFIG["min_stars"])
            .order_by(Project.stars.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def _analyze_coverage(self, repos: List[Project]) -> tuple[List[Dict], List[Dict]]:
        """
        Analyze which repositories meet launch readiness criteria.
        
        Returns:
            Tuple of (ready_repos, not_ready_repos) with details
        """
        ready = []
        not_ready = []

        for repo in repos:
            reasons = self._check_readiness(repo)
            
            if not reasons:
                ready.append({
                    "project_external_id": repo.project_external_id,
                    "full_name": repo.full_name,
                    "stars": repo.stars,
                    "domain": getattr(repo, "domain", "unknown")
                })
            else:
                not_ready.append({
                    "project_external_id": repo.project_external_id,
                    "full_name": repo.full_name,
                    "stars": repo.stars,
                    "domain": getattr(repo, "domain", "unknown"),
                    "reasons": reasons
                })

        return ready, not_ready

    def _check_readiness(self, repo: Project) -> List[str]:
        """
        Check if repository meets all launch readiness criteria.
        
        Returns:
            List of reasons why repository is not ready (empty list = ready)
        """
        reasons = []

        # Check 1: Wiki snapshot exists and is data-ready
        snapshot = self._get_wiki_snapshot(repo.project_external_id)
        if not snapshot:
            reasons.append("No wiki snapshot found")
            return reasons

        if not snapshot.is_data_ready:
            reasons.append("Wiki marked as not data-ready")

        # Check 2: Core-6 sections are complete
        missing_sections = self._check_section_completeness(snapshot)
        if missing_sections:
            reasons.append(f"Missing/incomplete sections: {', '.join(missing_sections)}")

        # Check 3: Recent activity (events within freshness window)
        if not self._check_activity_freshness(repo.id):
            reasons.append(f"No activity in last {LAUNCH_CONFIG['freshness_window_days']} days")

        return reasons

    def _get_wiki_snapshot(self, project_external_id: str) -> ProjectWikiSnapshot | None:
        """Get latest wiki snapshot for project."""
        stmt = (
            select(ProjectWikiSnapshot)
            .where(ProjectWikiSnapshot.project_external_id == project_external_id)
            .order_by(ProjectWikiSnapshot.generated_at.desc())
            .limit(1)
        )
        result = self.db.execute(stmt).scalar_one_or_none()
        return result

    def _check_section_completeness(self, snapshot: ProjectWikiSnapshot) -> List[str]:
        """Check which required sections are missing or too short."""
        missing = []

        for section in LAUNCH_CONFIG["required_sections"]:
            summary_field = f"{section}_summary"
            summary = getattr(snapshot, summary_field, None)

            if not summary or len(summary) < LAUNCH_CONFIG["min_section_length"]:
                missing.append(section)

        return missing

    def _check_activity_freshness(self, project_id: int) -> bool:
        """Check if project has recent activity within freshness window."""
        freshness_cutoff = self.timestamp - timedelta(days=LAUNCH_CONFIG["freshness_window_days"])

        stmt = (
            select(func.count(ProjectEvent.id))
            .where(
                and_(
                    ProjectEvent.project_id == project_id,
                    ProjectEvent.released_at >= freshness_cutoff.date()
                )
            )
        )
        count = self.db.execute(stmt).scalar()
        return count > 0

    def _print_summary(
        self,
        ready: List[Dict],
        not_ready: List[Dict],
        coverage_percent: float,
        threshold_met: bool
    ):
        """Print coverage summary."""
        print(f"\n{'─'*70}")
        print(f"COVERAGE SUMMARY")
        print(f"{'─'*70}")
        print(f"✅ Ready repositories:     {len(ready):>3}")
        print(f"❌ Not ready repositories: {len(not_ready):>3}")
        print(f"📈 Coverage:               {coverage_percent:>6.2f}%")
        print(f"🎯 Threshold:              {LAUNCH_CONFIG['min_coverage_percent']:>6.2f}%")
        print()
        
        if threshold_met:
            print("✅ LAUNCH THRESHOLD MET")
        else:
            shortfall = LAUNCH_CONFIG["min_coverage_percent"] - coverage_percent
            repos_needed = int((shortfall / 100) * (len(ready) + len(not_ready))) + 1
            print(f"❌ LAUNCH THRESHOLD NOT MET")
            print(f"   Need {repos_needed} more ready repositories to meet threshold")

    def _print_ready_repos(self, ready: List[Dict]):
        """Print ready repositories."""
        if not ready:
            return

        print(f"\n{'─'*70}")
        print(f"READY REPOSITORIES ({len(ready)})")
        print(f"{'─'*70}")
        
        for i, repo in enumerate(ready[:10], 1):  # Show top 10
            print(f"{i:2}. {repo['full_name']:<40} ({repo['stars']:>7,} ⭐)")

        if len(ready) > 10:
            print(f"    ... and {len(ready) - 10} more")

    def _print_not_ready_repos(self, not_ready: List[Dict]):
        """Print not-ready repositories with exclusion reasons."""
        if not not_ready:
            return

        print(f"\n{'─'*70}")
        print(f"NOT READY REPOSITORIES ({len(not_ready)})")
        print(f"{'─'*70}")

        for i, repo in enumerate(not_ready[:15], 1):  # Show top 15
            print(f"\n{i:2}. {repo['full_name']} ({repo['stars']:,} ⭐)")
            for reason in repo["reasons"]:
                print(f"    ❌ {reason}")

        if len(not_ready) > 15:
            print(f"\n    ... and {len(not_ready) - 15} more not ready")


def main():
    """CLI entry point."""
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("[DRY RUN MODE - No changes will be persisted]\n")

    db = SessionLocal()
    try:
        report = WikiCoverageReport(db, dry_run=dry_run)
        result = report.run()

        print(f"\n{'='*70}\n")

        # Exit with appropriate code
        sys.exit(0 if result["threshold_met"] else 1)

    finally:
        db.close()


if __name__ == "__main__":
    main()

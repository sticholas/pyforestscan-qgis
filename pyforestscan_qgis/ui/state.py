"""Plain-Python Mission Control state models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class MissionActivity:
    """One Mission Control activity entry."""

    label: str
    detail: str = ""


@dataclass(frozen=True)
class MissionControlState:
    """Snapshot of Mission Control workflow state independent of QGIS widgets."""

    environment_status: str = "Unknown"
    latest_dataset: str | None = None
    latest_project: str | None = None
    latest_report_paths: tuple[Path, ...] = ()
    planning_status: str = "Not started"
    activities: tuple[MissionActivity, ...] = field(default_factory=tuple)

    def with_activity(self, label: str, detail: str = "", limit: int = 8) -> "MissionControlState":
        """Return a new state with a recent activity prepended."""
        next_activities = (MissionActivity(label, detail),) + self.activities
        return MissionControlState(
            environment_status=self.environment_status,
            latest_dataset=self.latest_dataset,
            latest_project=self.latest_project,
            latest_report_paths=self.latest_report_paths,
            planning_status=self.planning_status,
            activities=next_activities[:limit],
        )

    def with_environment(self, status: str) -> "MissionControlState":
        """Return a new state with environment status changed."""
        return MissionControlState(
            environment_status=status,
            latest_dataset=self.latest_dataset,
            latest_project=self.latest_project,
            latest_report_paths=self.latest_report_paths,
            planning_status=self.planning_status,
            activities=self.activities,
        )

    def with_dataset(self, dataset: str) -> "MissionControlState":
        """Return a new state with latest dataset changed."""
        return MissionControlState(
            environment_status=self.environment_status,
            latest_dataset=dataset,
            latest_project=self.latest_project,
            latest_report_paths=self.latest_report_paths,
            planning_status=self.planning_status,
            activities=self.activities,
        )

    def with_planning(self, status: str) -> "MissionControlState":
        """Return a new state with planning status changed."""
        return MissionControlState(
            environment_status=self.environment_status,
            latest_dataset=self.latest_dataset,
            latest_project=self.latest_project,
            latest_report_paths=self.latest_report_paths,
            planning_status=status,
            activities=self.activities,
        )

    def with_report_path(self, path: Path) -> "MissionControlState":
        """Return a new state with a report path recorded."""
        paths = (path,) + tuple(existing for existing in self.latest_report_paths if existing != path)
        return MissionControlState(
            environment_status=self.environment_status,
            latest_dataset=self.latest_dataset,
            latest_project=self.latest_project,
            latest_report_paths=paths[:10],
            planning_status=self.planning_status,
            activities=self.activities,
        )

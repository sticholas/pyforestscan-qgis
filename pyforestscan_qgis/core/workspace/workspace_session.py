"""Workspace session persistence models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WorkspaceSession:
    """Last-opened local user session state."""

    last_opened_workspace: Path | None = None
    last_selected_dataset: Path | None = None
    last_output_folder: Path | None = None
    last_planner_settings: dict[str, str] | None = None
    last_selected_products: tuple[str, ...] = ()
    last_page: str | None = None
    window_geometry: str | None = None
    floating: bool | None = None
    docked: bool | None = None
    remember_last_workspace: bool = True
    remember_last_dataset: bool = True
    remember_last_output_folder: bool = True
    maximum_recent_items: int = 10
    auto_save_enabled: bool = True
    open_mission_control_on_startup: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serializable session data."""
        return {
            "last_opened_workspace": str(self.last_opened_workspace) if self.last_opened_workspace else None,
            "last_selected_dataset": str(self.last_selected_dataset) if self.last_selected_dataset else None,
            "last_output_folder": str(self.last_output_folder) if self.last_output_folder else None,
            "last_planner_settings": self.last_planner_settings or {},
            "last_selected_products": list(self.last_selected_products),
            "last_page": self.last_page,
            "window_geometry": self.window_geometry,
            "floating": self.floating,
            "docked": self.docked,
            "remember_last_workspace": self.remember_last_workspace,
            "remember_last_dataset": self.remember_last_dataset,
            "remember_last_output_folder": self.remember_last_output_folder,
            "maximum_recent_items": self.maximum_recent_items,
            "auto_save_enabled": self.auto_save_enabled,
            "open_mission_control_on_startup": self.open_mission_control_on_startup,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorkspaceSession":
        """Build session state from JSON data."""
        return cls(
            last_opened_workspace=_path_or_none(payload.get("last_opened_workspace")),
            last_selected_dataset=_path_or_none(payload.get("last_selected_dataset")),
            last_output_folder=_path_or_none(payload.get("last_output_folder")),
            last_planner_settings={str(k): str(v) for k, v in (payload.get("last_planner_settings") or {}).items()},
            last_selected_products=tuple(str(item) for item in payload.get("last_selected_products", [])),
            last_page=payload.get("last_page"),
            window_geometry=payload.get("window_geometry"),
            floating=payload.get("floating"),
            docked=payload.get("docked"),
            remember_last_workspace=bool(payload.get("remember_last_workspace", True)),
            remember_last_dataset=bool(payload.get("remember_last_dataset", True)),
            remember_last_output_folder=bool(payload.get("remember_last_output_folder", True)),
            maximum_recent_items=max(1, int(payload.get("maximum_recent_items", 10))),
            auto_save_enabled=bool(payload.get("auto_save_enabled", True)),
            open_mission_control_on_startup=bool(payload.get("open_mission_control_on_startup", False)),
        )


def _path_or_none(value: object) -> Path | None:
    return Path(str(value)) if value else None

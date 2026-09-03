"""Qt 5 unscoped and Qt 6 scoped enum compatibility."""

from __future__ import annotations

from typing import Any


def qt_enum(qt: Any, name: str, scope: str) -> Any:
    """Resolve an enum member from Qt 5 or its Qt 6 scoped enum."""
    direct = getattr(qt, name, None)
    if direct is not None:
        return direct
    scoped = getattr(qt, scope, None)
    if scoped is not None and hasattr(scoped, name):
        return getattr(scoped, name)
    raise AttributeError(f"Qt enum {scope}.{name} is unavailable")


def install_enum_aliases(owner: Any, scope: str, names: tuple[str, ...]) -> None:
    """Expose Qt 6 scoped members under their Qt 5 names for legacy call sites."""
    scoped = getattr(owner, scope, None)
    if scoped is None:
        return
    for name in names:
        if not hasattr(owner, name) and hasattr(scoped, name):
            setattr(owner, name, getattr(scoped, name))


__all__ = ["install_enum_aliases", "qt_enum"]

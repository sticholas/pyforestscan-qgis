"""Small pure helpers for presenting noisy viewer telemetry consistently."""

from __future__ import annotations


class DisplayTelemetryStabilizer:
    """Publish changing display summaries only after repeated confirmation.

    Renderer telemetry is intentionally high-frequency and may describe several
    refinement stages in succession. This helper affects presentation only; it
    never changes render budgets, selection state, or commands sent to a worker.
    """

    _FIELDS = ("displayed", "budget", "quality", "detail")

    def __init__(self, confirmations=2):
        self.confirmations = max(1, int(confirmations))
        self.reset()

    def reset(self):
        self._published = {}
        self._candidate = {}
        self._count = {}

    def observe(self, telemetry):
        diagnostics = telemetry.get("render_diagnostics") or {}
        values = {
            "displayed": diagnostics.get("rendered_points", telemetry.get("displayed", 0)),
            "budget": telemetry.get("budget"),
            "quality": telemetry.get("quality", "Automatic"),
            "detail": telemetry.get("detail", "Refining"),
        }
        for key in self._FIELDS:
            value = values[key]
            if key not in self._published:
                self._published[key] = value
                continue
            if value == self._published[key]:
                self._candidate.pop(key, None)
                self._count.pop(key, None)
                continue
            if self._candidate.get(key) == value:
                self._count[key] = self._count.get(key, 1) + 1
            else:
                self._candidate[key] = value
                self._count[key] = 1
            if self._count[key] >= self.confirmations:
                self._published[key] = value
                self._candidate.pop(key, None)
                self._count.pop(key, None)
        return dict(self._published)

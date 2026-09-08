"""Feature probes: a version string is not a Python binding guarantee."""
from dataclasses import dataclass


@dataclass(frozen=True)
class QgisNativePointCloudCapabilities:
    layer_available: bool
    canvas_available: bool
    canvas_configuration: bool
    native_edit_buffer: bool
    attribute_edit: bool

    @classmethod
    def probe(cls, layer_type=None, canvas_type=None):
        has = lambda target, name: callable(getattr(target, name, None))
        return cls(
            layer_type is not None,
            canvas_type is not None,
            has(canvas_type, "setMapSettings"),
            has(layer_type, "startEditing") and has(layer_type, "rollBack"),
            has(layer_type, "changeAttributeValue"),
        )

    @property
    def native_edit_capable(self):
        return self.native_edit_buffer and self.attribute_edit

    # Capability detection never grants permission to commit a source edit.
    source_commit_allowed = False

"""Bounded journal replay. Never evaluates a predicate on edited attributes."""
from __future__ import annotations

from .session import AttributeEditOperation
from .selection import selection_mask


class EditExecutionPlan:
    def __init__(self, operations):
        import shapely
        self.operations = tuple(operations)
        self.shapes = []
        regions, owners = [], []
        for index, operation in enumerate(self.operations):
            if isinstance(operation, AttributeEditOperation):
                shapes = [shapely.Polygon(item.geometry) for item in operation.definitions]
                if any(not shape.is_valid or shape.is_empty or shape.area <= 0 for shape in shapes):
                    raise ValueError("Journal has an invalid selection polygon.")
                for shape in shapes:
                    shapely.prepare(shape)
                self.shapes.append(shapes)
                for item, shape in zip(operation.definitions, shapes):
                    if item.selection_mode != "SUBTRACT":
                        regions.append(shape.envelope)
                        owners.append(index)
            else:
                self.shapes.append(None)
                x, y, _z, xx, yy, _zz = operation.selection.bounds
                regions.append(shapely.box(x, y, xx, yy))
                owners.append(index)
        self.owners = owners
        self.tree = shapely.STRtree(regions)

    def apply(self, original):
        import numpy as np
        import shapely
        edited = original.copy()
        removed = np.zeros(len(original), dtype=bool)
        if not len(original):
            return edited, removed
        box = shapely.box(float(original["X"].min()), float(original["Y"].min()),
                          float(original["X"].max()), float(original["Y"].max()))
        relevant = sorted({self.owners[int(i)] for i in self.tree.query(box)})
        for index in relevant:
            operation = self.operations[index]
            if isinstance(operation, AttributeEditOperation):
                mask = selection_mask(original, operation.definitions, self.shapes[index])
                if operation.attribute == "DELETE_ON_EXPORT":
                    removed[mask] = bool(operation.value)
                    continue
                attribute, value = operation.attribute, operation.value
            else:
                selection = operation.selection
                mask = np.ones(len(original), dtype=bool)
                for i, dimension in enumerate(("X", "Y", "Z")):
                    mask &= (original[dimension] >= selection.bounds[i]) & (original[dimension] <= selection.bounds[i + 3])
                if selection.original_classes:
                    mask &= np.isin(original["Classification"], selection.original_classes)
                attribute, value = "Classification", operation.classification
            if attribute not in (original.dtype.names or ()):
                raise ValueError(f"Source does not contain writable {attribute}.")
            edited[attribute][mask] = value
        return edited, removed

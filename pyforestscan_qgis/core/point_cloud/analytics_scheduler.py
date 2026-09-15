"""QGIS-free coalescing and bounded-cache contracts for viewer analytics."""
from collections import OrderedDict
from dataclasses import dataclass


@dataclass(frozen=True)
class AnalyticsRequest:
    generation: int
    key: tuple
    payload: object


class AnalyticsCoalescer:
    """Keep only the newest pending analytics request and accept newest results."""
    def __init__(self):
        self.generation = 0
        self.pending = None
        self.in_flight = 0

    def submit(self, key, payload=None):
        self.generation += 1
        request = AnalyticsRequest(self.generation, tuple(key), payload)
        self.pending = request
        return request

    def take_latest(self):
        request, self.pending = self.pending, None
        if request is not None:
            self.in_flight += 1
        return request

    def finish(self, request):
        if self.in_flight:
            self.in_flight -= 1
        return request is not None and request.generation == self.generation

    def is_current(self, request):
        return request is not None and request.generation == self.generation


class BoundedAnalyticsCache:
    def __init__(self, capacity=32):
        if type(capacity) is not int or capacity < 1:
            raise ValueError("Analytics cache capacity must be positive.")
        self.capacity = capacity
        self._items = OrderedDict()

    def get(self, key):
        if key not in self._items:
            return None
        value = self._items.pop(key)
        self._items[key] = value
        return value

    def put(self, key, value):
        self._items.pop(key, None)
        self._items[key] = value
        while len(self._items) > self.capacity:
            self._items.popitem(last=False)

    def __len__(self):
        return len(self._items)

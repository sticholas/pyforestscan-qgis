"""Bounds-only acceleration over ORIGINAL LAS/LAZ record ranges.

No point attributes or reordered cache records are used as edit authority.
A full sequential pass builds the index once; queries read source record ranges.
"""
from __future__ import annotations

from contextlib import closing
import json
import math
import os
from pathlib import Path
import sqlite3
from uuid import uuid4


class RawSpatialIndex:
    SCHEMA = 1
    RECORDS_PER_BLOCK = 2048

    def __init__(self, source, root):
        if source.source_type not in ("LAS", "LAZ"):
            raise ValueError("Raw range indexing is only for LAS/LAZ.")
        self.source = source
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / (source.sha256 + ".sqlite")
        self.stamp = self._stamp()

    def _stamp(self):
        value = Path(self.source.path).stat()
        return [value.st_size, value.st_mtime_ns, value.st_ctime_ns]

    def _check(self):
        if self._stamp() != self.stamp:
            raise ValueError("Original source changed during indexed query.")

    def _connect(self):
        if self.path.is_symlink():
            raise ValueError("Source index must not be a symbolic link.")
        return sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)

    def valid(self):
        try:
            self._check()
            with closing(self._connect()) as db:
                info = json.loads(db.execute("SELECT payload FROM info").fetchone()[0])
                return (info.get("schema") == self.SCHEMA and info.get("sha256") == self.source.sha256
                        and info.get("stamp") == self.stamp and info.get("points", 0) > 0)
        except (OSError, ValueError, sqlite3.Error, TypeError):
            return False

    def ensure(self, *, cancelled=lambda: False, progress=lambda count: None):
        if self.valid():
            return
        import numpy as np
        import pdal

        temporary = self.root / (self.source.sha256 + "." + uuid4().hex + ".partial.sqlite")
        count = 0
        db = None
        try:
            db = sqlite3.connect(temporary)
            db.execute("CREATE TABLE ranges (id INTEGER PRIMARY KEY, start INTEGER NOT NULL, count INTEGER NOT NULL)")
            db.execute("CREATE VIRTUAL TABLE spatial USING rtree(id,xmin,xmax,ymin,ymax)")
            db.execute("CREATE TABLE info (payload TEXT NOT NULL)")
            pipeline = pdal.Pipeline(json.dumps([{"type": "readers.las", "filename": self.source.path}]))
            expected = int(next(iter(pipeline.quickinfo.values()))["num_points"])
            for chunk in pipeline.iterator(chunk_size=65536, prefetch=0):
                if cancelled():
                    raise InterruptedError("Source range indexing cancelled.")
                self._check()
                for offset in range(0, len(chunk), self.RECORDS_PER_BLOCK):
                    block = chunk[offset:offset+self.RECORDS_PER_BLOCK]
                    x, y = block["X"], block["Y"]
                    if not np.isfinite(x).all() or not np.isfinite(y).all():
                        raise ValueError("Non-finite original coordinates cannot be spatially indexed.")
                    row = db.execute("INSERT INTO ranges(start,count) VALUES (?,?)", (count+offset, len(block)))
                    db.execute("INSERT INTO spatial VALUES (?,?,?,?,?)",
                               (row.lastrowid, float(x.min()), float(x.max()), float(y.min()), float(y.max())))
                count += len(chunk)
                progress(count)
            self._check()
            if cancelled():
                raise InterruptedError("Source range indexing cancelled.")
            if not count:
                raise ValueError("Original source contains no points.")
            if count != expected:
                raise ValueError("Original-source index is incomplete; point count differs from the LAS header.")
            db.execute("INSERT INTO info VALUES (?)", (json.dumps({
                "schema": self.SCHEMA, "sha256": self.source.sha256, "stamp": self.stamp, "points": count}),))
            db.commit()
            db.close()
            db = None
            self._check()
            os.replace(temporary, self.path)
        finally:
            if db is not None:
                db.close()
            temporary.unlink(missing_ok=True)

    def ranges(self, envelopes):
        self._check()
        if not self.valid():
            raise ValueError("Original-source index is missing or stale.")
        candidates = {}
        with closing(self._connect()) as db:
            for xmin, ymin, xmax, ymax in envelopes:
                if not all(math.isfinite(v) for v in (xmin,ymin,xmax,ymax)) or xmin > xmax or ymin > ymax:
                    raise ValueError("Invalid original-source query bounds.")
                # RTree bounds round outwards, retaining boundary candidates.
                for start, count in db.execute(
                        "SELECT r.start,r.count FROM spatial s JOIN ranges r ON r.id=s.id "
                        "WHERE s.xmax>=? AND s.xmin<=? AND s.ymax>=? AND s.ymin<=?",
                        (xmin,xmax,ymin,ymax)):
                    candidates[start] = count
        merged = []
        for start, count in sorted(candidates.items()):
            if merged and merged[-1][0]+merged[-1][1] == start:
                merged[-1] = (merged[-1][0], merged[-1][1]+count)
            else:
                merged.append((start,count))
        return tuple(merged)

    def chunks(self, envelopes, *, cancelled=lambda: False):
        import pdal

        for start, count in self.ranges(envelopes):
            if cancelled():
                raise InterruptedError("Original-source query cancelled.")
            pipeline = pdal.Pipeline(json.dumps([{"type":"readers.las", "filename":self.source.path,
                                                  "start":start, "count":count}]))
            received = 0
            for chunk in pipeline.iterator(chunk_size=65536, prefetch=0):
                if cancelled():
                    raise InterruptedError("Original-source query cancelled.")
                self._check()
                received += len(chunk)
                if received > count:
                    raise ValueError("Original-source range reader exceeded its requested record count.")
                yield chunk
            if received != count:
                raise ValueError("Original-source range read was incomplete.")
            self._check()

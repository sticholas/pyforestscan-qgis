"""Non-destructive preparation intent; execution stays in the managed runtime."""
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path

from .session import PointCloudEditSession, SourceIdentity


@dataclass(frozen=True)
class PreparationOptions:
    thinning: str = "none"
    spacing: float | None = None
    height_action: str = "preserve"
    allow_ground_classification: bool = False

    def __post_init__(self):
        if self.thinning not in ("none", "poisson", "voxel_first"):
            raise ValueError("Choose no thinning, Poisson, or voxel-first thinning.")
        if self.thinning == "none":
            if self.spacing is not None:
                raise ValueError("Spacing requires an explicit thinning method.")
        elif type(self.spacing) not in (int, float) or not math.isfinite(self.spacing) or self.spacing <= 0:
            raise ValueError("Thinning spacing must be positive and finite in source coordinate units.")
        if self.height_action not in ("preserve", "add_hag", "normalize_z"):
            raise ValueError("Choose preserved height, added HAG, or normalized Z.")
        if type(self.allow_ground_classification) is not bool:
            raise ValueError("Ground-classification consent must be a boolean.")
        if self.allow_ground_classification and self.height_action == "preserve":
            raise ValueError("Ground classification is only available for height preparation.")
        if self.thinning == "none" and self.height_action == "preserve":
            raise ValueError("Choose at least one preparation operation.")


@dataclass(frozen=True)
class PreparationRequest:
    source: SourceIdentity
    output_path: str
    options: PreparationOptions

    def __post_init__(self):
        if not isinstance(self.source, SourceIdentity) or not isinstance(self.options, PreparationOptions):
            raise ValueError("Preparation requires immutable local source identity and validated options.")
        source = Path(self.source.path)
        output = Path(self.output_path)
        if not source.is_absolute() or not output.is_absolute():
            raise ValueError("Preparation paths must be absolute.")
        if output.suffix.lower() not in (".las", ".laz") or output.name.lower().endswith(".copc.laz"):
            raise ValueError("Publish a new LAS/LAZ; COPC export is not qualified.")
        object.__setattr__(self, "output_path", str(output))
        self.validate_destination()

    @classmethod
    def from_session(cls, session: PointCloudEditSession, output_path, options):
        if session.operations:
            raise ValueError("Export staged edits and open the validated export before preparing a derived dataset.")
        return cls(session.source, str(output_path), options)

    @property
    def provenance_path(self):
        return Path(self.output_path).with_name(Path(self.output_path).name + ".preparation.json")

    def validate_destination(self):
        """Read-only preflight; execution must repeat it and publish without replacement."""
        output = Path(self.output_path)
        source = Path(self.source.path)
        if output.resolve() == source.resolve():
            raise ValueError("Preparation must never replace its source.")
        for destination in (output, self.provenance_path):
            if destination.exists() or destination.is_symlink():
                raise ValueError("Preparation requires new output and provenance paths.")
        if not output.parent.is_dir():
            raise ValueError("Choose an existing output directory.")

    def verify_input(self, *, cancelled=lambda: False):
        """Hash verification belongs in a worker, never the UI event loop."""
        self.validate_destination()
        self.source.verify(cancelled=cancelled)

    def to_dict(self):
        return {"schema_version": 1, **asdict(self)}

    @classmethod
    def from_dict(cls, payload):
        if not isinstance(payload, dict) or set(payload) != {"schema_version", "source", "output_path", "options"}:
            raise ValueError("Invalid preparation request fields.")
        if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
            raise ValueError("Unsupported preparation request schema.")
        try:
            return cls(SourceIdentity(**payload["source"]), payload["output_path"],
                       PreparationOptions(**payload["options"]))
        except TypeError as error:
            raise ValueError("Invalid preparation request values.") from error

    @property
    def signature(self):
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True,
                                         allow_nan=False).encode("utf-8")).hexdigest()

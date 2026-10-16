"""Engineering budgets, not county limits or a transactional source guarantee."""

from dataclasses import asdict, dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class RetrievalPolicy:
    timeout_seconds: float = 30.0
    max_attempts: int = 3
    min_request_spacing: float = 1.0
    backoff_seconds: float = 1.0
    max_single_wait: float = 60.0
    max_total_wait: float = 120.0
    max_body_bytes: int = 25 * 1024 * 1024
    max_inventory_ids: int = 1_000_000

    def __post_init__(self) -> None:
        for name in ("max_attempts", "max_body_bytes", "max_inventory_ids"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        for name in (
            "timeout_seconds",
            "min_request_spacing",
            "backoff_seconds",
            "max_single_wait",
            "max_total_wait",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (float, int))
                or not isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{name} must be finite and positive")

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)

from dataclasses import dataclass
from pathlib import Path

from .retrieval import RetrievalPolicy


@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path = Path(__file__).resolve().parents[3]
    raw_dir: Path = project_root / "data" / "raw"
    processed_dir: Path = project_root / "data" / "processed"
    timeout_seconds: float = 30.0
    page_size: int = 2_000
    max_retries: int = 3
    min_request_spacing: float = 1.0
    backoff_seconds: float = 1.0
    max_single_wait: float = 60.0
    max_total_wait: float = 120.0
    max_body_bytes: int = 25 * 1024 * 1024
    max_inventory_ids: int = 1_000_000
    default_min_acres: str = "10"

    def __post_init__(self) -> None:
        if type(self.page_size) is not int or self.page_size <= 0:
            raise ValueError("page_size must be a positive integer")
        self.retrieval_policy()

    def retrieval_policy(self) -> RetrievalPolicy:
        return RetrievalPolicy(
            timeout_seconds=self.timeout_seconds,
            max_attempts=self.max_retries,
            min_request_spacing=self.min_request_spacing,
            backoff_seconds=self.backoff_seconds,
            max_single_wait=self.max_single_wait,
            max_total_wait=self.max_total_wait,
            max_body_bytes=self.max_body_bytes,
            max_inventory_ids=self.max_inventory_ids,
        )


SETTINGS = Settings()

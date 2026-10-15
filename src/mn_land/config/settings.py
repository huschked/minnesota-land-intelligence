from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path = Path(__file__).resolve().parents[3]
    raw_dir: Path = project_root / "data" / "raw"
    processed_dir: Path = project_root / "data" / "processed"
    timeout_seconds: float = 30.0
    page_size: int = 2_000
    max_retries: int = 3
    default_min_acres: str = "10"


SETTINGS = Settings()

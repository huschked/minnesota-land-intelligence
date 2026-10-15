from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from mn_land.models import Parcel


class CountyAdapter(ABC):
    def record_identifier(self, raw_record: Mapping[str, Any]) -> str | int | None:
        """Optional source-native record reference for quarantine diagnostics."""
        return None

    @abstractmethod
    def fetch_parcels(self, raw_run_dir: Path, retrieved_at: datetime) -> Iterable[Mapping[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def normalize_parcel(self, raw_record: Mapping[str, Any], retrieved_at: datetime) -> Parcel:
        raise NotImplementedError

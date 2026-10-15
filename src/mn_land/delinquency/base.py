from abc import ABC, abstractmethod

from mn_land.models import DelinquencyRecord


class DelinquencySource(ABC):
    """Independent authoritative source of delinquency assertions."""

    @abstractmethod
    def load_records(self) -> list[DelinquencyRecord]:
        raise NotImplementedError

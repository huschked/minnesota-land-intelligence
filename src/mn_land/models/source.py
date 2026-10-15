from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    agency: str
    dataset: str
    service_url: str
    layer_id: int | None
    retrieved_at: datetime
    source_fields: dict[str, str] = field(default_factory=dict)
    notes: tuple[str, ...] = ()
    publication_date: str | None = None
    source_record_id: str | None = None
    original_identifier: str | None = None
    normalized_identifier: str | None = None

    @property
    def layer_url(self) -> str:
        if self.layer_id is None:
            return self.service_url
        return f"{self.service_url.rstrip('/')}/{self.layer_id}"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["retrieved_at"] = self.retrieved_at.isoformat()
        result["notes"] = list(self.notes)
        result["layer_url"] = self.layer_url
        return result

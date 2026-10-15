from dataclasses import dataclass, fields


@dataclass(frozen=True, slots=True)
class InputLimits:
    """Engineering budgets, not limits stated by the county."""

    max_file_bytes: int = 25 * 1024 * 1024
    max_expanded_bytes: int = 100 * 1024 * 1024
    max_records: int = 100_000
    max_columns: int = 256
    max_cell_bytes: int = 1024 * 1024
    max_archive_members: int = 4096

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{item.name} must be a positive integer")


DEFAULT_INPUT_LIMITS = InputLimits()

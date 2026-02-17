from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class SozoColumnStats:
    """Statistics for a generated column."""

    type: str
    min: float | None = None
    max: float | None = None
    mean: float | None = None
    unique_count: int | None = None
    values: dict[str, int] | None = None


@dataclass
class SozoGenerateResponse:
    """Response from Sōzō generate."""

    columns: list[str]
    rows: list[dict[str, Any]]
    stats: dict[str, SozoColumnStats]

    def to_csv(self) -> str:
        """Convert rows to CSV."""

        def escape(value: Any) -> str:
            if value is None:
                return ""
            raw = str(value)
            if "," in raw or '"' in raw:
                return '"' + raw.replace('"', '""') + '"'
            return raw

        lines = [",".join(self.columns)]
        for row in self.rows:
            lines.append(",".join(escape(row.get(column)) for column in self.columns))
        return "\n".join(lines)

    def to_jsonl(self) -> str:
        """Convert rows to JSON Lines."""
        return "\n".join(json.dumps(row) for row in self.rows)

    def to_dataframe(self) -> Any:
        """Convert rows to pandas DataFrame (requires pandas extras)."""
        import pandas as pd  # type: ignore[import-untyped]

        return pd.DataFrame(self.rows)


@dataclass
class SozoSchemaInfo:
    """Info about a predefined schema."""

    name: str
    columns: dict[str, str]

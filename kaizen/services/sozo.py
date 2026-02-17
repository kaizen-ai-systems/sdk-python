from __future__ import annotations

from typing import Any

from .._types import CorrelationType
from ..errors import KaizenValidationError
from ..http import HttpClient
from ..models import SozoColumnStats, SozoGenerateResponse, SozoSchemaInfo


class SozoClient:
    """Client for Sōzō (Synthetic Data) API."""

    def __init__(self, http: HttpClient):
        self._http = http

    def generate(
        self,
        records: int,
        schema: dict[str, str] | None = None,
        schema_name: str | None = None,
        correlations: dict[str, CorrelationType] | None = None,
        seed: int | None = None,
    ) -> SozoGenerateResponse:
        if not schema and not schema_name:
            raise KaizenValidationError("Either schema or schema_name is required")

        payload: dict[str, Any] = {"records": records}
        if schema:
            payload["schema"] = schema
        if schema_name:
            payload["schemaName"] = schema_name
        if correlations:
            payload["correlations"] = correlations
        if seed is not None:
            payload["seed"] = seed

        result = self._http.post("/v1/sozo/generate", payload)

        stats: dict[str, SozoColumnStats] = {}
        for column_name, stat in result.get("stats", {}).items():
            stats[column_name] = SozoColumnStats(
                type=stat.get("type", "unknown"),
                min=stat.get("min"),
                max=stat.get("max"),
                mean=stat.get("mean"),
                unique_count=stat.get("uniqueCount"),
                values=stat.get("values"),
            )

        return SozoGenerateResponse(
            columns=result.get("columns", []),
            rows=result.get("rows", []),
            stats=stats,
        )

    def list_schemas(self) -> list[SozoSchemaInfo]:
        result = self._http.get("/v1/sozo/schemas")
        return [
            SozoSchemaInfo(name=schema["name"], columns=schema["columns"])
            for schema in result.get("schemas", [])
        ]

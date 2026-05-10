from __future__ import annotations

from typing import Any

from .._types import QueryMode, SQLDialect
from ..errors import KaizenError
from ..http import HttpClient
from ..models import (
    AkumaExplainResponse,
    AkumaInteractiveQueryResponse,
    AkumaQueryResponse,
    AkumaSchemaResponse,
    AkumaSource,
    AkumaSourceMutationResponse,
    AkumaTable,
    Guardrails,
)


class AkumaClient:
    """Client for Akuma (NL→SQL) API."""

    def __init__(self, http: HttpClient):
        self._http = http

    def query(
        self,
        dialect: SQLDialect,
        prompt: str,
        mode: QueryMode = "sql-only",
        max_rows: int | None = None,
        guardrails: Guardrails | None = None,
        source_id: str | None = None,
    ) -> AkumaQueryResponse:
        payload: dict[str, Any] = {
            "dialect": dialect,
            "prompt": prompt,
            "mode": mode,
        }
        if max_rows:
            payload["maxRows"] = max_rows
        if guardrails:
            payload["guardrails"] = guardrails.to_dict()
        if source_id:
            payload["sourceId"] = source_id

        result = self._http.post("/v1/akuma/query", payload)

        return self._parse_query_response(result)

    def query_interactive(
        self,
        dialect: SQLDialect,
        prompt: str,
        mode: QueryMode = "sql-only",
        max_rows: int | None = None,
        guardrails: Guardrails | None = None,
        source_id: str | None = None,
    ) -> AkumaInteractiveQueryResponse:
        payload: dict[str, Any] = {
            "dialect": dialect,
            "prompt": prompt,
            "mode": mode,
        }
        if max_rows is not None:
            payload["maxRows"] = max_rows
        if guardrails:
            payload["guardrails"] = guardrails.to_dict()
        if source_id:
            payload["sourceId"] = source_id

        result = self._http.post("/v1/akuma/queries/interactive", payload)

        if not isinstance(result, dict):
            raise KaizenError(
                "interactive query response must be an object",
                code="INVALID_RESPONSE",
                data={"response": result},
            )
        status = result.get("status")
        if not isinstance(status, str) or status.strip() == "":
            raise KaizenError(
                "interactive query response missing status",
                code="INVALID_RESPONSE",
                data=result,
            )
        has_query_result = "result" in result
        query_result = result.get("result")
        if has_query_result and not isinstance(query_result, dict):
            raise KaizenError(
                "interactive query response result must be an object",
                code="INVALID_RESPONSE",
                data=result,
            )
        if status in {"completed", "rejected"} and not has_query_result:
            raise KaizenError(
                "interactive query response missing result",
                code="INVALID_RESPONSE",
                data=result,
            )
        if isinstance(query_result, dict):
            query_error = query_result.get("error")
            if status == "rejected" and (
                not isinstance(query_error, str) or query_error.strip() == ""
            ):
                raise KaizenError(
                    "interactive query rejected response missing error",
                    code="INVALID_RESPONSE",
                    data=result,
                )
            if status == "completed" and isinstance(query_error, str) and query_error.strip() != "":
                raise KaizenError(
                    "interactive query completed response must not include error",
                    code="INVALID_RESPONSE",
                    data=result,
                )
        parsed_result = None
        if isinstance(query_result, dict):
            parsed_result = self._parse_query_response(query_result)

        return AkumaInteractiveQueryResponse(
            status=status,
            result=parsed_result,
            raw_response=result,
        )

    @staticmethod
    def _parse_query_response(result: dict[str, Any]) -> AkumaQueryResponse:
        return AkumaQueryResponse(
            sql=result.get("sql", ""),
            rows=result.get("rows"),
            explanation=result.get("explanation"),
            tables=result.get("tables"),
            warnings=result.get("warnings"),
            error=result.get("error"),
        )

    def explain(self, sql: str) -> AkumaExplainResponse:
        result = self._http.post("/v1/akuma/explain", {"sql": sql})
        return AkumaExplainResponse(
            sql=result.get("sql", sql),
            explanation=result.get("explanation", ""),
        )

    def set_schema(
        self,
        tables: list[AkumaTable],
        dialect: SQLDialect,
        version: str | None = None,
        name: str | None = None,
        source_id: str | None = None,
    ) -> AkumaSchemaResponse:
        payload: dict[str, Any] = {
            "dialect": dialect,
            "tables": [table.to_dict() for table in tables],
        }
        if version:
            payload["version"] = version
        if name:
            payload["name"] = name
        if source_id:
            payload["sourceId"] = source_id

        result = self._http.post("/v1/akuma/schema", payload)
        return _parse_source_mutation(result)

    def list_sources(self) -> list[AkumaSource]:
        result = self._http.get("/v1/akuma/sources")
        return [_parse_source(item) for item in result.get("sources", [])]

    def create_source(
        self,
        name: str,
        dialect: str,
        connection_string: str,
        target_schemas: list[str] | None = None,
    ) -> AkumaSourceMutationResponse:
        payload: dict[str, Any] = {
            "name": name,
            "dialect": dialect,
            "connectionString": connection_string,
        }
        if target_schemas:
            payload["targetSchemas"] = target_schemas
        result = self._http.post("/v1/akuma/sources", payload)
        return _parse_source_mutation(result)

    def delete_source(self, source_id: str) -> AkumaSourceMutationResponse:
        result = self._http.request("DELETE", f"/v1/akuma/sources/{source_id}")
        return _parse_source_mutation(result)

    def sync_source(self, source_id: str) -> AkumaSourceMutationResponse:
        result = self._http.post(f"/v1/akuma/sources/{source_id}/sync", {})
        return _parse_source_mutation(result)


def _parse_source(result: dict[str, Any]) -> AkumaSource:
    return AkumaSource(
        id=result.get("id", ""),
        name=result.get("name", ""),
        dialect=result.get("dialect", ""),
        is_manual=bool(result.get("isManual", False)),
        target_schemas=list(result.get("targetSchemas", []) or []),
        status=result.get("status", ""),
        created_at=result.get("createdAt", ""),
        updated_at=result.get("updatedAt", ""),
        last_error=result.get("lastError"),
        last_synced_at=result.get("lastSyncedAt"),
    )


def _parse_source_mutation(result: dict[str, Any]) -> AkumaSourceMutationResponse:
    source_payload = result.get("source")
    source = _parse_source(source_payload) if isinstance(source_payload, dict) else None
    return AkumaSourceMutationResponse(
        status=result.get("status", ""),
        source_id=result.get("sourceId"),
        tables=result.get("tables"),
        source=source,
    )

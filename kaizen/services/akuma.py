from __future__ import annotations

from typing import Any

from .._types import QueryMode, SQLDialect
from ..errors import KaizenError
from ..http import HttpClient
from ..models import (
    AkumaClarification,
    AkumaClarificationOption,
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
        """Run a fresh query through the interactive Akuma protocol.

        To consume a needs_clarification response, use `consume_clarification`.
        """
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
        return self._parse_interactive_response(result)

    def consume_clarification(
        self,
        clarification_token: str,
        option_id: str,
        idempotency_key: str,
    ) -> AkumaInteractiveQueryResponse:
        """Consume a previously-issued clarification by selecting an option.

        `idempotency_key` is required and is sent as the Idempotency-Key
        header. First successful consume wins; same-key retries replay the
        persisted result; different-key retries are rejected with a 409
        KaizenError.
        """
        if not isinstance(clarification_token, str) or clarification_token.strip() == "":
            raise KaizenError(
                "clarification_token is required", code="INVALID_REQUEST"
            )
        if not isinstance(option_id, str) or option_id.strip() == "":
            raise KaizenError("option_id is required", code="INVALID_REQUEST")
        if not isinstance(idempotency_key, str) or idempotency_key.strip() == "":
            raise KaizenError(
                "idempotency_key is required for consume", code="INVALID_REQUEST"
            )
        body = {
            "clarificationToken": clarification_token,
            "optionId": option_id,
        }
        result = self._http.request(
            "POST",
            "/v1/akuma/queries/interactive",
            body,
            extra_headers={"Idempotency-Key": idempotency_key},
        )
        return self._parse_interactive_response(result)

    def _parse_interactive_response(self, result: Any) -> AkumaInteractiveQueryResponse:
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
        has_clarification = "clarification" in result
        clarification_payload = result.get("clarification")
        if has_clarification and not isinstance(clarification_payload, dict):
            raise KaizenError(
                "interactive query response clarification must be an object",
                code="INVALID_RESPONSE",
                data=result,
            )
        parsed_clarification: AkumaClarification | None = None
        if status == "needs_clarification":
            if not has_clarification or not isinstance(clarification_payload, dict):
                raise KaizenError(
                    "interactive query needs_clarification response missing clarification",
                    code="INVALID_RESPONSE",
                    data=result,
                )
            parsed_clarification = self._parse_clarification(clarification_payload, raw=result)
        # For non-needs_clarification statuses, intentionally skip strict
        # parsing of any clarification payload. The raw dict is already on
        # `raw_response` for callers that want to inspect it; running
        # _parse_clarification on a forward-compat status that ships a
        # permissively-shaped clarification would raise INVALID_RESPONSE
        # spuriously (Gemini round-3 F2; Go and TS SDKs already
        # short-circuit the same way).

        return AkumaInteractiveQueryResponse(
            status=status,
            result=parsed_result,
            clarification=parsed_clarification,
            raw_response=result,
        )

    @staticmethod
    def _parse_clarification(payload: dict[str, Any], raw: dict[str, Any]) -> AkumaClarification:
        token = payload.get("clarificationToken")
        if not isinstance(token, str) or token.strip() == "":
            raise KaizenError(
                "interactive query needs_clarification response missing clarificationToken",
                code="INVALID_RESPONSE",
                data=raw,
            )
        question = payload.get("question")
        if not isinstance(question, str) or question.strip() == "":
            raise KaizenError(
                "interactive query needs_clarification response missing question",
                code="INVALID_RESPONSE",
                data=raw,
            )
        options_raw = payload.get("options")
        if not isinstance(options_raw, list) or len(options_raw) < 2 or len(options_raw) > 4:
            raise KaizenError(
                "interactive query needs_clarification response requires 2-4 options",
                code="INVALID_RESPONSE",
                data=raw,
            )
        options: list[AkumaClarificationOption] = []
        for entry in options_raw:
            if not isinstance(entry, dict):
                raise KaizenError(
                    "interactive query needs_clarification option must be an object",
                    code="INVALID_RESPONSE",
                    data=raw,
                )
            opt_id = entry.get("id")
            opt_label = entry.get("label")
            if not isinstance(opt_id, str) or opt_id.strip() == "":
                raise KaizenError(
                    "interactive query needs_clarification option missing id",
                    code="INVALID_RESPONSE",
                    data=raw,
                )
            if not isinstance(opt_label, str) or opt_label.strip() == "":
                raise KaizenError(
                    "interactive query needs_clarification option missing label",
                    code="INVALID_RESPONSE",
                    data=raw,
                )
            opt_description_raw = entry.get("description")
            opt_description: str | None = None
            if isinstance(opt_description_raw, str) and opt_description_raw != "":
                opt_description = opt_description_raw
            options.append(
                AkumaClarificationOption(
                    id=opt_id,
                    label=opt_label,
                    description=opt_description,
                )
            )
        expires_at = payload.get("expiresAt")
        if not isinstance(expires_at, str) or expires_at.strip() == "":
            raise KaizenError(
                "interactive query needs_clarification response missing expiresAt",
                code="INVALID_RESPONSE",
                data=raw,
            )
        return AkumaClarification(
            clarification_token=token,
            question=question,
            options=options,
            expires_at=expires_at,
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

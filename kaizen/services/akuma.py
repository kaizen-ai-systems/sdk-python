from __future__ import annotations

from typing import Any
from urllib.parse import quote

from .._types import QueryMode, SQLDialect
from ..errors import KaizenError
from ..http import HttpClient
from ..models import (
    AkumaClarification,
    AkumaClarificationOption,
    AkumaCreateMetricDefinitionResponse,
    AkumaExplainResponse,
    AkumaForgetMetricDefinitionResponse,
    AkumaInteractiveQueryResponse,
    AkumaListMetricDefinitionsResponse,
    AkumaMetric,
    AkumaMetricActive,
    AkumaMetricCandidate,
    AkumaMetricDefinition,
    AkumaMetricDefinitionRestoreRequest,
    AkumaMetricDefinitionTokenRequest,
    AkumaMetricFieldStatus,
    AkumaMetricFilter,
    AkumaMetricMonth,
    AkumaMetricReadBack,
    AkumaMetricReadBackField,
    AkumaMetricRecipe,
    AkumaProvenance,
    AkumaProvenanceAggregations,
    AkumaProvenanceFilter,
    AkumaProvenanceJoin,
    AkumaProvenanceProjection,
    AkumaProvenanceWarning,
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
        metric_action: str | None = None,
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

        if metric_action is not None:
            payload["metricAction"] = metric_action

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

        # PR 1c: provenance is defined only for completed results; the same
        # forward-compat scoping applies — strictly require an object shape only
        # on `completed`, and leave the raw payload on `raw_response` for any
        # other status.
        parsed_provenance: AkumaProvenance | None = None
        if status == "completed":
            provenance_payload = result.get("provenance")
            if provenance_payload is not None:
                if not isinstance(provenance_payload, dict):
                    raise KaizenError(
                        "interactive query response provenance must be an object",
                        code="INVALID_RESPONSE",
                        data=result,
                    )
                # provenanceFidelity is the load-bearing field — without it a
                # client cannot tell full from limited provenance.
                fidelity = provenance_payload.get("provenanceFidelity")
                if not isinstance(fidelity, str) or fidelity.strip() == "":
                    raise KaizenError(
                        "interactive query response provenance missing provenanceFidelity",
                        code="INVALID_RESPONSE",
                        data=result,
                    )
                parsed_provenance = self._parse_provenance(provenance_payload)

        parsed_metric = None
        if (
            status in {"completed", "rejected", "needs_clarification"}
            and result.get("metric") is not None
        ):
            try:
                parsed_metric = _parse_metric(result["metric"])
            except (KeyError, TypeError, ValueError, AttributeError) as error:
                raise _metric_response_error(result) from error

        return AkumaInteractiveQueryResponse(
            status=status,
            result=parsed_result,
            clarification=parsed_clarification,
            provenance=parsed_provenance,
            raw_response=result,
            metric=parsed_metric,
        )

    @staticmethod
    def _parse_provenance(payload: dict[str, Any]) -> AkumaProvenance:
        """Map the camelCase wire provenance onto snake_case dataclasses.

        Absent arrays normalize to empty; PRESENT contents must be well-typed
        and fail closed otherwise — parity with the Go SDK, whose typed
        unmarshal rejects off-type fields (Claude round-3 F2). Missing scalar
        fields map to Go's zero values ("" / None); present-but-mistyped
        scalars fail closed.
        """

        def malformed(detail: str) -> KaizenError:
            return KaizenError(
                f"interactive query response provenance malformed: {detail}",
                code="INVALID_RESPONSE",
                data=payload,
            )

        def str_list(field: str, value: Any) -> list[str]:
            if value is None:
                return []
            if not isinstance(value, list):
                raise malformed(f"{field} must be an array")
            for item in value:
                if not isinstance(item, str):
                    raise malformed(f"{field} entries must be strings")
            return list(value)

        def obj_list(field: str, value: Any) -> list[dict[str, Any]]:
            if value is None:
                return []
            if not isinstance(value, list):
                raise malformed(f"{field} must be an array")
            for item in value:
                if not isinstance(item, dict):
                    raise malformed(f"{field} entries must be objects")
            return list(value)

        def str_field(field: str, entry: dict[str, Any], key: str) -> str:
            value = entry.get(key)
            if value is None:
                return ""
            if not isinstance(value, str):
                raise malformed(f"{field}.{key} must be a string")
            return value

        def opt_str_field(field: str, entry: dict[str, Any], key: str) -> str | None:
            value = entry.get(key)
            if value is None:
                return None
            if not isinstance(value, str):
                raise malformed(f"{field}.{key} must be a string")
            return value

        # The caller has already validated provenanceFidelity is a non-empty
        # string (fail-closed); no silent default here (Claude round-2 L6).
        fidelity = str_field("provenance", payload, "provenanceFidelity")
        dialect = str_field("provenance", payload, "dialect")

        joins = [
            AkumaProvenanceJoin(
                type=str_field("joins", entry, "type"),
                left=opt_str_field("joins", entry, "left"),
                right=opt_str_field("joins", entry, "right"),
                condition=opt_str_field("joins", entry, "condition"),
            )
            for entry in obj_list("joins", payload.get("joins"))
        ]
        filters = [
            AkumaProvenanceFilter(
                clause=str_field("filters", entry, "clause"),
                expression=str_field("filters", entry, "expression"),
            )
            for entry in obj_list("filters", payload.get("filters"))
        ]
        projections = [
            AkumaProvenanceProjection(
                expression=str_field("projections", entry, "expression"),
                alias=opt_str_field("projections", entry, "alias"),
            )
            for entry in obj_list("projections", payload.get("projections"))
        ]
        warnings = [
            AkumaProvenanceWarning(
                category=str_field("warnings", entry, "category"),
                detail=opt_str_field("warnings", entry, "detail"),
            )
            for entry in obj_list("warnings", payload.get("warnings"))
        ]
        agg_raw = payload.get("aggregations")
        if agg_raw is not None and not isinstance(agg_raw, dict):
            raise malformed("aggregations must be an object")
        agg = agg_raw or {}
        aggregations = AkumaProvenanceAggregations(
            group_by=str_list("aggregations.groupBy", agg.get("groupBy")),
            functions=str_list("aggregations.functions", agg.get("functions")),
        )
        return AkumaProvenance(
            provenance_fidelity=fidelity,
            dialect=dialect,
            tables=str_list("tables", payload.get("tables")),
            joins=joins,
            filters=filters,
            projections=projections,
            aggregations=aggregations,
            warnings=warnings,
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
        candidates = None
        if payload.get("kind") == "metric_proposal":
            try:
                entries = payload["metricCandidates"]
                if not isinstance(entries, list):
                    raise ValueError("metricCandidates must be an array")
                candidates = [_parse_metric_candidate(entry) for entry in entries]
            except (KeyError, TypeError, ValueError, AttributeError) as error:
                raise _metric_response_error(raw) from error
        return AkumaClarification(
            clarification_token=token,
            question=question,
            options=options,
            expires_at=expires_at,
            kind=payload.get("kind"),
            metric_candidates=candidates,
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

    def create_metric_definition(
        self,
        request: AkumaMetricDefinitionTokenRequest | AkumaMetricDefinitionRestoreRequest,
        idempotency_key: str,
    ) -> AkumaCreateMetricDefinitionResponse:
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise KaizenError("idempotency_key is required", code="INVALID_REQUEST")
        result = self._http.request(
            "POST", "/v1/akuma/metric-definitions", request.to_dict(),
            extra_headers={"Idempotency-Key": idempotency_key},
        )
        try:
            superseded = result["supersededVersion"]
            if superseded is not None:
                superseded = _metric_version(superseded)
            return AkumaCreateMetricDefinitionResponse(
                definition=_parse_metric_definition(result["definition"]),
                superseded_version=superseded,
            )
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise _metric_response_error(result) from error

    def list_metric_definitions(self, source_id: str) -> AkumaListMetricDefinitionsResponse:
        result = self._http.get(
            "/v1/akuma/metric-definitions?sourceId=" + quote(source_id, safe="")
        )
        try:
            entries = result["definitions"]
            if not isinstance(entries, list):
                raise ValueError("definitions must be an array")
            return AkumaListMetricDefinitionsResponse(
                definitions=[_parse_metric_definition(item) for item in entries]
            )
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise _metric_response_error(result) from error

    def forget_metric_definition(self, definition_id: str) -> AkumaForgetMetricDefinitionResponse:
        result = self._http.request(
            "DELETE", "/v1/akuma/metric-definitions/" + quote(definition_id, safe="")
        )
        try:
            return AkumaForgetMetricDefinitionResponse(
                definition=_parse_metric_definition(result["definition"])
            )
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise _metric_response_error(result) from error

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
        admission_mode=result.get("admissionMode"),
        above_cap=result.get("aboveCap"),
        table_count_visible=result.get("tableCountVisible"),
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



def _metric_response_error(raw: Any) -> KaizenError:
    return KaizenError(
        "metric response malformed", code="INVALID_RESPONSE",
        data=raw if isinstance(raw, dict) else {"response": raw},
    )


def _metric_string(payload: dict[str, Any], key: str, *, identifier: bool = False) -> str:
    value = payload[key]
    if not isinstance(value, str) or not value or (not identifier and not value.strip()):
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _metric_version(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("version must be a positive integer")
    return value


def _parse_metric_field_status(payload: dict[str, Any]) -> AkumaMetricFieldStatus:
    return AkumaMetricFieldStatus(
        table=_metric_string(payload, "table"), measure=_metric_string(payload, "measure"),
        date=_metric_string(payload, "date"), filter=_metric_string(payload, "filter"),
    )


def _parse_metric_recipe(payload: dict[str, Any]) -> AkumaMetricRecipe:
    metric_filter = payload["filter"]
    parsed_filter = None
    if metric_filter is not None:
        if not isinstance(metric_filter, dict) or not isinstance(metric_filter.get("keep"), bool):
            raise ValueError("filter must be null or a column and boolean keep")
        parsed_filter = AkumaMetricFilter(
            column=_metric_string(metric_filter, "column", identifier=True),
            keep=metric_filter["keep"],
        )
    return AkumaMetricRecipe(
        table=_metric_string(payload, "table", identifier=True),
        measure=_metric_string(payload, "measure", identifier=True),
        date_column=_metric_string(payload, "dateColumn", identifier=True), filter=parsed_filter,
    )


def _parse_metric_candidate(payload: dict[str, Any]) -> AkumaMetricCandidate:
    saved = payload.get("savedVersion")
    return AkumaMetricCandidate(
        option_id=_metric_string(payload, "optionId"),
        recipe=_parse_metric_recipe(payload["recipe"]),
        field_status=_parse_metric_field_status(payload["fieldStatus"]),
        saved_version=_metric_version(saved) if saved is not None else None,
    )


def _parse_metric_definition(payload: dict[str, Any]) -> AkumaMetricDefinition:
    return AkumaMetricDefinition(
        id=_metric_string(payload, "id"), term=_metric_string(payload, "term"),
        version=_metric_version(payload["version"]),
        created_at=_metric_string(payload, "createdAt"),
        recipe=_parse_metric_recipe(payload["recipe"]),
        field_status=_parse_metric_field_status(payload["fieldStatus"]),
    )


def _parse_metric(payload: dict[str, Any]) -> AkumaMetric:
    if not isinstance(payload, dict) or not isinstance(payload.get("applied"), bool):
        raise ValueError("metric requires boolean applied")
    if payload["applied"]:
        for field in [
            "term", "origin", "recipeDigest", "sqlDigest", "computedAt", "status",
            "checkedAt", "canonicalPrompt",
        ]:
            _metric_string(payload, field)
        for field in ["recipe", "month", "readBack", "activeAtCompletion"]:
            if field not in payload or (
                field != "activeAtCompletion" and not isinstance(payload[field], dict)
            ):
                raise ValueError(f"metric requires {field}")
    else:
        _metric_string(payload, "reason")
    for field in [
        "reason", "detail", "term", "definitionId", "origin", "recipeDigest", "sqlDigest",
        "computedAt", "status", "checkedAt", "canonicalPrompt",
    ]:
        if payload.get(field) is not None:
            _metric_string(payload, field)
    month = payload.get("month")
    parsed_month = None
    if month is not None:
        parsed_month = AkumaMetricMonth(
            _metric_string(month, "label"), _metric_string(month, "start"),
            _metric_string(month, "endExclusive"),
        )
    active = payload.get("activeAtCompletion")
    parsed_active = None
    if active is not None:
        parsed_active = AkumaMetricActive(
            id=_metric_string(active, "id"), version=_metric_version(active["version"]),
            recipe_digest=_metric_string(active, "recipeDigest"),
        )
    read_back = payload.get("readBack")
    parsed_read_back = None
    if read_back is not None:
        for field in ["fields", "checked", "notVerified"]:
            if not isinstance(read_back[field], list):
                raise ValueError(f"readBack.{field} must be an array")
        for field in ["checked", "notVerified"]:
            if not all(isinstance(item, str) for item in read_back[field]):
                raise ValueError(f"readBack.{field} entries must be strings")
        parsed_read_back = AkumaMetricReadBack(
            fields=[AkumaMetricReadBackField(
                field=_metric_string(item, "field"),
                value=_metric_string(
                    item, "value", identifier=item["field"] in ("table", "measure", "date"),
                ),
                status=_metric_string(item, "status"),
            ) for item in read_back["fields"]],
            checked=read_back["checked"], not_verified=read_back["notVerified"],
        )
    recipe = payload.get("recipe")
    version = payload.get("version")
    return AkumaMetric(
        applied=payload["applied"], reason=payload.get("reason"), detail=payload.get("detail"),
        term=payload.get("term"), definition_id=payload.get("definitionId"),
        version=_metric_version(version) if version is not None else None,
        origin=payload.get("origin"),
        recipe=_parse_metric_recipe(recipe) if recipe is not None else None,
        recipe_digest=payload.get("recipeDigest"), sql_digest=payload.get("sqlDigest"),
        month=parsed_month, read_back=parsed_read_back,
        computed_at=payload.get("computedAt"), status=payload.get("status"),
        active_at_completion=parsed_active,
        checked_at=payload.get("checkedAt"), canonical_prompt=payload.get("canonicalPrompt"),
    )

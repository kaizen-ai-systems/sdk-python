"""
Kaizen SDK - Official Python SDK for Kaizen AI Systems
Products: Akuma (NL→SQL) | Enzan (GPU Cost) | Sōzō (Synthetic Data)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Literal, Optional

import httpx

__version__ = "1.0.0"
__all__ = [
    "KaizenClient",
    "AkumaClient",
    "EnzanClient",
    "SozoClient",
    "akuma",
    "enzan",
    "sozo",
    "set_api_key",
    "set_base_url",
    "KaizenError",
    "KaizenAuthError",
    "KaizenRateLimitError",
]

# =============================================================================
# TYPES
# =============================================================================

SQLDialect = Literal[
    "postgres",
    "mysql",
    "snowflake",
    "bigquery",
    "sqlite",
    "redshift",
    "clickhouse",
]
QueryMode = Literal["sql-only", "sql-and-results", "explain"]
TimeWindow = Literal["1h", "24h", "7d", "30d"]
GroupByDimension = Literal["project", "model", "team", "provider", "endpoint"]
AlertType = Literal["cost_threshold", "usage_spike", "idle_resource", "budget_exceeded"]
CorrelationType = Literal["positive", "negative"]


@dataclass
class Guardrails:
    """Security guardrails for Akuma queries."""
    read_only: bool = True
    allow_tables: Optional[list[str]] = None
    deny_tables: Optional[list[str]] = None
    deny_columns: Optional[list[str]] = None
    max_rows: Optional[int] = None
    timeout_secs: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        d = {"readOnly": self.read_only}
        if self.allow_tables:
            d["allowTables"] = self.allow_tables
        if self.deny_tables:
            d["denyTables"] = self.deny_tables
        if self.deny_columns:
            d["denyColumns"] = self.deny_columns
        if self.max_rows:
            d["maxRows"] = self.max_rows
        if self.timeout_secs:
            d["timeoutSecs"] = self.timeout_secs
        return d


@dataclass
class AkumaQueryResponse:
    """Response from Akuma query."""
    sql: str
    rows: Optional[list[dict[str, Any]]] = None
    explanation: Optional[str] = None
    tables: Optional[list[str]] = None
    warnings: Optional[list[str]] = None
    error: Optional[str] = None


@dataclass
class AkumaExplainResponse:
    """Response from Akuma explain."""
    sql: str
    explanation: str


@dataclass
class EnzanSummaryRow:
    """Row in Enzan summary."""
    cost_usd: float
    gpu_hours: float
    requests: int
    tokens_in: int
    tokens_out: int
    project: Optional[str] = None
    model: Optional[str] = None
    team: Optional[str] = None
    provider: Optional[str] = None


@dataclass
class EnzanSummaryResponse:
    """Response from Enzan summary."""
    window: str
    start_time: str
    end_time: str
    rows: list[EnzanSummaryRow]
    total_cost_usd: float
    total_gpu_hours: float
    total_requests: int


@dataclass
class EnzanResource:
    """GPU resource for Enzan tracking."""
    id: str
    provider: str
    gpu_type: str
    gpu_count: int
    hourly_rate: float
    region: Optional[str] = None
    labels: Optional[dict[str, str]] = None


@dataclass
class EnzanAlert:
    """Alert configuration for Enzan."""
    id: str
    name: str
    type: AlertType
    threshold: float
    window: str
    enabled: bool = True


@dataclass
class SozoColumnStats:
    """Statistics for a generated column."""
    type: str
    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None
    unique_count: Optional[int] = None
    values: Optional[dict[str, int]] = None


@dataclass
class SozoGenerateResponse:
    """Response from Sōzō generate."""
    columns: list[str]
    rows: list[dict[str, Any]]
    stats: dict[str, SozoColumnStats]

    def to_csv(self) -> str:
        """Convert to CSV string."""
        def escape(v: Any) -> str:
            if v is None:
                return ""
            s = str(v)
            if "," in s or '"' in s:
                return f'"{s.replace(chr(34), chr(34)+chr(34))}"'
            return s

        lines = [",".join(self.columns)]
        for row in self.rows:
            lines.append(",".join(escape(row.get(c)) for c in self.columns))
        return "\n".join(lines)

    def to_jsonl(self) -> str:
        """Convert to JSON Lines string."""
        return "\n".join(json.dumps(row) for row in self.rows)

    def to_dataframe(self):
        """Convert to pandas DataFrame (requires pandas)."""
        import pandas as pd
        return pd.DataFrame(self.rows)


@dataclass
class SozoSchemaInfo:
    """Info about a predefined schema."""
    name: str
    columns: dict[str, str]


# =============================================================================
# ERRORS
# =============================================================================

class KaizenError(Exception):
    """Base exception for Kaizen SDK."""
    def __init__(self, message: str, status: Optional[int] = None, code: Optional[str] = None):
        super().__init__(message)
        self.status = status
        self.code = code


class KaizenAuthError(KaizenError):
    """Authentication error."""
    def __init__(self, message: str = "Invalid or missing API key"):
        super().__init__(message, 401, "AUTH_ERROR")


class KaizenRateLimitError(KaizenError):
    """Rate limit exceeded."""
    def __init__(self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None):
        super().__init__(message, 429, "RATE_LIMIT")
        self.retry_after = retry_after


class KaizenValidationError(KaizenError):
    """Validation error."""
    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(message, 400, "VALIDATION_ERROR")
        self.field = field


# =============================================================================
# HTTP CLIENT
# =============================================================================

class HttpClient:
    """HTTP client for API requests."""

    def __init__(
        self,
        base_url: str = "https://api.kaizenaisystems.com",
        api_key: str = "",
        timeout: float = 30.0,
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout

    def set_api_key(self, key: str) -> None:
        self.api_key = key

    def set_base_url(self, url: str) -> None:
        self.base_url = url

    def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.request(method, url, headers=headers, json=json_data)
                data = response.json()

                if response.status_code == 401:
                    raise KaizenAuthError(data.get("error", "Authentication failed"))
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    raise KaizenRateLimitError(
                        data.get("error", "Rate limit exceeded"),
                        int(retry_after) if retry_after else None,
                    )
                if response.status_code >= 400:
                    raise KaizenError(data.get("error", "Request failed"), response.status_code)

                return data
        except httpx.RequestError as e:
            raise KaizenError(f"Request failed: {e}")

    def get(self, path: str) -> dict[str, Any]:
        return self._request("GET", path)

    def post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, data)


# =============================================================================
# AKUMA CLIENT
# =============================================================================

class AkumaClient:
    """Client for Akuma (NL→SQL) API."""

    def __init__(self, http: HttpClient):
        self._http = http

    def query(
        self,
        dialect: SQLDialect,
        prompt: str,
        mode: QueryMode = "sql-only",
        max_rows: Optional[int] = None,
        guardrails: Optional[Guardrails] = None,
    ) -> AkumaQueryResponse:
        """
        Translate natural language to SQL.

        Args:
            dialect: Database dialect (postgres, mysql, snowflake, bigquery, sqlite)
            prompt: Natural language query
            mode: Query mode (sql-only, sql-and-results, explain)
            max_rows: Maximum rows to return
            guardrails: Security guardrails

        Returns:
            AkumaQueryResponse with generated SQL and optional results

        Example:
            >>> response = akuma.query(
            ...     dialect="postgres",
            ...     prompt="Top 10 customers by MRR",
            ...     mode="sql-and-results",
            ...     guardrails=Guardrails(read_only=True)
            ... )
            >>> print(response.sql)
        """
        data: dict[str, Any] = {
            "dialect": dialect,
            "prompt": prompt,
            "mode": mode,
        }
        if max_rows:
            data["maxRows"] = max_rows
        if guardrails:
            data["guardrails"] = guardrails.to_dict()

        result = self._http.post("/v1/akuma/query", data)

        return AkumaQueryResponse(
            sql=result.get("sql", ""),
            rows=result.get("rows"),
            explanation=result.get("explanation"),
            tables=result.get("tables"),
            warnings=result.get("warnings"),
            error=result.get("error"),
        )

    def explain(self, sql: str) -> AkumaExplainResponse:
        """
        Explain a SQL query in plain English.

        Args:
            sql: SQL query to explain

        Returns:
            AkumaExplainResponse with explanation

        Example:
            >>> response = akuma.explain("SELECT * FROM users WHERE active = true")
            >>> print(response.explanation)
        """
        result = self._http.post("/v1/akuma/explain", {"sql": sql})
        return AkumaExplainResponse(
            sql=result.get("sql", sql),
            explanation=result.get("explanation", ""),
        )


# =============================================================================
# ENZAN CLIENT
# =============================================================================

class EnzanClient:
    """Client for Enzan (GPU Cost) API."""

    def __init__(self, http: HttpClient):
        self._http = http

    def summary(
        self,
        window: TimeWindow = "24h",
        group_by: Optional[list[GroupByDimension]] = None,
        filters: Optional[dict[str, list[str]]] = None,
    ) -> EnzanSummaryResponse:
        """
        Get GPU cost summary for a time window.

        Args:
            window: Time window (1h, 24h, 7d, 30d)
            group_by: Dimensions to group by (project, model, team, provider)
            filters: Filters to apply

        Returns:
            EnzanSummaryResponse with cost breakdown

        Example:
            >>> summary = enzan.summary(window="24h", group_by=["project", "model"])
            >>> print(f"Total: ${summary.total_cost_usd:.2f}")
        """
        data: dict[str, Any] = {"window": window}
        if group_by:
            data["groupBy"] = group_by
        if filters:
            data["filters"] = filters

        result = self._http.post("/v1/enzan/summary", data)
        rows = [
            EnzanSummaryRow(
                cost_usd=r.get("cost_usd", 0),
                gpu_hours=r.get("gpu_hours", 0),
                requests=r.get("requests", 0),
                tokens_in=r.get("tokens_in", 0),
                tokens_out=r.get("tokens_out", 0),
                project=r.get("project"),
                model=r.get("model"),
                team=r.get("team"),
                provider=r.get("provider"),
            )
            for r in result.get("rows", [])
        ]
        total = result.get("total", {})
        return EnzanSummaryResponse(
            window=result.get("window", window),
            start_time=result.get("startTime", ""),
            end_time=result.get("endTime", ""),
            rows=rows,
            total_cost_usd=total.get("cost_usd", 0),
            total_gpu_hours=total.get("gpu_hours", 0),
            total_requests=total.get("requests", 0),
        )

    def burn(self) -> dict[str, Any]:
        """
        Get current burn rate.

        Returns:
            Dict with burn_rate_usd_per_hour and timestamp

        Example:
            >>> burn = enzan.burn()
            >>> print(f"Burn rate: ${burn['burn_rate_usd_per_hour']:.2f}/hr")
        """
        return self._http.get("/v1/enzan/burn")

    def list_resources(self) -> list[EnzanResource]:
        """List registered GPU resources."""
        result = self._http.get("/v1/enzan/resources")
        return [
            EnzanResource(
                id=r["id"],
                provider=r["provider"],
                gpu_type=r["gpuType"],
                gpu_count=r["gpuCount"],
                hourly_rate=r["hourlyRate"],
                region=r.get("region"),
                labels=r.get("labels"),
            )
            for r in result.get("resources", [])
        ]

    def register_resource(self, resource: EnzanResource) -> dict[str, str]:
        """
        Register a GPU resource for tracking.

        Example:
            >>> enzan.register_resource(EnzanResource(
            ...     id="gpu-001",
            ...     provider="aws",
            ...     gpu_type="a100_80gb",
            ...     gpu_count=8,
            ...     hourly_rate=32.77,
            ...     labels={"project": "ml-training"}
            ... ))
        """
        data = {
            "id": resource.id,
            "provider": resource.provider,
            "gpuType": resource.gpu_type,
            "gpuCount": resource.gpu_count,
            "hourlyRate": resource.hourly_rate,
        }
        if resource.region:
            data["region"] = resource.region
        if resource.labels:
            data["labels"] = resource.labels
        return self._http.post("/v1/enzan/resources", data)

    def list_alerts(self) -> list[EnzanAlert]:
        """List configured alerts."""
        result = self._http.get("/v1/enzan/alerts")
        return [
            EnzanAlert(
                id=a["id"],
                name=a["name"],
                type=a["type"],
                threshold=a["threshold"],
                window=a["window"],
                enabled=a.get("enabled", True),
            )
            for a in result.get("alerts", [])
        ]

    def create_alert(self, alert: EnzanAlert) -> dict[str, str]:
        """
        Create a cost/usage alert.

        Example:
            >>> enzan.create_alert(EnzanAlert(
            ...     id="alert-001",
            ...     name="High spend",
            ...     type="cost_threshold",
            ...     threshold=1000,
            ...     window="24h"
            ... ))
        """
        return self._http.post("/v1/enzan/alerts", {
            "id": alert.id,
            "name": alert.name,
            "type": alert.type,
            "threshold": alert.threshold,
            "window": alert.window,
            "enabled": alert.enabled,
        })


# =============================================================================
# SŌZŌ CLIENT
# =============================================================================

class SozoClient:
    """Client for Sōzō (Synthetic Data) API."""

    def __init__(self, http: HttpClient):
        self._http = http

    def generate(
        self,
        records: int,
        schema: Optional[dict[str, str]] = None,
        schema_name: Optional[str] = None,
        correlations: Optional[dict[str, CorrelationType]] = None,
        seed: Optional[int] = None,
    ) -> SozoGenerateResponse:
        """
        Generate synthetic data.

        Args:
            records: Number of records to generate
            schema: Custom schema definition
            schema_name: Name of predefined schema
            correlations: Column correlations
            seed: Random seed for reproducibility

        Returns:
            SozoGenerateResponse with generated data

        Example:
            >>> # Using predefined schema
            >>> data = sozo.generate(records=1000, schema_name="saas_customers_v1")
            >>>
            >>> # Using custom schema
            >>> data = sozo.generate(
            ...     records=5000,
            ...     schema={
            ...         "user_id": "uuid4",
            ...         "email": "email",
            ...         "plan": "choice:free,pro,enterprise",
            ...         "mrr": "float:0-500",
            ...         "churned": "boolean:0.15"
            ...     },
            ...     correlations={"plan:mrr": "positive"}
            ... )
        """
        if not schema and not schema_name:
            raise KaizenValidationError("Either schema or schema_name is required")

        data: dict[str, Any] = {"records": records}
        if schema:
            data["schema"] = schema
        if schema_name:
            data["schemaName"] = schema_name
        if correlations:
            data["correlations"] = correlations
        if seed is not None:
            data["seed"] = seed

        result = self._http.post("/v1/sozo/generate", data)

        stats = {}
        for col, s in result.get("stats", {}).items():
            stats[col] = SozoColumnStats(
                type=s.get("type", "unknown"),
                min=s.get("min"),
                max=s.get("max"),
                mean=s.get("mean"),
                unique_count=s.get("uniqueCount"),
                values=s.get("values"),
            )

        return SozoGenerateResponse(
            columns=result.get("columns", []),
            rows=result.get("rows", []),
            stats=stats,
        )

    def list_schemas(self) -> list[SozoSchemaInfo]:
        """
        List available predefined schemas.

        Example:
            >>> schemas = sozo.list_schemas()
            >>> for s in schemas:
            ...     print(f"{s.name}: {list(s.columns.keys())}")
        """
        result = self._http.get("/v1/sozo/schemas")
        return [
            SozoSchemaInfo(name=s["name"], columns=s["columns"])
            for s in result.get("schemas", [])
        ]


# =============================================================================
# MAIN CLIENT
# =============================================================================

class KaizenClient:
    """
    Main client for Kaizen AI Systems API.

    Example:
        >>> client = KaizenClient(api_key="your-api-key")
        >>> result = client.akuma.query(dialect="postgres", prompt="Show all users")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.kaizenaisystems.com",
        timeout: float = 30.0,
    ):
        key = api_key or os.environ.get("KAIZEN_API_KEY", "")
        self._http = HttpClient(base_url=base_url, api_key=key, timeout=timeout)
        self.akuma = AkumaClient(self._http)
        self.enzan = EnzanClient(self._http)
        self.sozo = SozoClient(self._http)

    def set_api_key(self, key: str) -> None:
        """Set the API key."""
        self._http.set_api_key(key)

    def set_base_url(self, url: str) -> None:
        """Set the API base URL."""
        self._http.set_base_url(url)

    def health(self) -> dict[str, Any]:
        """Check API health."""
        return self._http.get("/health")


# =============================================================================
# DEFAULT CLIENT & CONVENIENCE FUNCTIONS
# =============================================================================

_default_client = KaizenClient()

akuma = _default_client.akuma
enzan = _default_client.enzan
sozo = _default_client.sozo


def set_api_key(key: str) -> None:
    """Set the API key for the default client."""
    _default_client.set_api_key(key)


def set_base_url(url: str) -> None:
    """Set the API base URL for the default client."""
    _default_client.set_base_url(url)

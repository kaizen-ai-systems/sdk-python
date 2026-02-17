from __future__ import annotations

from dataclasses import dataclass

from .._types import AlertType


@dataclass
class EnzanSummaryRow:
    """Row in Enzan summary."""

    cost_usd: float
    gpu_hours: float
    requests: int
    tokens_in: int
    tokens_out: int
    project: str | None = None
    model: str | None = None
    team: str | None = None
    provider: str | None = None


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
    region: str | None = None
    labels: dict[str, str] | None = None


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
class EnzanBurnResponse:
    """Response from Enzan burn endpoint."""

    burn_rate_usd_per_hour: float
    timestamp: str

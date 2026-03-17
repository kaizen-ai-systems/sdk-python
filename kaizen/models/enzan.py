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
    endpoint: str | None = None
    avg_util_pct: float | None = None


@dataclass
class EnzanSummaryTotal:
    """Aggregate totals from an Enzan summary response."""

    cost_usd: float
    gpu_hours: float
    requests: int
    tokens_in: int = 0
    tokens_out: int = 0


@dataclass
class EnzanSummaryResponse:
    """Response from Enzan summary."""

    window: str
    start_time: str
    end_time: str
    rows: list[EnzanSummaryRow]
    total: EnzanSummaryTotal
    api_costs: APICostSummary | None = None

    @property
    def total_cost_usd(self) -> float:
        return self.total.cost_usd

    @property
    def total_gpu_hours(self) -> float:
        return self.total.gpu_hours

    @property
    def total_requests(self) -> int:
        return self.total.requests

    @property
    def total_tokens_in(self) -> int:
        return self.total.tokens_in

    @property
    def total_tokens_out(self) -> int:
        return self.total.tokens_out


@dataclass
class APICostSummary:
    """Estimated Akuma API token spend for the requested window."""

    total_cost_usd: float
    prompt_tokens: int
    output_tokens: int
    queries: int


@dataclass
class EnzanModelCategoryBreakdown:
    """Prompt complexity breakdown for a model row."""

    category: str
    queries: int
    prompt_tokens: int
    output_tokens: int
    cost_usd: float
    percentage: float
    avg_cost_per_query: float


@dataclass
class EnzanModelCostRow:
    """Model-level spend row."""

    model: str
    queries: int
    prompt_tokens: int
    output_tokens: int
    cost_usd: float
    percentage: float
    avg_cost_per_query: float
    categories: list[EnzanModelCategoryBreakdown] | None = None


@dataclass
class EnzanModelCostTotal:
    """Aggregate totals for model-level spend analytics."""

    queries: int
    prompt_tokens: int
    output_tokens: int
    cost_usd: float


@dataclass
class EnzanModelCostResponse:
    """Response from Enzan model-level cost analytics."""

    window: str
    start_time: str
    end_time: str
    rows: list[EnzanModelCostRow]
    total: EnzanModelCostTotal


@dataclass
class EnzanLLMPricing:
    """LLM pricing catalog row."""

    provider: str
    model: str
    display_name: str
    input_cost_per_1k_tokens_usd: float
    output_cost_per_1k_tokens_usd: float
    currency: str
    active: bool


@dataclass
class EnzanGPUPricing:
    """GPU pricing catalog row."""

    provider: str
    gpu_type: str
    display_name: str
    hourly_rate_usd: float
    currency: str
    active: bool


@dataclass
class EnzanLLMPricingMutationResponse:
    """Response from an LLM pricing upsert."""

    status: str
    pricing: EnzanLLMPricing


@dataclass
class EnzanGPUPricingMutationResponse:
    """Response from a GPU pricing upsert."""

    status: str
    pricing: EnzanGPUPricing


@dataclass
class EnzanResource:
    """GPU resource for Enzan tracking."""

    id: str
    provider: str
    gpu_type: str
    gpu_count: int
    hourly_rate: float
    region: str | None = None
    endpoint: str | None = None
    labels: dict[str, str] | None = None
    created_at: str | None = None
    last_seen_at: str | None = None


@dataclass
class EnzanAlert:
    """Alert configuration for Enzan."""

    id: str
    name: str
    type: AlertType
    threshold: float
    window: str
    labels: dict[str, str] | None = None
    enabled: bool = True


@dataclass
class EnzanBurnResponse:
    """Response from Enzan burn endpoint."""

    burn_rate_usd_per_hour: float
    timestamp: str

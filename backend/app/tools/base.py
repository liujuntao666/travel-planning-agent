from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class ToolRequest:
    origin: str
    dest_cities: list[str]
    day_count: int
    people: int
    transport_mode: str | None = None
    start_date: date | None = None
    taboos: list[str] = field(default_factory=list)


@dataclass
class ToolResult:
    tool_type: str
    status: str = "SUCCESS"
    degrade: bool = False
    data: dict | list | None = None
    result_count: int = 0
    data_source: str | None = None
    query_time: datetime | None = None
    error_code: str | None = None
    error_msg: str | None = None
    call_id: str = ""
    cost_ms: int = 0
    request_params: dict = field(default_factory=dict)


@dataclass
class ToolBundle:
    trace_id: str
    results: dict[str, ToolResult]

    def data(self, key: str, default=None):
        result = self.results.get(key)
        return result.data if result and result.data is not None else default

    @property
    def degraded_types(self) -> list[str]:
        return [r.tool_type for r in self.results.values() if r.degrade]

    @property
    def calls(self) -> list[dict]:
        return [
            {
                "call_id": r.call_id,
                "tool_type": r.tool_type,
                "status": r.status,
                "degrade": r.degrade,
                "result_count": r.result_count,
                "cost_ms": r.cost_ms,
                "data_source": r.data_source,
                "error_msg": r.error_msg,
            }
            for r in self.results.values()
        ]

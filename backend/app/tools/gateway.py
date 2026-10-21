import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import datetime

from app.common.config import settings
from app.common.db import SessionLocal
from app.common.logging import get_logger
from app.models import ToolCallLog
from app.tools.base import ToolBundle, ToolRequest, ToolResult
from app.tools.providers import query_food, query_hotels, query_pois, query_transport, query_weather

log = get_logger(__name__)

TASKS = {
    "POI": query_pois,
    "TRANSPORT": query_transport,
    "HOTEL": query_hotels,
    "WEATHER": query_weather,
    "FOOD": query_food,
}

SUMMARY = {
    "POI": "返回景点",
    "TRANSPORT": "返回交通班次",
    "HOTEL": "返回住宿",
    "WEATHER": "返回逐日预报",
    "FOOD": "返回美食",
}


def _call(tool_type: str, req: ToolRequest, trace_id: str, conversation_id: int | None,
          trip_id: int | None) -> ToolResult:
    started = time.perf_counter()
    call_id = f"TC{datetime.now():%Y%m%d%H%M%S}{tool_type[:3]}{uuid.uuid4().hex[:6].upper()}"
    params = {
        "origin": req.origin,
        "dest_cities": req.dest_cities,
        "day_count": req.day_count,
        "people": req.people,
        "start_date": req.start_date.isoformat() if req.start_date else None,
    }
    result = ToolResult(tool_type=tool_type, call_id=call_id, request_params=params)

    if settings.tool_offline:
        result.status = "FAIL"
        result.degrade = True
        result.error_code = "TOOL_OFFLINE"
        result.error_msg = "故障注入演练：外部服务不可用，已降级为信息待确认"
    else:
        db = SessionLocal()
        try:
            data = TASKS[tool_type](db, req)
            result.data = data
            if isinstance(data, list):
                result.result_count = len(data)
                result.degrade = len(data) == 0
                first = data[0] if data else None
            else:
                legs = data.get("legs", []) if isinstance(data, dict) else []
                city_weather = data.get("by_city", {}) if isinstance(data, dict) else {}
                if legs:
                    result.result_count = sum(len(leg["options"]) for leg in legs)
                    result.degrade = result.result_count == 0
                    first = next((o for leg in legs for o in leg["options"]), None)
                else:
                    result.result_count = sum(len(v) for v in city_weather.values())
                    result.degrade = result.result_count == 0
                    first = next((w for v in city_weather.values() for w in v), None)
            result.data_source = (first or {}).get("data_source") if isinstance(first, dict) else None
            result.query_time = datetime.now()
            if result.degrade:
                result.error_code = "EMPTY_RESULT"
                result.error_msg = "外部服务无可用数据，已降级为信息待确认"
        except Exception as exc:
            result.status = "FAIL"
            result.degrade = True
            result.error_code = "TOOL_ERROR"
            result.error_msg = str(exc)[:500]
            log.warning("tool %s failed: %s", tool_type, exc)
        finally:
            db.close()

    result.cost_ms = int((time.perf_counter() - started) * 1000)
    if result.status == "SUCCESS" and result.degrade:
        result.status = "SUCCESS"
    summary = (
        f"{SUMMARY[tool_type]} {result.result_count} 条"
        if not result.degrade
        else f"{SUMMARY[tool_type]}无可用数据，降级为信息待确认"
    )
    try:
        db = SessionLocal()
        db.add(
            ToolCallLog(
                call_id=call_id,
                trace_id=trace_id,
                conversation_id=conversation_id,
                trip_id=trip_id,
                tool_type=tool_type,
                request_params=params,
                response_summary=summary[:512],
                result_count=result.result_count,
                status=result.status,
                degrade_flag=1 if result.degrade else 0,
                cost_ms=result.cost_ms,
                error_code=result.error_code,
                error_msg=result.error_msg,
                called_at=datetime.now(),
            )
        )
        db.commit()
        db.close()
    except Exception as exc:
        log.warning("write tool log failed: %s", exc)
    return result


def collect(req: ToolRequest, trace_id: str, conversation_id: int | None = None,
            trip_id: int | None = None) -> ToolBundle:
    """五类工具并行调用，单工具超时 5 秒，超时即降级（NFR-08）。"""
    timeout_s = max(settings.tool_timeout_ms, 100) / 1000
    results: dict[str, ToolResult] = {}
    with ThreadPoolExecutor(max_workers=len(TASKS), thread_name_prefix="tool") as pool:
        futures = {
            tool: pool.submit(_call, tool, req, trace_id, conversation_id, trip_id)
            for tool in TASKS
        }
        for tool, future in futures.items():
            try:
                results[tool] = future.result(timeout=timeout_s)
            except FutureTimeout:
                call_id = f"TC{datetime.now():%Y%m%d%H%M%S}{tool[:3]}TIMEOUT"
                results[tool] = ToolResult(
                    tool_type=tool,
                    status="TIMEOUT",
                    degrade=True,
                    error_code="TIMEOUT_5000",
                    error_msg=f"单工具超时 {int(timeout_s * 1000)} 毫秒，已降级",
                    call_id=call_id,
                    cost_ms=int(timeout_s * 1000),
                    request_params={},
                )
    return ToolBundle(trace_id=trace_id, results=results)

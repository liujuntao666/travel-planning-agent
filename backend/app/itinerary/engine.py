from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from app.itinerary.geo import (
    from_minutes,
    haversine_km,
    to_minutes,
    travel_minutes,
)
from app.itinerary.styles import StyleConfig
from app.itinerary.validator import validate_plan
from app.tools.base import ToolBundle

TOOL_LABELS = {"POI": "景点", "TRANSPORT": "交通", "HOTEL": "住宿", "WEATHER": "天气", "FOOD": "美食"}
MODE_TYPE = {"飞机优先": "FLIGHT", "高铁优先": "HIGHSPEED", "火车优先": "TRAIN", "自驾": "CAR_RENTAL", "公交优先": "BUS"}

MORNING = (9 * 60, 12 * 60)
AFTERNOON = (13 * 60 + 30, 18 * 60)
EVENING = (19 * 60 + 30, 21 * 60 + 30)
LUNCH = (12 * 60, 13 * 60 + 30)
DINNER = (18 * 60, 19 * 60 + 30)
MEAL_MINUTES = 90


@dataclass
class PlanInput:
    origin: str
    dest_cities: list[str]
    day_count: int
    people: int = 2
    budget_total: float | None = None
    style_code: str = "COMMON"
    transport_mode: str | None = None
    taboos: list[str] = field(default_factory=list)
    start_date: date | None = None
    title: str | None = None
    near_scenic: bool = False
    local_food: bool = False


def _date_of(start: date, offset: int) -> str:
    return (start + timedelta(days=offset)).isoformat()


def _allocate_days(cities: list[str], total: int) -> list[str]:
    if not cities:
        return ["待确认"] * total
    base, rem = divmod(total, len(cities))
    seq: list[str] = []
    for i, city in enumerate(cities):
        seq.extend([city] * (base + (1 if i < rem else 0)))
    while len(seq) < total:
        seq.append(cities[-1])
    return seq[:total]


def _pick_transport_option(options: list[dict], preferred: str) -> dict | None:
    if not options:
        return None
    def key(option: dict):
        return (
            option.get("transport_type") != preferred if preferred else False,
            -(option.get("seat_left") or 0),
            float(option.get("price") or 0),
        )
    return sorted(options, key=key)[0]


def _build_transport(input_: PlanInput, tools: ToolBundle, city_days: list[str]) -> tuple[list[dict], list[dict], dict[int, int]]:
    """返回 (交通腿, 交通条目, 每一天的到达/出发分钟)。"""
    route = [input_.origin, *input_.dest_cities, input_.origin]
    preferred = MODE_TYPE.get(input_.transport_mode or "", "")
    transport_data = tools.data("TRANSPORT", {"legs": []})
    legs_raw = {leg["leg_index"]: leg for leg in transport_data.get("legs", [])}
    legs: list[dict] = []
    day_windows: dict[int, dict[str, int | None]] = {}

    # 每段交通对应的日期：首段=第 1 天；城际段=抵达新城市首日；返程=最后一天
    city_start_day: dict[str, int] = {}
    seen: set[str] = set()
    for idx, city in enumerate(city_days):
        if city not in seen:
            seen.add(city)
            city_start_day[city] = idx + 1

    for leg_index in range(1, len(route)):
        dep, arr = route[leg_index - 1], route[leg_index]
        if dep == arr:
            continue
        if leg_index == 1:
            target_day = 1
        elif leg_index == len(route) - 1:
            target_day = len(city_days)
        else:
            target_day = city_start_day.get(arr, 1)
        target = (input_.start_date or date.today()) + timedelta(days=target_day - 1)
        options = (legs_raw.get(leg_index) or {}).get("options", [])
        chosen = _pick_transport_option(options, preferred)
        base = {
            "leg_index": leg_index,
            "from_city": dep,
            "to_city": arr,
            "transport_type": (chosen or {}).get("transport_type") or MODE_TYPE.get(input_.transport_mode or "", "HIGHSPEED"),
            "carrier": (chosen or {}).get("carrier"),
            "trip_no": (chosen or {}).get("trip_no"),
            "dep_station": (chosen or {}).get("dep_station"),
            "arr_station": (chosen or {}).get("arr_station"),
            "dep_time": None,
            "arr_time": None,
            "duration_min": (chosen or {}).get("duration_min"),
            "price": (chosen or {}).get("price"),
            "transfer_desc": (chosen or {}).get("transfer_desc"),
            "option_id": (chosen or {}).get("id"),
            "data_source": (chosen or {}).get("data_source"),
            "degrade_flag": 0,
        }
        if chosen and chosen.get("dep_time"):
            try:
                dep_dt = datetime.fromisoformat(str(chosen["dep_time"]))
                arr_dt = datetime.fromisoformat(str(chosen["arr_time"])) if chosen.get("arr_time") else None
                dep_full = datetime.combine(target, dep_dt.time())
                if arr_dt:
                    offset = 0 if arr_dt.date() == dep_dt.date() else 1
                    arr_full = datetime.combine(target + timedelta(days=offset), arr_dt.time())
                else:
                    arr_full = dep_full + timedelta(minutes=int(chosen.get("duration_min") or 0))
                base["dep_time"] = dep_full.isoformat(sep=" ")
                base["arr_time"] = arr_full.isoformat(sep=" ")
                base["duration_min"] = int((arr_full - dep_full).total_seconds() // 60)
            except ValueError:
                base["degrade_flag"] = 1
        else:
            base["degrade_flag"] = 1
            base["carrier"] = "信息待确认"
            base["transfer_desc"] = "实时班次不可用，出行前请确认"
        legs.append(base)

        window = day_windows.setdefault(target_day, {"arrival_min": None, "departure_min": None})
        if base["arr_time"]:
            window["arrival_min"] = max(window["arrival_min"] or 0, to_minutes(base["arr_time"][11:16]) + 60)
        if leg_index == len(route) - 1 and base["dep_time"]:
            window["departure_min"] = to_minutes(base["dep_time"][11:16]) - 120

        base["_target_day"] = target_day
    return legs, [], day_windows


def _filter_pois(pois: list[dict], taboos: list[str]) -> list[dict]:
    result = []
    for poi in pois:
        name = poi.get("name") or ""
        category = poi.get("category") or ""
        if "不购物" in taboos and ("购物" in name or "购物" in category):
            continue
        if "恐高" in taboos and ("雪山" in name or "索道" in name):
            continue
        result.append(poi)
    return result


def _pick_pois(candidates: list[dict], count: int, style: StyleConfig,
               start_lat: float | None, start_lon: float | None) -> list[dict]:
    if count <= 0 or not candidates:
        return []
    ranked = sorted(
        candidates,
        key=lambda p: (-style.weight_for(p.get("category")), -(float(p.get("rating") or 0))),
    )
    picked = ranked[:count]
    # 最近邻排序，减少回头路
    ordered: list[dict] = []
    cur_lat, cur_lon = start_lat, start_lon
    while picked:
        nxt = min(
            picked,
            key=lambda p: haversine_km(cur_lat, cur_lon, p.get("latitude"), p.get("longitude")),
        )
        ordered.append(nxt)
        picked.remove(nxt)
        cur_lat, cur_lon = nxt.get("latitude"), nxt.get("longitude")
    return ordered


def _hotel_for(city: str, hotels: list[dict], near_scenic: bool,
               anchor: tuple[float | None, float | None], level: str) -> dict | None:
    options = [h for h in hotels if h.get("city") == city and (h.get("available_rooms") or 0) > 0]
    if not options:
        options = [h for h in hotels if h.get("city") == city]
    if not options:
        return None

    def key(h: dict):
        dist = haversine_km(anchor[0], anchor[1], h.get("latitude"), h.get("longitude"))
        if near_scenic:
            return (dist, float(h.get("price_min") or 0))
        if level == "经济":
            return (float(h.get("price_min") or 0), -float(h.get("score") or 0))
        if level == "高端":
            return (-float(h.get("score") or 0), -float(h.get("price_min") or 0))
        return (-float(h.get("score") or 0), dist)
    return sorted(options, key=key)[0]


def _restaurants_for(city: str, restaurants: list[dict], local_food: bool) -> list[dict]:
    options = [r for r in restaurants if r.get("city") == city]
    return sorted(
        options,
        key=lambda r: (
            -(r.get("local_must_flag") or 0) if local_food else 0,
            -(float(r.get("score") or 0)),
        ),
    )


def _period_of(minute: int) -> str:
    if minute < MORNING[1]:
        return "MORNING"
    if minute < DINNER[0]:
        return "AFTERNOON"
    return "EVENING"


def build_plan(input_: PlanInput, tools: ToolBundle, style: StyleConfig) -> dict:
    start = input_.start_date or (date.today() + timedelta(days=7))
    city_days = _allocate_days(input_.dest_cities, input_.day_count)
    pois = tools.data("POI", [])
    hotels = tools.data("HOTEL", [])
    restaurants = tools.data("FOOD", [])
    weather_data = tools.data("WEATHER", {"by_city": {}}).get("by_city", {})
    legs, _, day_windows = _build_transport(input_, tools, city_days)

    used_pois: set[int] = set()
    meal_cursor: dict[str, int] = {}
    days: list[dict] = []
    lodging_rows: list[dict] = []
    degrade_notes: list[str] = []

    # 预算档次（用于住宿选择）
    per_person_budget = (input_.budget_total or 0) / max(input_.people, 1)
    budget_level = "经济" if 0 < per_person_budget <= 1500 else ("高端" if per_person_budget > 3000 else "舒适")

    for day_index in range(1, input_.day_count + 1):
        city = city_days[day_index - 1]
        day_date = _date_of(start, day_index - 1)
        window = day_windows.get(day_index, {})
        arrival_min = window.get("arrival_min")
        departure_min = window.get("departure_min")
        start_min = max(MORNING[0], arrival_min or 0)
        end_min = min(EVENING[1], departure_min if departure_min is not None else EVENING[1])

        city_pois = [
            p for p in _filter_pois(pois, input_.taboos)
            if p.get("city") == city and p.get("id") not in used_pois
        ]
        is_edge = day_index == 1 or day_index == input_.day_count
        if end_min <= start_min:
            count = 0
        elif is_edge:
            count = min(style.min_poi, len(city_pois))
        else:
            count = min(style.max_poi, len(city_pois))
        anchor_hotel = _hotel_for(city, hotels, input_.near_scenic, (None, None), budget_level)
        anchor = ((anchor_hotel or {}).get("latitude"), (anchor_hotel or {}).get("longitude"))
        picked = _pick_pois(city_pois, count, style, anchor[0], anchor[1])

        day_restaurants = _restaurants_for(city, restaurants, input_.local_food)
        items: list[dict] = []
        seq = 1

        def add_item(**kwargs) -> None:
            nonlocal seq
            item = {
                "seq": seq,
                "period": kwargs.pop("period", "MORNING"),
                "item_type": kwargs.pop("item_type", "POI"),
                "ref_id": kwargs.pop("ref_id", None),
                "ref_name": kwargs.pop("ref_name", None),
                "start_time": kwargs.pop("start_time", None),
                "end_time": kwargs.pop("end_time", None),
                "duration_min": kwargs.pop("duration_min", None),
                "distance_km": kwargs.pop("distance_km", 0.0),
                "travel_min": kwargs.pop("travel_min", 0),
                "ticket_price": kwargs.pop("ticket_price", 0.0),
                "booking_required": kwargs.pop("booking_required", 0),
                "booking_advance_days": kwargs.pop("booking_advance_days", None),
                "degrade_flag": kwargs.pop("degrade_flag", 0),
                "note": kwargs.pop("note", None),
                **kwargs,
            }
            items.append(item)
            seq += 1

        def _window_free(span: tuple[int, int]) -> bool:
            for item in items:
                if not item.get("start_time") or not item.get("end_time"):
                    continue
                s, e = to_minutes(item["start_time"]), to_minutes(item["end_time"])
                if s < span[1] and span[0] < e:
                    return False
            return True

        def _find_gap(earliest: int, latest_end: int, duration: int = MEAL_MINUTES) -> int | None:
            """在 [earliest, latest_end] 内找到第一个可容纳正餐的空档。"""
            candidates = {max(earliest, start_min)}
            for item in items:
                if item.get("start_time") and item.get("end_time"):
                    end = to_minutes(item["end_time"])
                    if earliest < end < latest_end:
                        candidates.add(end)
            for begin in sorted(candidates):
                if begin + duration <= latest_end and _window_free((begin, begin + duration)):
                    return begin
            return None

        def add_meal(begin: int, label: str) -> None:
            nonlocal prev_lat, prev_lon
            meal = day_restaurants[meal_cursor.get(city, 0) % len(day_restaurants)] if day_restaurants else None
            meal_cursor[city] = meal_cursor.get(city, 0) + 1
            dist = haversine_km(prev_lat, prev_lon, (meal or {}).get("latitude"), (meal or {}).get("longitude"))
            add_item(
                period="MEAL", item_type="RESTAURANT",
                ref_id=(meal or {}).get("id"), ref_name=(meal or {}).get("name") or "餐饮信息待确认",
                start_time=from_minutes(begin), end_time=from_minutes(begin + MEAL_MINUTES),
                duration_min=MEAL_MINUTES, distance_km=dist, travel_min=travel_minutes(dist),
                ticket_price=float((meal or {}).get("avg_price") or 0),
                degrade_flag=0 if meal else 1,
                note=(f"{label}：人均约 {float(meal['avg_price']):.0f} 元 · 招牌 {meal.get('signature_dish') or '当地风味'}"
                      if meal else f"{label}美食服务不可用，请出行前确认餐厅"),
            )
            prev_lat, prev_lon = (meal or {}).get("latitude"), (meal or {}).get("longitude")

        # 单时间轴顺序排期：从当天可用时间起依次安放景点，排不下的留待后续日期
        cursor = start_min
        prev_lat, prev_lon = anchor
        lunch_done = dinner_done = False
        for poi in picked:
            # 到达正餐时段时先用餐，再继续后续点位
            if not lunch_done and LUNCH[0] <= cursor < LUNCH[1]:
                add_meal(cursor, "午餐")
                lunch_done = True
                cursor += MEAL_MINUTES
            if not dinner_done and DINNER[0] <= cursor < DINNER[1]:
                add_meal(cursor, "晚餐")
                dinner_done = True
                cursor += MEAL_MINUTES

            duration = int(poi.get("suggest_duration_min") or 120) + int(poi.get("queue_minutes") or 0)
            open_start = to_minutes(poi.get("open_time_start"), 0)
            dist = haversine_km(prev_lat, prev_lon, poi.get("latitude"), poi.get("longitude"))
            travel = travel_minutes(dist)
            earliest = max(cursor + travel, open_start)
            if earliest + duration > end_min:
                break
            add_item(
                period=_period_of(earliest), item_type="POI",
                ref_id=poi.get("id"), ref_name=poi.get("name"),
                start_time=from_minutes(earliest), end_time=from_minutes(earliest + duration),
                duration_min=duration, distance_km=dist, travel_min=travel,
                ticket_price=float(poi.get("ticket_price") or 0),
                booking_required=int(poi.get("booking_required") or 0),
                booking_advance_days=poi.get("booking_advance_days"),
                degrade_flag=int(poi.get("degrade_flag") or 0),
                note=(f"{poi.get('open_time_desc') or ''} · 需提前 {poi.get('booking_advance_days')} 天预约"
                      if poi.get("booking_required") else poi.get("open_time_desc")),
                _open_start=poi.get("open_time_start"), _open_end=poi.get("open_time_end"),
                _lat=poi.get("latitude"), _lon=poi.get("longitude"),
            )
            used_pois.add(poi.get("id"))
            cursor = earliest + duration
            prev_lat, prev_lon = poi.get("latitude"), poi.get("longitude")

        if not lunch_done:
            lunch_begin = _find_gap(LUNCH[0], min(LUNCH[1] + 60, end_min))
            if lunch_begin is not None:
                add_meal(lunch_begin, "午餐")
        if not dinner_done:
            dinner_begin = _find_gap(DINNER[0], min(EVENING[1], end_min))
            if dinner_begin is not None:
                add_meal(dinner_begin, "晚餐")

        # 交通条目（与 t_trip_transport 对应，便于行程单按天展示）
        for leg in legs:
            if leg.get("_target_day") != day_index:
                continue
            dep_t = (leg.get("dep_time") or "")[11:16] or None
            arr_t = (leg.get("arr_time") or "")[11:16] or None
            add_item(
                period="MORNING" if to_minutes(dep_t, 9 * 60) < 12 * 60 else "AFTERNOON",
                item_type="TRANSPORT", ref_id=None,
                ref_name=f"{leg['from_city']} → {leg['to_city']}",
                start_time=dep_t, end_time=arr_t, duration_min=leg.get("duration_min"),
                ticket_price=float(leg.get("price") or 0), booking_required=1,
                booking_advance_days=1, degrade_flag=leg.get("degrade_flag") or 0,
                note=leg.get("transfer_desc") or ("班次信息待确认" if leg.get("degrade_flag") else None),
            )

        if not any(i["item_type"] == "POI" for i in items) and day_index != input_.day_count:
            add_item(
                period="AFTERNOON", item_type="FREE", ref_name="自由活动（信息待确认）",
                start_time=from_minutes(max(start_min, AFTERNOON[0])),
                end_time=from_minutes(min(end_min, AFTERNOON[1])),
                duration_min=max(0, min(end_min, AFTERNOON[1]) - max(start_min, AFTERNOON[0])),
                degrade_flag=1, note="实时景点信息不可用，已降级为自由活动，出行前请确认",
            )

        items.sort(key=lambda i: to_minutes(i.get("start_time"), 24 * 60))
        for idx, item in enumerate(items, 1):
            item["seq"] = idx

        weather = None
        for row in weather_data.get(city, []):
            if str(row.get("forecast_date")) == day_date:
                weather = row
                break
        if weather is None:
            degrade_notes.append(f"第 {day_index} 天（{city}）天气信息待确认")

        day = {
            "day_index": day_index,
            "day_date": day_date,
            "city": city,
            "theme": _theme_for(day_index, city, items, input_.day_count),
            "pace": style.pace,
            "remark": _remark_for(day_index, input_.day_count, weather, departure_min),
            "weather": weather,
            "items": items,
            "lodging": None,
        }
        days.append(day)

        # 住宿：最后一晚不安排
        if day_index < input_.day_count:
            anchor_item = next((i for i in reversed(items) if i.get("_lat")), None)
            hotel = _hotel_for(
                city, hotels, input_.near_scenic,
                ((anchor_item or {}).get("_lat") or anchor[0], (anchor_item or {}).get("_lon") or anchor[1]),
                budget_level,
            )
            rooms = max(1, (input_.people + 1) // 2)
            if hotel:
                night_price = float(hotel.get("price_min") or hotel.get("price_max") or 0)
                distance = haversine_km(
                    (anchor_item or {}).get("_lat"), (anchor_item or {}).get("_lon"),
                    hotel.get("latitude"), hotel.get("longitude"),
                )
                lodging = {
                    "hotel_id": hotel.get("id"),
                    "hotel_name": hotel.get("name"),
                    "room_type": hotel.get("room_type"),
                    "check_in": day_date,
                    "check_out": _date_of(start, day_index),
                    "nights": 1,
                    "price_per_night": night_price,
                    "rooms": rooms,
                    "total_price": round(night_price * rooms, 2),
                    "distance_to_scenic": distance,
                    "score": hotel.get("score"),
                    "degrade_flag": 0,
                    "data_source": hotel.get("data_source"),
                }
            else:
                lodging = {
                    "hotel_id": None, "hotel_name": "住宿信息待确认", "room_type": None,
                    "check_in": day_date, "check_out": _date_of(start, day_index),
                    "nights": 1, "price_per_night": 0, "rooms": rooms, "total_price": 0,
                    "distance_to_scenic": None, "score": None, "degrade_flag": 1,
                }
                degrade_notes.append(f"第 {day_index} 晚（{city}）住宿信息待确认")
            day["lodging"] = lodging
            lodging_rows.append(lodging)

    budget = _budget(days, legs, input_, budget_level)
    for leg in legs:
        leg.pop("_target_day", None)

    plan = {
        "trip": {
            "title": input_.title or f"{input_.origin}出发 {(' / '.join(input_.dest_cities))} {input_.day_count}天{input_.day_count - 1}晚{style.name}行",
            "origin_city": input_.origin,
            "dest_cities": " / ".join(input_.dest_cities),
            "day_count": input_.day_count,
            "night_count": input_.day_count - 1,
            "people_count": input_.people,
            "budget_total": float(input_.budget_total) if input_.budget_total else None,
            "budget_level": budget_level,
            "style_code": input_.style_code,
            "style_name": style.name,
            "transport_mode": input_.transport_mode,
            "taboos": ",".join(input_.taboos) if input_.taboos else None,
            "start_date": start.isoformat(),
        },
        "days": days,
        "transports": legs,
        "budget": budget,
        "degrade_notes": list(dict.fromkeys(degrade_notes)),
        "degrade_flag": bool(degrade_notes) or bool(tools.degraded_types),
        "tool_calls": tools.calls,
        "trace_id": tools.trace_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "meta": {
            "style": style.code,
            "degraded_tools": tools.degraded_types,
            "source_notice": "价格、班次、房态、开放时间均来自工具返回并附查询时间；缺失项标注「信息待确认」，系统不做估算替代。",
        },
    }
    issues = validate_plan(plan, style)

    # 校验完成后再清理仅用于排期的内部字段
    for day in days:
        for item in day["items"]:
            for key in ("_open_start", "_open_end", "_lat", "_lon"):
                item.pop(key, None)

    plan["issues"] = issues
    plan["valid_flag"] = not any(i["level"] == "ERROR" for i in issues)
    return plan


def _theme_for(day_index: int, city: str, items: list[dict], total: int) -> str:
    if day_index == total:
        return "返程"
    names = [i["ref_name"] for i in items if i.get("item_type") == "POI"]
    if names:
        return f"{city} · " + " / ".join(names[:2])
    if any(i.get("item_type") == "TRANSPORT" for i in items):
        return f"转场 {city}"
    return f"{city} 自由活动"


def _remark_for(day_index: int, total: int, weather: dict | None, departure_min) -> str | None:
    notes = []
    if weather:
        tips = weather.get("dressing_tip")
        if tips:
            notes.append(tips)
    if day_index == total and departure_min:
        notes.append("预留充足时间前往车站 / 机场")
    return "；".join(notes) or None


def _budget(days: list[dict], legs: list[dict], input_: PlanInput, level: str) -> dict:
    people = max(input_.people, 1)
    transport = round(sum(float(leg.get("price") or 0) for leg in legs) * people, 2)
    lodging = round(sum(float((day.get("lodging") or {}).get("total_price") or 0) for day in days), 2)
    tickets = round(sum(
        float(item.get("ticket_price") or 0) * people
        for day in days for item in day["items"] if item.get("item_type") == "POI"
    ), 2)
    meals = round(sum(
        float(item.get("ticket_price") or 0) * people
        for day in days for item in day["items"] if item.get("item_type") == "RESTAURANT"
    ), 2)
    total = round(transport + lodging + tickets + meals, 2)
    budget = float(input_.budget_total) if input_.budget_total else None
    over = round(total - budget, 2) if budget and total > budget else 0.0
    suggestions: list[str] = []
    if over:
        suggestions.append(f"当前方案超出预算约 {over:.0f} 元，可将部分住宿调整为经济型，或减少 1 个收费景点")
        suggestions.append("优先选择高铁 / 动车并在非高峰时段出行，可进一步压缩交通成本")
    return {
        "transport": transport,
        "lodging": lodging,
        "tickets": tickets,
        "meals": meals,
        "total": total,
        "per_person": round(total / people, 2),
        "budget_total": budget,
        "budget_level": level,
        "over_budget": over > 0,
        "over_amount": over,
        "status": "OVER" if over > 0 else ("IN" if budget else "NO_BUDGET"),
        "suggestions": suggestions,
    }

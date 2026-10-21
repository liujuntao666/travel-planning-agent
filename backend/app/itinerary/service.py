import copy
import uuid
from datetime import date, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.common.errors import ConflictError, NotFoundError, ValidationError
from app.itinerary.engine import PlanInput, _budget, build_plan
from app.itinerary.geo import from_minutes, to_minutes
from app.itinerary.styles import get_style
from app.itinerary.validator import validate_plan
from app.models import (
    Conversation,
    Hotel,
    Poi,
    Trip,
    TripDay,
    TripItem,
    TripLodging,
    TripTransport,
    TripVersion,
)
from app.tools.base import ToolBundle


def new_trip(db: Session, user_id: int, conversation_id: int | None, plan: dict) -> Trip:
    trip_info = plan["trip"]
    trip = Trip(
        trip_no=f"TRIP{datetime.now():%Y%m%d%H%M%S}{uuid.uuid4().hex[:4].upper()}",
        user_id=user_id,
        conversation_id=conversation_id,
        title=trip_info["title"],
        origin_city=trip_info["origin_city"],
        dest_cities=trip_info["dest_cities"],
        day_count=trip_info["day_count"],
        night_count=trip_info["night_count"],
        people_count=trip_info["people_count"],
        budget_total=trip_info.get("budget_total"),
        budget_level=trip_info.get("budget_level"),
        style_code=trip_info["style_code"],
        transport_mode=trip_info.get("transport_mode"),
        taboos=trip_info.get("taboos"),
        current_version_no=0,
        status=2,
        degrade_flag=1 if plan.get("degrade_flag") else 0,
    )
    db.add(trip)
    db.flush()
    return trip


def create_plan(db: Session, user_id: int, conversation_id: int | None, plan: dict) -> Trip:
    trip = new_trip(db, user_id, conversation_id, plan)
    save_version(db, trip, plan, "INIT", "首次生成完整行程")
    return trip


def save_version(db: Session, trip: Trip, plan: dict, change_type: str, summary: str,
                 base_version_id: int | None = None) -> TripVersion:
    version_no = (db.scalar(
        select(func.max(TripVersion.version_no)).where(TripVersion.trip_id == trip.id)
    ) or 0) + 1
    version = TripVersion(
        trip_id=trip.id,
        version_no=version_no,
        change_type=change_type,
        change_summary=summary[:500],
        base_version_id=base_version_id,
        content_json=plan,
        total_cost=(plan.get("budget") or {}).get("total"),
        current_flag=0,
        valid_flag=1 if plan.get("valid_flag") else 0,
    )
    db.add(version)
    db.flush()

    for day_data in plan.get("days", []):
        day = TripDay(
            trip_version_id=version.id,
            day_index=day_data["day_index"],
            day_date=date.fromisoformat(day_data["day_date"]) if day_data.get("day_date") else None,
            city=day_data.get("city"),
            theme=day_data.get("theme"),
            pace=day_data.get("pace"),
            remark=day_data.get("remark"),
        )
        db.add(day)
        db.flush()
        for item_data in day_data.get("items", []):
            db.add(TripItem(
                trip_day_id=day.id,
                period=item_data.get("period") or "MORNING",
                item_type=item_data.get("item_type") or "POI",
                ref_id=item_data.get("ref_id"),
                ref_name=item_data.get("ref_name"),
                start_time=_time(item_data.get("start_time")),
                end_time=_time(item_data.get("end_time")),
                duration_min=item_data.get("duration_min"),
                seq=item_data.get("seq") or 1,
                distance_km=item_data.get("distance_km"),
                travel_min=item_data.get("travel_min"),
                ticket_price=item_data.get("ticket_price"),
                booking_required=item_data.get("booking_required") or 0,
                booking_advance_days=item_data.get("booking_advance_days"),
                degrade_flag=item_data.get("degrade_flag") or 0,
                note=item_data.get("note"),
            ))
        lodging_data = day_data.get("lodging")
        if lodging_data:
            db.add(TripLodging(
                trip_day_id=day.id,
                hotel_id=lodging_data.get("hotel_id"),
                hotel_name=lodging_data.get("hotel_name"),
                room_type=lodging_data.get("room_type"),
                check_in=_date(lodging_data.get("check_in")),
                check_out=_date(lodging_data.get("check_out")),
                nights=lodging_data.get("nights") or 1,
                price_per_night=lodging_data.get("price_per_night"),
                total_price=lodging_data.get("total_price"),
                distance_to_scenic=lodging_data.get("distance_to_scenic"),
                score=lodging_data.get("score"),
                degrade_flag=lodging_data.get("degrade_flag") or 0,
            ))

    for leg in plan.get("transports", []):
        db.add(TripTransport(
            trip_version_id=version.id,
            leg_index=leg.get("leg_index") or 1,
            transport_type=leg.get("transport_type") or "HIGHSPEED",
            option_id=leg.get("option_id"),
            carrier=leg.get("carrier"),
            trip_no=leg.get("trip_no"),
            from_city=leg.get("from_city"),
            to_city=leg.get("to_city"),
            dep_station=leg.get("dep_station"),
            arr_station=leg.get("arr_station"),
            dep_time=_datetime(leg.get("dep_time")),
            arr_time=_datetime(leg.get("arr_time")),
            duration_min=leg.get("duration_min"),
            price=leg.get("price"),
            transfer_desc=leg.get("transfer_desc"),
            degrade_flag=leg.get("degrade_flag") or 0,
        ))

    db.execute(
        update(TripVersion).where(TripVersion.trip_id == trip.id, TripVersion.id != version.id)
        .values(current_flag=0)
    )
    version.current_flag = 1
    trip_info = plan["trip"]
    trip.title = trip_info.get("title") or trip.title
    trip.day_count = trip_info["day_count"]
    trip.night_count = trip_info["night_count"]
    trip.people_count = trip_info["people_count"]
    trip.budget_total = trip_info.get("budget_total")
    trip.budget_level = trip_info.get("budget_level")
    trip.style_code = trip_info["style_code"]
    trip.transport_mode = trip_info.get("transport_mode")
    trip.taboos = trip_info.get("taboos")
    trip.current_version_no = version_no
    trip.status = 2
    trip.degrade_flag = 1 if plan.get("degrade_flag") else 0
    db.flush()
    return version


def current_version(db: Session, trip: Trip) -> TripVersion:
    version = db.scalar(
        select(TripVersion).where(
            TripVersion.trip_id == trip.id,
            TripVersion.current_flag == 1,
            TripVersion.deleted == 0,
        ).order_by(TripVersion.version_no.desc())
    )
    if not version:
        raise NotFoundError("行程版本不存在")
    return version


def get_version(db: Session, trip: Trip, version_id: int) -> TripVersion:
    version = db.scalar(
        select(TripVersion).where(
            TripVersion.id == version_id,
            TripVersion.trip_id == trip.id,
            TripVersion.deleted == 0,
        )
    )
    if not version:
        raise NotFoundError("行程版本不存在")
    return version


def get_trip(db: Session, trip_id: int) -> Trip:
    trip = db.scalar(select(Trip).where(Trip.id == trip_id, Trip.deleted == 0))
    if not trip:
        raise NotFoundError("行程不存在")
    return trip


def serialize_trip(db: Session, trip: Trip, version: TripVersion | None = None) -> dict:
    version = version or current_version(db, trip)
    plan = copy.deepcopy(version.content_json or {})
    plan["id"] = trip.id
    plan["trip_no"] = trip.trip_no
    plan["status"] = trip.status
    plan["conversation_id"] = trip.conversation_id
    plan["version"] = {
        "id": version.id,
        "version_no": version.version_no,
        "change_type": version.change_type,
        "change_summary": version.change_summary,
        "total_cost": float(version.total_cost) if version.total_cost is not None else None,
        "current_flag": version.current_flag,
        "valid_flag": version.valid_flag,
        "created_at": version.created_at.isoformat() if version.created_at else None,
        "base_version_id": version.base_version_id,
    }

    days = db.scalars(
        select(TripDay).where(
            TripDay.trip_version_id == version.id, TripDay.deleted == 0
        ).order_by(TripDay.day_index)
    ).all()
    row_by_index = {d.day_index: d for d in days}
    for day in plan.get("days", []):
        row = row_by_index.get(day["day_index"])
        if not row:
            continue
        day["id"] = row.id
        items = db.scalars(
            select(TripItem).where(
                TripItem.trip_day_id == row.id, TripItem.deleted == 0
            ).order_by(TripItem.seq)
        ).all()
        item_by_seq = {i.seq: i for i in items}
        for item in day.get("items", []):
            db_item = item_by_seq.get(item.get("seq"))
            if db_item:
                item["id"] = db_item.id
                item["trip_day_id"] = row.id
        lodging = db.scalar(
            select(TripLodging).where(
                TripLodging.trip_day_id == row.id, TripLodging.deleted == 0
            ).order_by(TripLodging.id.desc())
        )
        if lodging and day.get("lodging"):
            day["lodging"]["id"] = lodging.id

    transports = db.scalars(
        select(TripTransport).where(
            TripTransport.trip_version_id == version.id, TripTransport.deleted == 0
        ).order_by(TripTransport.leg_index)
    ).all()
    db_legs = {t.leg_index: t for t in transports}
    for leg in plan.get("transports", []):
        row = db_legs.get(leg.get("leg_index"))
        if row:
            leg["id"] = row.id
    return plan


def list_versions(db: Session, trip: Trip) -> list[dict]:
    rows = db.scalars(
        select(TripVersion).where(
            TripVersion.trip_id == trip.id, TripVersion.deleted == 0
        ).order_by(TripVersion.version_no.desc())
    ).all()
    return [
        {
            "id": v.id,
            "version_no": v.version_no,
            "change_type": v.change_type,
            "change_summary": v.change_summary,
            "total_cost": float(v.total_cost) if v.total_cost is not None else None,
            "current_flag": v.current_flag,
            "valid_flag": v.valid_flag,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in rows
    ]


def activate_version(db: Session, trip: Trip, version_id: int) -> dict:
    version = get_version(db, trip, version_id)
    db.execute(
        update(TripVersion).where(TripVersion.trip_id == trip.id).values(current_flag=0)
    )
    version.current_flag = 1
    trip.current_version_no = version.version_no
    db.flush()
    return serialize_trip(db, trip, version)


def compare_versions(db: Session, trip: Trip, base_id: int, target_id: int) -> dict:
    base = get_version(db, trip, base_id)
    target = get_version(db, trip, target_id)
    base_plan = base.content_json or {}
    target_plan = target.content_json or {}
    base_names = {
        (d["day_index"], i.get("seq"), i.get("ref_name"))
        for d in base_plan.get("days", []) for i in d.get("items", [])
    }
    target_names = {
        (d["day_index"], i.get("seq"), i.get("ref_name"))
        for d in target_plan.get("days", []) for i in d.get("items", [])
    }
    added = [n[2] for n in target_names - base_names]
    removed = [n[2] for n in base_names - target_names]
    return {
        "base": {"id": base.id, "version_no": base.version_no, "total_cost": float(base.total_cost or 0)},
        "target": {"id": target.id, "version_no": target.version_no, "total_cost": float(target.total_cost or 0)},
        "added": added,
        "removed": removed,
        "cost_delta": float(target.total_cost or 0) - float(base.total_cost or 0),
        "summary": target.change_summary,
    }


def _time(value):
    if value is None:
        return None
    if hasattr(value, "hour"):
        return value
    from datetime import time as t
    parts = str(value).split(":")
    return t(int(parts[0]), int(parts[1]), int(float(parts[2])) if len(parts) > 2 else 0)


def _date(value):
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


# ---------------------------------------------------------------- 手动编辑

def _locate_item(plan: dict, day_index: int, seq: int) -> dict:
    for day in plan.get("days", []):
        if day["day_index"] == day_index:
            for item in day.get("items", []):
                if item.get("seq") == seq:
                    return item
    raise NotFoundError("行程条目不存在")


def _resolve_item_row(db: Session, trip: Trip, item_id: int) -> tuple[TripItem, TripDay]:
    item = db.scalar(select(TripItem).where(TripItem.id == item_id, TripItem.deleted == 0))
    if not item:
        raise NotFoundError("行程条目不存在")
    day = db.scalar(select(TripDay).where(TripDay.id == item.trip_day_id, TripDay.deleted == 0))
    if not day:
        raise NotFoundError("行程日不存在")
    version = db.scalar(select(TripVersion).where(TripVersion.id == day.trip_version_id))
    if not version or not version.current_flag:
        raise ConflictError("只能编辑当前生效版本")
    if version.trip_id != trip.id:
        raise NotFoundError("行程条目不存在")
    return item, day


def _renumber(day: dict) -> None:
    day["items"].sort(key=lambda i: (to_minutes(i.get("start_time"), 24 * 60), i.get("seq") or 0))
    for idx, item in enumerate(day["items"], 1):
        item["seq"] = idx


def _recalc_plan(db: Session, trip: Trip, plan: dict) -> None:
    style = get_style(db, trip.style_code)
    info = plan["trip"]
    input_ = PlanInput(
        origin=info["origin_city"],
        dest_cities=[c.strip() for c in info["dest_cities"].split("/") if c.strip()],
        day_count=info["day_count"],
        people=info["people_count"],
        budget_total=info.get("budget_total"),
        style_code=info["style_code"],
        transport_mode=info.get("transport_mode"),
        start_date=date.fromisoformat(info["start_date"]) if info.get("start_date") else None,
        title=info.get("title"),
    )
    plan["budget"] = _budget(plan["days"], plan["transports"], input_, info.get("budget_level") or "舒适")
    plan["issues"] = validate_plan(plan, style)
    plan["valid_flag"] = not any(i["level"] == "ERROR" for i in plan["issues"])


def _save_edit(db: Session, trip: Trip, plan: dict, change_type: str, summary: str) -> dict:
    base = current_version(db, trip)
    _recalc_plan(db, trip, plan)
    if any(i["level"] == "ERROR" for i in plan["issues"]):
        raise ConflictError("存在时段冲突或排期错误，请先调整：" + plan["issues"][0]["message"])
    save_version(db, trip, plan, change_type, summary, base_version_id=base.id)
    return serialize_trip(db, trip)


def update_item(db: Session, trip: Trip, item_id: int, payload: dict) -> dict:
    item, day_row = _resolve_item_row(db, trip, item_id)
    plan = copy.deepcopy(current_version(db, trip).content_json)
    target = _locate_item(plan, day_row.day_index, item.seq)
    for key in ("start_time", "end_time", "period", "note"):
        if payload.get(key) is not None:
            target[key] = payload[key]
    if target.get("start_time") and target.get("end_time"):
        target["duration_min"] = max(0, to_minutes(target["end_time"]) - to_minutes(target["start_time"]))
    day = next(d for d in plan["days"] if d["day_index"] == day_row.day_index)
    _renumber(day)
    return _save_edit(db, trip, plan, "MANUAL_EDIT", f"手动修改「{target.get('ref_name')}」时段")


def delete_item(db: Session, trip: Trip, item_id: int) -> dict:
    item, day_row = _resolve_item_row(db, trip, item_id)
    plan = copy.deepcopy(current_version(db, trip).content_json)
    day = next(d for d in plan["days"] if d["day_index"] == day_row.day_index)
    target = _locate_item(plan, day_row.day_index, item.seq)
    day["items"] = [i for i in day["items"] if i is not target]
    _renumber(day)
    return _save_edit(db, trip, plan, "MANUAL_EDIT", f"删除「{target.get('ref_name')}」")


def move_item(db: Session, trip: Trip, item_id: int, direction: str) -> dict:
    if direction not in ("up", "down"):
        raise ValidationError("direction 只能是 up 或 down")
    item, day_row = _resolve_item_row(db, trip, item_id)
    plan = copy.deepcopy(current_version(db, trip).content_json)
    day = next(d for d in plan["days"] if d["day_index"] == day_row.day_index)
    items = day["items"]
    idx = next((i for i, x in enumerate(items) if x.get("seq") == item.seq), None)
    if idx is None:
        raise NotFoundError("行程条目不存在")
    swap_idx = idx - 1 if direction == "up" else idx + 1
    if swap_idx < 0 or swap_idx >= len(items):
        return serialize_trip(db, trip)
    a, b = items[idx], items[swap_idx]
    a["seq"], b["seq"] = b.get("seq"), a.get("seq")
    for key in ("start_time", "end_time", "duration_min", "period"):
        a[key], b[key] = b.get(key), a.get(key)
    _renumber(day)
    return _save_edit(db, trip, plan, "MANUAL_EDIT", f"调整顺序：{a.get('ref_name')} ↔ {b.get('ref_name')}")


def add_item(db: Session, trip: Trip, payload: dict) -> dict:
    plan = copy.deepcopy(current_version(db, trip).content_json)
    day = next((d for d in plan["days"] if d["day_index"] == payload["day_index"]), None)
    if not day:
        raise NotFoundError("行程日不存在")
    item_type = payload.get("item_type") or "POI"
    name = payload.get("ref_name")
    price = 0.0
    if item_type == "POI" and payload.get("ref_id"):
        poi = db.scalar(select(Poi).where(Poi.id == payload["ref_id"], Poi.deleted == 0))
        if not poi:
            raise NotFoundError("景点不存在")
        name = poi.name
        price = float(poi.ticket_price or 0)
    if not name:
        raise ValidationError("请提供条目名称或 ref_id")
    start = payload.get("start_time") or "10:00"
    end = payload.get("end_time") or from_minutes(to_minutes(start) + int(payload.get("duration_min") or 90))
    item = {
        "seq": len(day["items"]) + 1,
        "period": payload.get("period") or "AFTERNOON",
        "item_type": item_type,
        "ref_id": payload.get("ref_id"),
        "ref_name": name,
        "start_time": start,
        "end_time": end,
        "duration_min": to_minutes(end) - to_minutes(start),
        "distance_km": 0.0,
        "travel_min": 0,
        "ticket_price": price,
        "booking_required": 0,
        "degrade_flag": 0,
        "note": payload.get("note"),
    }
    day["items"].append(item)
    _renumber(day)
    return _save_edit(db, trip, plan, "MANUAL_EDIT", f"新增「{name}」")


def replace_hotel(db: Session, trip: Trip, lodging_id: int, hotel_id: int) -> dict:
    lodging = db.scalar(select(TripLodging).where(TripLodging.id == lodging_id, TripLodging.deleted == 0))
    if not lodging:
        raise NotFoundError("住宿安排不存在")
    day = db.scalar(select(TripDay).where(TripDay.id == lodging.trip_day_id))
    hotel = db.scalar(select(Hotel).where(Hotel.id == hotel_id, Hotel.deleted == 0))
    if not day or not hotel:
        raise NotFoundError("酒店不存在")
    if not hotel.available_rooms:
        raise ConflictError("该酒店在查询日期无可订房量")
    plan = copy.deepcopy(current_version(db, trip).content_json)
    day_plan = next((d for d in plan["days"] if d["day_index"] == day.day_index), None)
    if not day_plan or not day_plan.get("lodging"):
        raise NotFoundError("住宿安排不存在")
    rooms = max(1, (plan["trip"]["people_count"] + 1) // 2)
    price = float(hotel.price_min or hotel.price_max or 0)
    day_plan["lodging"].update({
        "hotel_id": hotel.id,
        "hotel_name": hotel.name,
        "room_type": hotel.room_type,
        "price_per_night": price,
        "rooms": rooms,
        "total_price": round(price * rooms, 2),
        "score": float(hotel.score) if hotel.score is not None else None,
        "data_source": hotel.data_source,
        "degrade_flag": 0,
    })
    return _save_edit(db, trip, plan, "MANUAL_EDIT", f"替换住宿为「{hotel.name}」")


def replan(db: Session, trip: Trip) -> dict:
    """AI 重新排布：保留显式点位，按时段顺延并复核预算。"""
    plan = copy.deepcopy(current_version(db, trip).content_json)
    for day in plan.get("days", []):
        if any(i.get("item_type") == "TRANSPORT" for i in day.get("items", [])):
            continue
        cursor = 9 * 60
        for item in sorted(day["items"], key=lambda i: i.get("seq") or 0):
            duration = int(item.get("duration_min") or 90)
            if item.get("period") == "MEAL":
                lunch = item.get("start_time") == "12:00" or item.get("start_time") == "12:00:00"
                start = 12 * 60 if lunch else max(cursor, 18 * 60)
            else:
                start = cursor
            item["start_time"] = from_minutes(start)
            item["end_time"] = from_minutes(start + duration)
            cursor = start + duration + 15
    _recalc_plan(db, trip, plan)
    base = current_version(db, trip)
    save_version(db, trip, plan, "AI_RERANK", "AI 重新排布：时段顺延、预算复核", base_version_id=base.id)
    return serialize_trip(db, trip)


def build_with_tools(db: Session, user_id: int, conversation_id: int | None,
                     input_: PlanInput, tools: ToolBundle) -> tuple[Trip, dict]:
    style = get_style(db, input_.style_code)
    plan = build_plan(input_, tools, style)
    trip = create_plan(db, user_id, conversation_id, plan)
    conversation = db.scalar(select(Conversation).where(Conversation.id == conversation_id)) if conversation_id else None
    if conversation:
        conversation.current_trip_id = trip.id
        conversation.last_intent = "NEW_PLAN"
    db.flush()
    return trip, plan

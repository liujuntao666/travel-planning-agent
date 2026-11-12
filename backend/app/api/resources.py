from fastapi import APIRouter, Depends, Query
from sqlalchemy import distinct, or_, select
from sqlalchemy.orm import Session

from app.common.db import get_db
from app.common.pagination import PageParams, paginate
from app.common.rbac import require_permission
from app.common.redis_client import cache_get_json, cache_set_json
from app.itinerary.styles import DEFAULT_STYLES
from app.models import Hotel, Poi, Restaurant, ToolCallLog, TravelTips, TripStyle

CITY_CACHE_KEY = "dict:cities"
STYLE_CACHE_KEY = "dict:styles"
DICT_CACHE_KEY = "dict:all"
CACHE_TTL_S = 600

router = APIRouter(
    tags=["resources"],
    dependencies=[Depends(require_permission("resource:read"))],
)


def _poi_dict(p: Poi) -> dict:
    return {
        "id": p.id, "name": p.name, "city": p.city, "address": p.address,
        "longitude": float(p.longitude) if p.longitude is not None else None,
        "latitude": float(p.latitude) if p.latitude is not None else None,
        "category": p.category,
        "ticket_price": float(p.ticket_price or 0),
        "open_time_desc": p.open_time_desc,
        "booking_required": p.booking_required,
        "booking_channel": p.booking_channel,
        "booking_advance_days": p.booking_advance_days,
        "suggest_duration_min": p.suggest_duration_min,
        "rating": float(p.rating) if p.rating is not None else None,
        "data_source": p.data_source,
        "query_time": p.query_time.isoformat() if p.query_time else None,
        "degrade_flag": p.degrade_flag,
    }


def _hotel_dict(h: Hotel) -> dict:
    return {
        "id": h.id, "name": h.name, "city": h.city, "address": h.address,
        "longitude": float(h.longitude) if h.longitude is not None else None,
        "latitude": float(h.latitude) if h.latitude is not None else None,
        "hotel_type": h.hotel_type, "star": h.star,
        "score": float(h.score) if h.score is not None else None,
        "price_min": float(h.price_min or 0), "price_max": float(h.price_max or 0),
        "room_type": h.room_type, "available_rooms": h.available_rooms,
        "query_date": h.query_date.isoformat() if h.query_date else None,
        "data_source": h.data_source,
        "query_time": h.query_time.isoformat() if h.query_time else None,
    }


@router.get("/resources/cities")
def cities(db: Session = Depends(get_db)) -> list[str]:
    cached = cache_get_json(CITY_CACHE_KEY)
    if cached:
        return cached
    values = set(db.scalars(select(distinct(Poi.city)).where(Poi.deleted == 0)))
    values |= set(db.scalars(select(distinct(Hotel.city)).where(Hotel.deleted == 0)))
    values |= set(db.scalars(select(distinct(Restaurant.city)).where(Restaurant.deleted == 0)))
    result = sorted(v for v in values if v)
    cache_set_json(CITY_CACHE_KEY, result, CACHE_TTL_S)
    return result


@router.get("/resources/pois")
def pois(
    city: str | None = Query(None, max_length=64),
    keyword: str | None = Query(None, max_length=64),
    category: str | None = Query(None, max_length=32),
    page_params: PageParams = Depends(),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Poi).where(Poi.deleted == 0)
    if city:
        stmt = stmt.where(Poi.city == city)
    if keyword:
        stmt = stmt.where(or_(Poi.name.contains(keyword), Poi.category.contains(keyword)))
    if category:
        stmt = stmt.where(Poi.category == category)
    page = paginate(
        db, stmt, page_params,
        allowed_sort={"id": Poi.id, "name": Poi.name, "rating": Poi.rating,
                      "ticket_price": Poi.ticket_price,
                      "suggest_duration_min": Poi.suggest_duration_min},
        default_sort="id:asc",
    )
    page["items"] = [_poi_dict(p) for p in page["items"]]
    return page


@router.get("/resources/hotels")
def hotels(
    city: str | None = Query(None, max_length=64),
    keyword: str | None = Query(None, max_length=64),
    star: int | None = Query(None, ge=1, le=5),
    hotel_type: str | None = Query(None, max_length=32),
    page_params: PageParams = Depends(),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Hotel).where(Hotel.deleted == 0)
    if city:
        stmt = stmt.where(Hotel.city == city)
    if keyword:
        stmt = stmt.where(or_(Hotel.name.contains(keyword), Hotel.room_type.contains(keyword)))
    if star:
        stmt = stmt.where(Hotel.star == star)
    if hotel_type:
        stmt = stmt.where(Hotel.hotel_type == hotel_type)
    page = paginate(
        db, stmt, page_params,
        allowed_sort={"id": Hotel.id, "name": Hotel.name, "score": Hotel.score,
                      "price_min": Hotel.price_min},
        default_sort="id:asc",
    )
    page["items"] = [_hotel_dict(h) for h in page["items"]]
    return page


@router.get("/meta/styles")
def styles(db: Session = Depends(get_db)) -> list[dict]:
    cached = cache_get_json(STYLE_CACHE_KEY)
    if cached:
        return cached
    rows = db.scalars(select(TripStyle).where(TripStyle.deleted == 0)).all()
    if not rows:
        result = [
            {"style_code": code, "style_name": name, "min_poi_per_day": min_poi,
             "max_poi_per_day": max_poi, "pace": pace, "poi_weight": weight,
             "drive_limit_km": limit, "nap_required": nap}
            for code, (name, min_poi, max_poi, pace, weight, limit, nap) in DEFAULT_STYLES.items()
        ]
    else:
        result = [
            {"style_code": r.style_code, "style_name": r.style_name,
             "min_poi_per_day": r.min_poi_per_day, "max_poi_per_day": r.max_poi_per_day,
             "pace": r.pace, "poi_weight": r.poi_weight,
             "drive_limit_km": float(r.drive_limit_km or 0), "nap_required": r.nap_required,
             "description": r.description}
            for r in rows
        ]
    cache_set_json(STYLE_CACHE_KEY, result, CACHE_TTL_S)
    return result


@router.get("/meta/dictionaries")
def dictionaries(db: Session = Depends(get_db)) -> dict:
    """字典聚合接口：城市、风格与出行锦囊统一走 Redis 缓存。"""
    cached = cache_get_json(DICT_CACHE_KEY)
    if cached:
        return cached
    city_list = cities(db)
    style_list = styles(db)
    tips_rows = db.scalars(
        select(TravelTips)
        .where(TravelTips.status == 1, TravelTips.deleted == 0)
        .order_by(TravelTips.id)
        .limit(200)
    ).all()
    payload = {
        "cities": city_list,
        "styles": style_list,
        "tips": [
            {"id": r.id, "tips_code": r.tips_code, "title": r.title, "city": r.city,
             "category": r.category, "tags": r.tags}
            for r in tips_rows
        ],
        "tips_categories": sorted({r.category for r in tips_rows if r.category}),
    }
    cache_set_json(DICT_CACHE_KEY, payload, CACHE_TTL_S)
    return payload


@router.get("/tips")
def tips(
    city: str | None = Query(None, max_length=64),
    keyword: str | None = Query(None, max_length=64),
    category: str | None = Query(None, max_length=32),
    page_params: PageParams = Depends(),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(TravelTips).where(TravelTips.status == 1, TravelTips.deleted == 0)
    if city:
        stmt = stmt.where(or_(TravelTips.city == city, TravelTips.city.is_(None)))
    if keyword:
        stmt = stmt.where(or_(
            TravelTips.title.contains(keyword),
            TravelTips.content.contains(keyword),
            TravelTips.tags.contains(keyword),
        ))
    if category:
        stmt = stmt.where(TravelTips.category == category)
    page = paginate(
        db, stmt, page_params,
        allowed_sort={"id": TravelTips.id, "title": TravelTips.title},
        default_sort="id:asc",
    )
    page["items"] = [
        {"id": r.id, "tips_code": r.tips_code, "title": r.title, "city": r.city,
         "category": r.category, "content": r.content, "tags": r.tags, "source": r.source}
        for r in page["items"]
    ]
    cache_set_json(cache_key, page, CACHE_TTL_S)
    return page


@router.get("/tool-logs", dependencies=[Depends(require_permission("system:log:read"))])
def tool_logs(
    trace_id: str | None = Query(None, max_length=64),
    conversation_id: int | None = Query(None, ge=1),
    trip_id: int | None = Query(None, ge=1),
    status: str | None = Query(None, max_length=16),
    tool_type: str | None = Query(None, max_length=32),
    page_params: PageParams = Depends(),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(ToolCallLog).where(ToolCallLog.deleted == 0)
    if trace_id:
        stmt = stmt.where(ToolCallLog.trace_id == trace_id)
    if conversation_id:
        stmt = stmt.where(ToolCallLog.conversation_id == conversation_id)
    if trip_id:
        stmt = stmt.where(ToolCallLog.trip_id == trip_id)
    if status:
        stmt = stmt.where(ToolCallLog.status == status)
    if tool_type:
        stmt = stmt.where(ToolCallLog.tool_type == tool_type)
    page = paginate(
        db, stmt, page_params,
        allowed_sort={"id": ToolCallLog.id, "called_at": ToolCallLog.called_at,
                      "cost_ms": ToolCallLog.cost_ms},
        default_sort="id:desc",
    )
    page["items"] = [
        {"id": r.id, "call_id": r.call_id, "trace_id": r.trace_id, "tool_type": r.tool_type,
         "status": r.status, "degrade_flag": r.degrade_flag, "cost_ms": r.cost_ms,
         "result_count": r.result_count, "response_summary": r.response_summary,
         "error_code": r.error_code, "error_msg": r.error_msg,
         "called_at": r.called_at.isoformat() if r.called_at else None}
        for r in page["items"]
    ]
    return page

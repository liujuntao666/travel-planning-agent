from fastapi import APIRouter, Depends, Query
from sqlalchemy import distinct, or_, select
from sqlalchemy.orm import Session

from app.common.db import get_db
from app.itinerary.styles import DEFAULT_STYLES
from app.models import Hotel, Poi, Restaurant, ToolCallLog, TravelTips, TripStyle

router = APIRouter(tags=["resources"])


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
    values = set(db.scalars(select(distinct(Poi.city)).where(Poi.deleted == 0)))
    values |= set(db.scalars(select(distinct(Hotel.city)).where(Hotel.deleted == 0)))
    values |= set(db.scalars(select(distinct(Restaurant.city)).where(Restaurant.deleted == 0)))
    return sorted(v for v in values if v)


@router.get("/resources/pois")
def pois(city: str | None = None, keyword: str | None = None,
         db: Session = Depends(get_db)) -> list[dict]:
    stmt = select(Poi).where(Poi.deleted == 0)
    if city:
        stmt = stmt.where(Poi.city == city)
    if keyword:
        stmt = stmt.where(or_(Poi.name.contains(keyword), Poi.category.contains(keyword)))
    return [_poi_dict(p) for p in db.scalars(stmt.limit(100)).all()]


@router.get("/resources/hotels")
def hotels(city: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    stmt = select(Hotel).where(Hotel.deleted == 0)
    if city:
        stmt = stmt.where(Hotel.city == city)
    return [_hotel_dict(h) for h in db.scalars(stmt.limit(100)).all()]


@router.get("/meta/styles")
def styles(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(TripStyle).where(TripStyle.deleted == 0)).all()
    if not rows:
        return [
            {"style_code": code, "style_name": name, "min_poi_per_day": min_poi,
             "max_poi_per_day": max_poi, "pace": pace, "poi_weight": weight,
             "drive_limit_km": limit, "nap_required": nap}
            for code, (name, min_poi, max_poi, pace, weight, limit, nap) in DEFAULT_STYLES.items()
        ]
    return [
        {"style_code": r.style_code, "style_name": r.style_name,
         "min_poi_per_day": r.min_poi_per_day, "max_poi_per_day": r.max_poi_per_day,
         "pace": r.pace, "poi_weight": r.poi_weight,
         "drive_limit_km": float(r.drive_limit_km or 0), "nap_required": r.nap_required,
         "description": r.description}
        for r in rows
    ]


@router.get("/tips")
def tips(city: str | None = None, keyword: str | None = None,
         db: Session = Depends(get_db)) -> list[dict]:
    stmt = select(TravelTips).where(TravelTips.status == 1, TravelTips.deleted == 0)
    if city:
        stmt = stmt.where(or_(TravelTips.city == city, TravelTips.city.is_(None)))
    if keyword:
        stmt = stmt.where(or_(
            TravelTips.title.contains(keyword),
            TravelTips.content.contains(keyword),
            TravelTips.tags.contains(keyword),
        ))
    rows = db.scalars(stmt.limit(50)).all()
    return [
        {"id": r.id, "tips_code": r.tips_code, "title": r.title, "city": r.city,
         "category": r.category, "content": r.content, "tags": r.tags, "source": r.source}
        for r in rows
    ]


@router.get("/tool-logs")
def tool_logs(trace_id: str | None = None, conversation_id: int | None = None,
              trip_id: int | None = None, limit: int = Query(50, ge=1, le=200),
              db: Session = Depends(get_db)) -> list[dict]:
    stmt = select(ToolCallLog).where(ToolCallLog.deleted == 0)
    if trace_id:
        stmt = stmt.where(ToolCallLog.trace_id == trace_id)
    if conversation_id:
        stmt = stmt.where(ToolCallLog.conversation_id == conversation_id)
    if trip_id:
        stmt = stmt.where(ToolCallLog.trip_id == trip_id)
    rows = db.scalars(stmt.order_by(ToolCallLog.id.desc()).limit(limit)).all()
    return [
        {"id": r.id, "call_id": r.call_id, "trace_id": r.trace_id, "tool_type": r.tool_type,
         "status": r.status, "degrade_flag": r.degrade_flag, "cost_ms": r.cost_ms,
         "result_count": r.result_count, "response_summary": r.response_summary,
         "error_code": r.error_code, "error_msg": r.error_msg,
         "called_at": r.called_at.isoformat() if r.called_at else None}
        for r in rows
    ]

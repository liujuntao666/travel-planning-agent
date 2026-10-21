from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Hotel, Poi, Restaurant, TransportOption, Weather
from app.tools.base import ToolRequest

TRANSPORT_MODE_TYPE = {
    "飞机优先": "FLIGHT",
    "高铁优先": "HIGHSPEED",
    "火车优先": "TRAIN",
    "自驾": "CAR_RENTAL",
    "公交优先": "BUS",
}


def jsonable(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return value


def row_dict(row, fields: list[str]) -> dict:
    return {f: jsonable(getattr(row, f)) for f in fields}


POI_FIELDS = [
    "id", "poi_code", "name", "city", "address", "longitude", "latitude", "category",
    "ticket_price", "open_time_desc", "open_time_start", "open_time_end", "booking_required",
    "booking_channel", "booking_advance_days", "suggest_duration_min", "queue_minutes",
    "sunrise_time", "sunset_time", "rating", "data_source", "query_time",
]
HOTEL_FIELDS = [
    "id", "hotel_code", "name", "city", "address", "longitude", "latitude", "hotel_type",
    "star", "score", "price_min", "price_max", "room_type", "available_rooms", "query_date",
    "data_source", "query_time",
]
OPTION_FIELDS = [
    "id", "option_code", "transport_type", "carrier", "trip_no", "dep_city", "arr_city",
    "dep_station", "arr_station", "dep_time", "arr_time", "duration_min", "price",
    "seat_left", "transfer_desc", "query_date", "data_source", "query_time",
]
WEATHER_FIELDS = [
    "id", "city", "forecast_date", "weather_text", "temp_min", "temp_max", "wind",
    "humidity", "precipitation", "dressing_tip", "data_source", "query_time",
]
RESTAURANT_FIELDS = [
    "id", "restaurant_code", "name", "city", "address", "longitude", "latitude", "category",
    "avg_price", "score", "signature_dish", "open_time_desc", "local_must_flag",
    "data_source", "query_time",
]


def query_pois(db: Session, req: ToolRequest) -> list[dict]:
    rows = db.scalars(
        select(Poi).where(Poi.city.in_(req.dest_cities), Poi.deleted == 0)
    ).all()
    return [row_dict(r, POI_FIELDS) for r in rows]


def query_hotels(db: Session, req: ToolRequest) -> list[dict]:
    rows = db.scalars(
        select(Hotel).where(Hotel.city.in_(req.dest_cities), Hotel.deleted == 0)
    ).all()
    return [row_dict(r, HOTEL_FIELDS) for r in rows]


def query_transport(db: Session, req: ToolRequest) -> dict:
    legs: list[dict] = []
    route = [req.origin, *req.dest_cities, req.origin]
    preferred = TRANSPORT_MODE_TYPE.get(req.transport_mode or "", "")
    for i in range(len(route) - 1):
        dep, arr = route[i], route[i + 1]
        if dep == arr:
            continue
        stmt = select(TransportOption).where(
            TransportOption.dep_city == dep,
            TransportOption.arr_city == arr,
            TransportOption.deleted == 0,
        )
        rows = db.scalars(stmt).all()
        options = [row_dict(r, OPTION_FIELDS) for r in rows]
        options.sort(key=lambda o: (o["transport_type"] != preferred if preferred else False,
                                    o["price"] or 0))
        legs.append({"leg_index": i + 1, "from": dep, "to": arr, "options": options[:4]})
    return {"legs": legs}


def query_weather(db: Session, req: ToolRequest) -> dict:
    start = req.start_date or date.today()
    end = start + timedelta(days=max(req.day_count, 1) - 1)
    by_city: dict[str, list[dict]] = {}
    for city in req.dest_cities:
        rows = db.scalars(
            select(Weather).where(
                Weather.city == city,
                Weather.forecast_date >= start,
                Weather.forecast_date <= end,
                Weather.deleted == 0,
            )
        ).all()
        by_city[city] = [row_dict(r, WEATHER_FIELDS) for r in rows]
    return {"by_city": by_city}


def query_food(db: Session, req: ToolRequest) -> list[dict]:
    rows = db.scalars(
        select(Restaurant).where(Restaurant.city.in_(req.dest_cities), Restaurant.deleted == 0)
    ).all()
    return [row_dict(r, RESTAURANT_FIELDS) for r in rows]

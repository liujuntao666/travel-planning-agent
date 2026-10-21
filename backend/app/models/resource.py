from datetime import date, datetime, time

from sqlalchemy import Date, DateTime, Integer, Numeric, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, PKMixin


class Poi(Base, PKMixin, AuditMixin):
    __tablename__ = "t_poi"

    poi_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    city: Mapped[str | None] = mapped_column(String(64))
    address: Mapped[str | None] = mapped_column(String(255))
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 6))
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 6))
    category: Mapped[str | None] = mapped_column(String(32))
    ticket_price: Mapped[float | None] = mapped_column(Numeric(10, 2))
    open_time_desc: Mapped[str | None] = mapped_column(String(64))
    open_time_start: Mapped[time | None] = mapped_column(Time)
    open_time_end: Mapped[time | None] = mapped_column(Time)
    booking_required: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    booking_channel: Mapped[str | None] = mapped_column(String(128))
    booking_advance_days: Mapped[int | None] = mapped_column(Integer)
    suggest_duration_min: Mapped[int | None] = mapped_column(Integer)
    queue_minutes: Mapped[int | None] = mapped_column(Integer)
    sunrise_time: Mapped[time | None] = mapped_column(Time)
    sunset_time: Mapped[time | None] = mapped_column(Time)
    rating: Mapped[float | None] = mapped_column(Numeric(4, 2))
    data_source: Mapped[str | None] = mapped_column(String(32))
    query_time: Mapped[datetime | None] = mapped_column(DateTime)
    degrade_flag: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")


class Hotel(Base, PKMixin, AuditMixin):
    __tablename__ = "t_hotel"

    hotel_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    city: Mapped[str | None] = mapped_column(String(64))
    address: Mapped[str | None] = mapped_column(String(255))
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 6))
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 6))
    hotel_type: Mapped[str | None] = mapped_column(String(24), default="HOTEL", server_default="HOTEL")
    star: Mapped[int | None] = mapped_column(Integer)
    score: Mapped[float | None] = mapped_column(Numeric(4, 2))
    price_min: Mapped[float | None] = mapped_column(Numeric(10, 2))
    price_max: Mapped[float | None] = mapped_column(Numeric(10, 2))
    room_type: Mapped[str | None] = mapped_column(String(64))
    available_rooms: Mapped[int | None] = mapped_column(Integer)
    query_date: Mapped[date | None] = mapped_column(Date)
    data_source: Mapped[str | None] = mapped_column(String(32))
    query_time: Mapped[datetime | None] = mapped_column(DateTime)
    degrade_flag: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")


class TransportOption(Base, PKMixin, AuditMixin):
    __tablename__ = "t_transport_option"

    option_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    transport_type: Mapped[str] = mapped_column(String(24), nullable=False)
    carrier: Mapped[str | None] = mapped_column(String(64))
    trip_no: Mapped[str | None] = mapped_column(String(32))
    dep_city: Mapped[str | None] = mapped_column(String(64))
    arr_city: Mapped[str | None] = mapped_column(String(64))
    dep_station: Mapped[str | None] = mapped_column(String(128))
    arr_station: Mapped[str | None] = mapped_column(String(128))
    dep_time: Mapped[datetime | None] = mapped_column(DateTime)
    arr_time: Mapped[datetime | None] = mapped_column(DateTime)
    duration_min: Mapped[int | None] = mapped_column(Integer)
    price: Mapped[float | None] = mapped_column(Numeric(10, 2))
    seat_left: Mapped[int | None] = mapped_column(Integer)
    transfer_desc: Mapped[str | None] = mapped_column(String(255))
    query_date: Mapped[date | None] = mapped_column(Date)
    data_source: Mapped[str | None] = mapped_column(String(32))
    query_time: Mapped[datetime | None] = mapped_column(DateTime)
    degrade_flag: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")


class Weather(Base, PKMixin, AuditMixin):
    __tablename__ = "t_weather"

    city: Mapped[str] = mapped_column(String(64), nullable=False)
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False)
    weather_text: Mapped[str | None] = mapped_column(String(64))
    temp_min: Mapped[float | None] = mapped_column(Numeric(5, 1))
    temp_max: Mapped[float | None] = mapped_column(Numeric(5, 1))
    wind: Mapped[str | None] = mapped_column(String(64))
    humidity: Mapped[int | None] = mapped_column(Integer)
    precipitation: Mapped[float | None] = mapped_column(Numeric(5, 1))
    dressing_tip: Mapped[str | None] = mapped_column(String(255))
    data_source: Mapped[str | None] = mapped_column(String(32))
    query_time: Mapped[datetime | None] = mapped_column(DateTime)
    degrade_flag: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")


class Restaurant(Base, PKMixin, AuditMixin):
    __tablename__ = "t_restaurant"

    restaurant_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    city: Mapped[str | None] = mapped_column(String(64))
    address: Mapped[str | None] = mapped_column(String(255))
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 6))
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 6))
    category: Mapped[str | None] = mapped_column(String(32))
    avg_price: Mapped[float | None] = mapped_column(Numeric(10, 2))
    score: Mapped[float | None] = mapped_column(Numeric(4, 2))
    signature_dish: Mapped[str | None] = mapped_column(String(255))
    open_time_desc: Mapped[str | None] = mapped_column(String(64))
    local_must_flag: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    data_source: Mapped[str | None] = mapped_column(String(32))
    query_time: Mapped[datetime | None] = mapped_column(DateTime)
    degrade_flag: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")


class TravelTips(Base, PKMixin, AuditMixin):
    __tablename__ = "t_travel_tips"

    tips_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str | None] = mapped_column(String(64))
    category: Mapped[str | None] = mapped_column(String(32))
    content: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[int | None] = mapped_column(Integer, default=1, server_default="1")


class TripStyle(Base, PKMixin, AuditMixin):
    __tablename__ = "t_trip_style"

    style_code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    style_name: Mapped[str] = mapped_column(String(32), nullable=False)
    min_poi_per_day: Mapped[int | None] = mapped_column(Integer, default=1, server_default="1")
    max_poi_per_day: Mapped[int | None] = mapped_column(Integer, default=2, server_default="2")
    pace: Mapped[str | None] = mapped_column(String(16), default="宽松", server_default="宽松")
    poi_weight: Mapped[str | None] = mapped_column(String(255))
    drive_limit_km: Mapped[float | None] = mapped_column(Numeric(8, 2))
    nap_required: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    description: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[int | None] = mapped_column(Integer, default=1, server_default="1")

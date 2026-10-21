from datetime import date, datetime, time

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, PKMixin


class Trip(Base, PKMixin, AuditMixin):
    __tablename__ = "t_trip"

    trip_no: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("t_user.id"), nullable=False)
    conversation_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("t_conversation.id")
    )
    title: Mapped[str | None] = mapped_column(String(128))
    origin_city: Mapped[str | None] = mapped_column(String(64))
    dest_cities: Mapped[str | None] = mapped_column(String(255))
    day_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    night_count: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    people_count: Mapped[int | None] = mapped_column(Integer, default=2, server_default="2")
    budget_total: Mapped[float | None] = mapped_column(Numeric(12, 2))
    budget_level: Mapped[str | None] = mapped_column(String(16))
    style_code: Mapped[str] = mapped_column(
        String(32), ForeignKey("t_trip_style.style_code"), nullable=False,
        default="COMMON", server_default="COMMON",
    )
    transport_mode: Mapped[str | None] = mapped_column(String(32))
    taboos: Mapped[str | None] = mapped_column(String(255))
    current_version_no: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[int | None] = mapped_column(Integer, default=1, server_default="1")
    degrade_flag: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")


class TripVersion(Base, PKMixin, AuditMixin):
    __tablename__ = "t_trip_version"

    trip_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("t_trip.id"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    change_type: Mapped[str] = mapped_column(String(32), nullable=False, default="INIT", server_default="INIT")
    change_summary: Mapped[str | None] = mapped_column(String(512))
    base_version_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("t_trip_version.id")
    )
    content_json: Mapped[dict | None] = mapped_column(JSON)
    total_cost: Mapped[float | None] = mapped_column(Numeric(12, 2))
    current_flag: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    valid_flag: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")


class TripDay(Base, PKMixin, AuditMixin):
    __tablename__ = "t_trip_day"

    trip_version_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("t_trip_version.id"), nullable=False
    )
    day_index: Mapped[int] = mapped_column(Integer, nullable=False)
    day_date: Mapped[date | None] = mapped_column(Date)
    city: Mapped[str | None] = mapped_column(String(64))
    theme: Mapped[str | None] = mapped_column(String(128))
    pace: Mapped[str | None] = mapped_column(String(16))
    remark: Mapped[str | None] = mapped_column(String(512))


class TripItem(Base, PKMixin, AuditMixin):
    __tablename__ = "t_trip_item"

    trip_day_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("t_trip_day.id"), nullable=False
    )
    period: Mapped[str] = mapped_column(String(16), nullable=False)
    item_type: Mapped[str] = mapped_column(String(16), nullable=False, default="POI", server_default="POI")
    ref_id: Mapped[int | None] = mapped_column(BigInteger)
    ref_name: Mapped[str | None] = mapped_column(String(128))
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    duration_min: Mapped[int | None] = mapped_column(Integer)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    distance_km: Mapped[float | None] = mapped_column(Numeric(8, 2))
    travel_min: Mapped[int | None] = mapped_column(Integer)
    ticket_price: Mapped[float | None] = mapped_column(Numeric(10, 2))
    booking_required: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    booking_advance_days: Mapped[int | None] = mapped_column(Integer)
    degrade_flag: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    note: Mapped[str | None] = mapped_column(String(512))


class TripLodging(Base, PKMixin, AuditMixin):
    __tablename__ = "t_trip_lodging"

    trip_day_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("t_trip_day.id"), nullable=False
    )
    hotel_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("t_hotel.id"))
    hotel_name: Mapped[str | None] = mapped_column(String(128))
    room_type: Mapped[str | None] = mapped_column(String(64))
    check_in: Mapped[date | None] = mapped_column(Date)
    check_out: Mapped[date | None] = mapped_column(Date)
    nights: Mapped[int | None] = mapped_column(Integer, default=1, server_default="1")
    price_per_night: Mapped[float | None] = mapped_column(Numeric(10, 2))
    total_price: Mapped[float | None] = mapped_column(Numeric(10, 2))
    distance_to_scenic: Mapped[float | None] = mapped_column(Numeric(8, 2))
    score: Mapped[float | None] = mapped_column(Numeric(4, 2))
    degrade_flag: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")


class TripTransport(Base, PKMixin, AuditMixin):
    __tablename__ = "t_trip_transport"

    trip_version_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("t_trip_version.id"), nullable=False
    )
    leg_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    transport_type: Mapped[str] = mapped_column(String(24), nullable=False)
    option_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("t_transport_option.id")
    )
    carrier: Mapped[str | None] = mapped_column(String(64))
    trip_no: Mapped[str | None] = mapped_column(String(32))
    from_city: Mapped[str | None] = mapped_column(String(64))
    to_city: Mapped[str | None] = mapped_column(String(64))
    dep_station: Mapped[str | None] = mapped_column(String(128))
    arr_station: Mapped[str | None] = mapped_column(String(128))
    dep_time: Mapped[datetime | None] = mapped_column(DateTime)
    arr_time: Mapped[datetime | None] = mapped_column(DateTime)
    duration_min: Mapped[int | None] = mapped_column(Integer)
    price: Mapped[float | None] = mapped_column(Numeric(10, 2))
    transfer_desc: Mapped[str | None] = mapped_column(String(255))
    degrade_flag: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")


class TripExport(Base, PKMixin, AuditMixin):
    __tablename__ = "t_trip_export"

    export_no: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    trip_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("t_trip.id"), nullable=False)
    trip_version_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("t_trip_version.id"), nullable=False
    )
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    file_url: Mapped[str | None] = mapped_column(String(512))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    page_count: Mapped[int | None] = mapped_column(Integer)
    degrade_notice_count: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[int | None] = mapped_column(Integer, default=1, server_default="1")
    fail_reason: Mapped[str | None] = mapped_column(String(255))

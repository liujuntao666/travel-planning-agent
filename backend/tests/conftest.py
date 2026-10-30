import os
import tempfile
from datetime import date, datetime, time

import pytest

TMP_DIR = tempfile.mkdtemp(prefix="travel-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{TMP_DIR}/test.db"
os.environ["AUTO_CREATE_TABLES"] = "true"
os.environ["EXPORT_DIR"] = f"{TMP_DIR}/exports"
os.environ["FILE_DIR"] = f"{TMP_DIR}/files"
os.environ["CHUNK_DIR"] = f"{TMP_DIR}/chunks"
os.environ["TOOL_TIMEOUT_MS"] = "5000"

from fastapi.testclient import TestClient  # noqa: E402

from app.common.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Base,
    Hotel,
    Poi,
    Restaurant,
    TransportOption,
    TravelTips,
    TripStyle,
    Weather,
)


def seed_resources() -> None:
    db = SessionLocal()
    try:
        styles = [
            ("COMMON", "均衡", 1, 2, "适中", "景观:2,街区:2,博物馆:1", 120, 0),
            ("RELAX", "休闲", 1, 2, "宽松", "景观:3,街区:2,咖啡馆:1", 100, 0),
            ("FAMILY", "家庭", 2, 2, "宽松", "亲子乐园:3,动植物园:2,博物馆:2", 90, 1),
            ("PHOTO", "摄影", 1, 3, "紧凑", "日出日落机位:3,景观:2", 150, 0),
        ]
        for code, name, min_poi, max_poi, pace, weight, limit, nap in styles:
            db.add(TripStyle(style_code=code, style_name=name, min_poi_per_day=min_poi,
                             max_poi_per_day=max_poi, pace=pace, poi_weight=weight,
                             drive_limit_km=limit, nap_required=nap, status=1))
        pois = [
            ("POI-DL-0001", "大理古城", "大理", 100.164, 25.692, "人文", 0, 210, 0, 4.62),
            ("POI-DL-0002", "洱海生态廊道", "大理", 100.19, 25.76, "自然", 0, 180, 0, 4.7),
            ("POI-DL-0003", "喜洲古镇", "大理", 100.133, 25.856, "人文", 0, 180, 0, 4.55),
            ("POI-LJ-0001", "丽江古城", "丽江", 100.234, 26.872, "人文", 0, 210, 0, 4.66),
            ("POI-LJ-0002", "玉龙雪山", "丽江", 100.186, 27.1, "自然", 240, 300, 1, 4.71),
        ]
        for code, name, city, lon, lat, category, price, duration, booking, rating in pois:
            db.add(Poi(
                poi_code=code, name=name, city=city, longitude=lon, latitude=lat,
                category=category, ticket_price=price, open_time_desc="08:00-18:00",
                open_time_start=time(8), open_time_end=time(18), booking_required=booking,
                booking_channel="官方公众号实名预约" if booking else None,
                booking_advance_days=3 if booking else None,
                suggest_duration_min=duration, queue_minutes=10, rating=rating,
                data_source="TEST_POI_API", query_time=datetime.now(),
            ))
        hotels = [
            ("HT-DL-0001", "大理古城观景民宿", "大理", 100.165, 25.693, 4, 4.72, 380, 460, "观景大床房", 6),
            ("HT-DL-0002", "洱海海景酒店", "大理", 100.188, 25.758, 5, 4.68, 520, 680, "海景双床房", 3),
            ("HT-LJ-0001", "丽江古城客栈", "丽江", 100.233, 26.873, 4, 4.75, 320, 420, "庭院大床房", 9),
        ]
        for code, name, city, lon, lat, star, score, pmin, pmax, room, rooms in hotels:
            db.add(Hotel(
                hotel_code=code, name=name, city=city, longitude=lon, latitude=lat,
                hotel_type="HOMESTAY", star=star, score=score, price_min=pmin, price_max=pmax,
                room_type=room, available_rooms=rooms, query_date=date(2026, 10, 20),
                data_source="TEST_HOTEL_API", query_time=datetime.now(),
            ))
        options = [
            ("OP-1", "HIGHSPEED", "中国铁路", "G2836", "成都", "大理", "成都南站", "大理站",
             datetime(2026, 10, 20, 7, 30), datetime(2026, 10, 20, 13, 5), 335, 462, 42),
            ("OP-2", "HIGHSPEED", "中国铁路", "D8788", "大理", "丽江", "大理站", "丽江站",
             datetime(2026, 10, 22, 9, 12), datetime(2026, 10, 22, 11, 5), 113, 136, 88),
            ("OP-3", "HIGHSPEED", "中国铁路", "G2838", "丽江", "成都", "丽江站", "成都南站",
             datetime(2026, 10, 24, 9, 40), datetime(2026, 10, 24, 17, 20), 460, 512, 21),
        ]
        for code, ttype, carrier, no, dep, arr, dstation, astation, dep_t, arr_t, minutes, price, seats in options:
            db.add(TransportOption(
                option_code=code, transport_type=ttype, carrier=carrier, trip_no=no,
                dep_city=dep, arr_city=arr, dep_station=dstation, arr_station=astation,
                dep_time=dep_t, arr_time=arr_t, duration_min=minutes, price=price, seat_left=seats,
                query_date=dep_t.date(), data_source="TEST_TRANSPORT_API", query_time=datetime.now(),
            ))
        for idx, (city, day) in enumerate(
            [("大理", 20), ("大理", 21), ("丽江", 22), ("丽江", 23), ("丽江", 24)]
        ):
            db.add(Weather(
                city=city, forecast_date=date(2026, 10, day), weather_text="晴", temp_min=10,
                temp_max=22, wind="西南风 2 级", humidity=55, precipitation=0,
                dressing_tip="早晚温差大，建议薄外套", data_source="TEST_WEATHER_API",
                query_time=datetime.now(),
            ))
        restaurants = [
            ("RS-DL-1", "大理白族风味馆", "大理", 100.166, 25.694, "老字号", 68, 1),
            ("RS-DL-2", "喜洲小吃街", "大理", 100.132, 25.855, "小吃街", 45, 1),
            ("RS-LJ-1", "丽江腊排骨火锅", "丽江", 100.228, 26.879, "火锅", 88, 1),
            ("RS-LJ-2", "丽江古城小吃铺", "丽江", 100.235, 26.872, "小吃", 38, 0),
        ]
        for code, name, city, lon, lat, category, avg, must in restaurants:
            db.add(Restaurant(
                restaurant_code=code, name=name, city=city, longitude=lon, latitude=lat,
                category=category, avg_price=avg, score=4.6, signature_dish="本地风味",
                open_time_desc="10:00-21:00", local_must_flag=must,
                data_source="TEST_FOOD_API", query_time=datetime.now(),
            ))
        db.add(TravelTips(
            tips_code="TIP-1", title="玉龙雪山索道需提前预约", city="丽江", category="预约",
            content="大索道每日限量，需提前 1～3 天实名预约。", tags="丽江,预约", source="官方公告",
            status=1,
        ))
        db.add(TravelTips(
            tips_code="TIP-2", title="证件与保险准备", city=None, category="签证",
            content="身份证、驾照随身携带，徒步建议购买旅行保险。", tags="通用,证件", source="锦囊",
            status=1,
        ))
        db.commit()
    finally:
        db.close()


@pytest.fixture(scope="session")
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_resources()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def user(client):
    resp = client.post("/api/v1/users/login", json={"open_id": "wx_test_001", "nickname": "测试游客"})
    assert resp.status_code == 200, resp.text
    return resp.json()

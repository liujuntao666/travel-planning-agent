import math
import re
from datetime import time

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float | None, lon1: float | None,
                 lat2: float | None, lon2: float | None) -> float:
    if None in (lat1, lon1, lat2, lon2):
        return 0.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)  # type: ignore[operator]
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a)), 2)


def travel_minutes(km: float) -> int:
    if km <= 0:
        return 0
    if km <= 3:
        return max(5, int(km * 4))
    return int(km * 2.2) + 5


def parse_time(value) -> time | None:
    if value is None:
        return None
    if isinstance(value, time):
        return value
    text = str(value)
    m = re.match(r"(\d{1,2}):(\d{2})", text)
    if not m:
        return None
    return time(int(m.group(1)) % 24, int(m.group(2)) % 60)


def to_minutes(value: str | time | None, default: int = 0) -> int:
    t = parse_time(value)
    if t is None:
        return default
    return t.hour * 60 + t.minute


def from_minutes(minutes: int) -> str:
    minutes = max(0, min(minutes, 23 * 60 + 59))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def overlap(start_a: str, end_a: str, start_b: str, end_b: str) -> bool:
    return to_minutes(start_a) < to_minutes(end_b) and to_minutes(start_b) < to_minutes(end_a)

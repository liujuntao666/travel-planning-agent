from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TripStyle

DEFAULT_STYLES = {
    "COMMON": ("均衡", 1, 2, "适中", "景观:2,街区:2,博物馆:1", 120, 0),
    "RELAX": ("休闲", 1, 2, "宽松", "景观:3,街区:2,咖啡馆:1", 100, 0),
    "COUPLE": ("情侣", 1, 2, "宽松", "景观:3,街区:2,咖啡馆:2", 100, 0),
    "FAMILY": ("家庭", 2, 2, "宽松", "亲子乐园:3,动植物园:2,博物馆:2", 90, 1),
    "KIDS": ("亲子", 2, 2, "宽松", "亲子乐园:3,动植物园:2,博物馆:2", 90, 1),
    "HIKE": ("徒步", 1, 3, "紧凑", "自然线路:3,山野:2", 150, 0),
    "PHOTO": ("摄影", 1, 3, "紧凑", "日出日落机位:3,景观:2", 150, 0),
    "FOOD": ("美食", 2, 2, "随餐安排", "市集:3,老字号:2,小吃街:2", 80, 0),
}


@dataclass
class StyleConfig:
    code: str
    name: str
    min_poi: int
    max_poi: int
    pace: str
    weights: dict[str, int] = field(default_factory=dict)
    drive_limit_km: float = 120.0
    nap_required: bool = False
    description: str = ""

    def weight_for(self, category: str | None) -> int:
        if not category:
            return 1
        for key, value in self.weights.items():
            if key and key in category:
                return value
        return 1


def _parse_weights(raw: str | None) -> dict[str, int]:
    if not raw:
        return {}
    result = {}
    for part in raw.split(","):
        if ":" in part:
            key, _, value = part.partition(":")
            try:
                result[key.strip()] = int(value.strip())
            except ValueError:
                continue
    return result


def get_style(db: Session, code: str) -> StyleConfig:
    row = db.scalar(select(TripStyle).where(TripStyle.style_code == code, TripStyle.deleted == 0))
    if row:
        return StyleConfig(
            code=row.style_code,
            name=row.style_name,
            min_poi=row.min_poi_per_day or 1,
            max_poi=row.max_poi_per_day or 2,
            pace=row.pace or "宽松",
            weights=_parse_weights(row.poi_weight),
            drive_limit_km=float(row.drive_limit_km or 120),
            nap_required=bool(row.nap_required),
            description=row.description or "",
        )
    name, min_poi, max_poi, pace, raw, limit, nap = DEFAULT_STYLES.get(code, DEFAULT_STYLES["COMMON"])
    return StyleConfig(code, name, min_poi, max_poi, pace, _parse_weights(raw), float(limit), bool(nap))

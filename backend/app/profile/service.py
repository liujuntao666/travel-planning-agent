"""用户行为采集与规则打标：规则优先、可解释、可按用户整体清除。"""
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import TagDict, Trip, TripExport, UserEvent, UserTag

# 事件保留期：超期只保留聚合结果，原始行为明细删除
EVENT_RETENTION_DAYS = 180

BUDGET_MAP = {"经济": "BUDGET_ECONOMY", "舒适": "BUDGET_COMFORT", "高端": "BUDGET_LUXURY"}


def record_event(
    db: Session,
    user_id: int,
    event_type: str,
    target_type: str | None = None,
    target_id: int | None = None,
) -> None:
    db.add(
        UserEvent(
            user_id=user_id,
            event_type=event_type,
            target_type=target_type,
            target_id=target_id,
        )
    )


def _top(counter: Counter) -> tuple[str, float] | None:
    if not counter:
        return None
    total = sum(counter.values())
    code, count = counter.most_common(1)[0]
    return code, count / total


def _length_code(day_count: int) -> str:
    if day_count <= 3:
        return "LENGTH_SHORT"
    if day_count >= 7:
        return "LENGTH_LONG"
    return "LENGTH_MEDIUM"


def compute_rules(db: Session, user_id: int) -> list[dict]:
    trips = list(
        db.scalars(select(Trip).where(Trip.user_id == user_id, Trip.deleted == 0))
    )
    results: list[dict] = []

    budget = _top(Counter(t.budget_level for t in trips if t.budget_level in BUDGET_MAP))
    if budget:
        results.append(
            {
                "tag_code": BUDGET_MAP[budget[0]],
                "score": round(budget[1] * 100, 2),
                "confidence": round(budget[1], 4),
            }
        )

    length = _top(Counter(_length_code(t.day_count) for t in trips))
    if length:
        results.append(
            {
                "tag_code": length[0],
                "score": round(length[1] * 100, 2),
                "confidence": round(length[1], 4),
            }
        )

    style = _top(Counter(t.style_code for t in trips if t.style_code))
    if style:
        results.append(
            {
                "tag_code": f"STYLE_{style[0]}",
                "score": round(style[1] * 100, 2),
                "confidence": round(style[1], 4),
            }
        )

    if trips:
        since = datetime.now() - timedelta(days=30)
        event_count = (
            db.scalar(
                select(func.count(UserEvent.id)).where(
                    UserEvent.user_id == user_id,
                    UserEvent.deleted == 0,
                    UserEvent.created_at >= since,
                )
            )
            or 0
        )
        score = min(100, event_count * 8 + len(trips) * 15)
        code = "ACTIVITY_HIGH" if score >= 60 else ("ACTIVITY_MEDIUM" if score >= 25 else "ACTIVITY_LOW")
        results.append({"tag_code": code, "score": float(score), "confidence": 0.9})

    exports = _top(
        Counter(
            db.scalars(
                select(TripExport.format)
                .join(Trip, Trip.id == TripExport.trip_id)
                .where(
                    Trip.user_id == user_id,
                    TripExport.deleted == 0,
                    TripExport.status == 2,
                )
            )
        )
    )
    if exports:
        results.append(
            {
                "tag_code": f"EXPORT_{exports[0]}",
                "score": round(exports[1] * 100, 2),
                "confidence": round(exports[1], 4),
            }
        )

    return results


def list_user_tags(db: Session, user_id: int) -> list[dict]:
    rows = db.execute(
        select(UserTag, TagDict)
        .join(TagDict, TagDict.tag_code == UserTag.tag_code)
        .where(
            UserTag.user_id == user_id,
            UserTag.deleted == 0,
            TagDict.status == 1,
            TagDict.deleted == 0,
        )
        .order_by(TagDict.sort_no, UserTag.id)
    ).all()
    return [
        {
            "tag_code": tag.tag_code,
            "tag_name": dict_.tag_name,
            "category": dict_.category,
            "description": dict_.description,
            "score": float(tag.score),
            "confidence": float(tag.confidence),
            "source": tag.source,
            "updated_at": tag.updated_at.isoformat() if tag.updated_at else None,
        }
        for tag, dict_ in rows
    ]


def refresh_user_tags(db: Session, user_id: int) -> list[dict]:
    known = {
        item.tag_code: item
        for item in db.scalars(select(TagDict).where(TagDict.status == 1, TagDict.deleted == 0))
    }
    computed = [item for item in compute_rules(db, user_id) if item["tag_code"] in known]

    db.execute(delete(UserTag).where(UserTag.user_id == user_id))
    for item in computed:
        db.add(
            UserTag(
                user_id=user_id,
                tag_code=item["tag_code"],
                score=item["score"],
                confidence=item["confidence"],
                source="RULE",
            )
        )
    db.flush()

    cutoff = datetime.now() - timedelta(days=EVENT_RETENTION_DAYS)
    db.execute(
        delete(UserEvent).where(UserEvent.user_id == user_id, UserEvent.created_at < cutoff)
    )
    return list_user_tags(db, user_id)


def clear_user_tags(db: Session, user_id: int) -> int:
    result = db.execute(delete(UserTag).where(UserTag.user_id == user_id))
    return result.rowcount or 0

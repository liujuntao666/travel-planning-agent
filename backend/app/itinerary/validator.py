from app.itinerary.geo import overlap, to_minutes
from app.itinerary.styles import StyleConfig


def validate_plan(plan: dict, style: StyleConfig) -> list[dict]:
    """时段冲突 / 距离 / 开放时间 / 节奏校验（NFR-04）。"""
    issues: list[dict] = []

    for day in plan.get("days", []):
        items = day.get("items", [])
        timed = [i for i in items if i.get("start_time") and i.get("end_time")]
        for idx, a in enumerate(timed):
            for b in timed[idx + 1:]:
                if overlap(a["start_time"], a["end_time"], b["start_time"], b["end_time"]):
                    issues.append({
                        "level": "ERROR",
                        "day_index": day["day_index"],
                        "type": "TIME_OVERLAP",
                        "message": f"「{a['ref_name']}」与「{b['ref_name']}」时段重叠",
                    })

        drive_km = sum(float(i.get("distance_km") or 0) for i in items)
        if drive_km > style.drive_limit_km:
            issues.append({
                "level": "WARN",
                "day_index": day["day_index"],
                "type": "DRIVE_LIMIT",
                "message": f"当日移动约 {drive_km:.1f} km，超过「{style.name}」风格上限 {style.drive_limit_km:.0f} km",
            })

        poi_count = sum(1 for i in items if i.get("item_type") == "POI")
        if poi_count > style.max_poi + 1:
            issues.append({
                "level": "WARN",
                "day_index": day["day_index"],
                "type": "PACE",
                "message": f"当日安排 {poi_count} 个主点位，超出「{style.name}」节奏建议",
            })

        for item in items:
            if item.get("item_type") != "POI" or not item.get("start_time"):
                continue
            open_start = item.get("_open_start")
            open_end = item.get("_open_end")
            if open_start and to_minutes(item["start_time"]) < to_minutes(open_start):
                issues.append({
                    "level": "WARN",
                    "day_index": day["day_index"],
                    "type": "OPEN_TIME",
                    "message": f"「{item['ref_name']}」计划到达早于开放时间 {open_start}",
                })
            if open_end and to_minutes(item["end_time"]) > to_minutes(open_end):
                issues.append({
                    "level": "WARN",
                    "day_index": day["day_index"],
                    "type": "OPEN_TIME",
                    "message": f"「{item['ref_name']}」计划结束晚于闭园时间 {open_end}",
                })

    return issues

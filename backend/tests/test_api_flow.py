import itertools

from app.common.config import settings

FIRST_MESSAGE = "想去云南玩5天4晚，预算6000元，两个人，休闲一点，高铁优先，不要购物"
SECOND_MESSAGE = "我从成都出发"


def _create_conversation(client, user) -> int:
    resp = client.post("/api/v1/conversations", json={"user_id": user["id"]})
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _assert_no_overlap(plan: dict) -> None:
    for day in plan["days"]:
        timed = [i for i in day["items"] if i.get("start_time") and i.get("end_time")]
        for a, b in itertools.combinations(timed, 2):
            assert not (a["start_time"] < b["end_time"] and b["start_time"] < a["end_time"]), (
                f"Day {day['day_index']} 「{a['ref_name']}」与「{b['ref_name']}」时段重叠"
            )


def test_plan_flow_adjust_edit_export(client, user):
    conversation_id = _create_conversation(client, user)

    # 第一条消息缺少出发地，应逐项追问
    resp = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": FIRST_MESSAGE, "start_date": "2026-10-20"},
    )
    assert resp.status_code == 200, resp.text
    first = resp.json()
    assert first["missing_slots"] == ["ORIGIN"]
    assert "出发" in first["reply"]
    assert first["trip"] is None

    # 补齐出发地后生成行程
    resp = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": SECOND_MESSAGE, "start_date": "2026-10-20"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["intent"] == "NEW_PLAN"
    assert body["missing_slots"] == []
    plan = body["trip"]
    assert plan["trip"]["day_count"] == 5
    assert len(plan["days"]) == 5
    assert plan["valid_flag"] is True
    _assert_no_overlap(plan)

    poi_names = [
        item["ref_name"]
        for day in plan["days"] for item in day["items"] if item["item_type"] == "POI"
    ]
    assert len(poi_names) == len(set(poi_names)), "同一景点不应重复出现在多天"
    meal_types = [
        item for day in plan["days"] for item in day["items"] if item["item_type"] == "RESTAURANT"
    ]
    assert meal_types, "完整行程应至少安排一顿正餐"
    assert plan["budget"]["total"] > 0
    trip_id = plan["id"]

    # 多轮调整：加一天 -> 生成新版本
    resp = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "加一天", "start_date": "2026-10-20"},
    )
    assert resp.status_code == 200, resp.text
    adjusted = resp.json()
    assert adjusted["intent"] == "ADJUST"
    assert adjusted["trip"]["trip"]["day_count"] == 6
    assert len(adjusted["trip"]["days"]) == 6
    _assert_no_overlap(adjusted["trip"])

    versions = client.get(f"/api/v1/trips/{trip_id}/versions").json()
    assert len(versions) == 2
    assert versions[0]["current_flag"] == 1

    # 手动编辑：修改备注并产生新版本
    day_items = [
        item for day in adjusted["trip"]["days"] for item in day["items"] if item.get("id")
    ]
    assert day_items
    item_id = day_items[0]["id"]
    resp = client.patch(
        f"/api/v1/trips/{trip_id}/items/{item_id}",
        json={"note": "雨天备选室内方案"},
    )
    assert resp.status_code == 200, resp.text
    edited = resp.json()
    versions = client.get(f"/api/v1/trips/{trip_id}/versions").json()
    assert len(versions) == 3
    edited_item = next(
        i for day in edited["days"] for i in day["items"] if i.get("note") == "雨天备选室内方案"
    )
    assert edited_item["id"]

    # 版本对比
    base_id = min(v["id"] for v in versions)
    target_id = max(v["id"] for v in versions)
    resp = client.get(
        f"/api/v1/trips/{trip_id}/versions/compare", params={"base": base_id, "target": target_id}
    )
    assert resp.status_code == 200, resp.text
    compare = resp.json()
    assert {"added", "removed", "cost_delta", "summary"} <= set(compare)

    # 导出 PDF 与微信长文
    resp = client.post(f"/api/v1/trips/{trip_id}/exports", json={"format": "PDF"})
    assert resp.status_code == 200, resp.text
    export = resp.json()
    assert export["status"] == 2, export.get("fail_reason")
    assert export["file_url"].startswith(settings.static_mount)
    file_resp = client.get(export["file_url"])
    assert file_resp.status_code == 200
    assert file_resp.content[:4] == b"%PDF"

    resp = client.post(f"/api/v1/trips/{trip_id}/exports", json={"format": "WECHAT_ARTICLE"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == 2

    exports = client.get(f"/api/v1/trips/{trip_id}/exports").json()
    assert len(exports) == 2


def test_stream_message(client, user):
    conversation_id = _create_conversation(client, user)
    resp = client.post(
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        json={"content": "我从重庆出发，想去三亚玩4天3晚", "start_date": "2026-10-20"},
    )
    assert resp.status_code == 200, resp.text
    text = resp.text
    assert "event: start" in text
    assert "event: slots" in text
    assert "event: done" in text
    assert "event: error" not in text


def test_tool_logs_recorded(client):
    resp = client.get("/api/v1/tool-logs", params={"limit": 20})
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert rows
    assert {"tool_type", "status", "degrade_flag"} <= set(rows[0])

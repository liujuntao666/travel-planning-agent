import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.agent_core.audit import audit_text
from app.agent_core.intent import INTENT_ADJUST, INTENT_CONSULT, INTENT_NEW, detect_intent
from app.agent_core.llm import llm_client
from app.agent_core.slots import (
    REQUIRED_SLOTS,
    SLOT_KEYS,
    ExtractedSlot,
    clarify_question,
    extract_slots,
    slot_label,
)
from app.common.config import settings
from app.common.errors import NotFoundError
from app.common.logging import get_logger
from app.itinerary.engine import PlanInput, build_plan
from app.itinerary.service import (
    create_plan,
    current_version,
    save_version,
    serialize_trip,
)
from app.itinerary.styles import get_style
from app.models import Conversation, Message, RequirementSlot, TravelTips, Trip, User
from app.tools.base import ToolRequest
from app.tools.gateway import collect

log = get_logger(__name__)

DEST_ALIASES = {
    "云南": ["大理", "丽江"],
    "滇": ["大理", "丽江"],
    "大理": ["大理"],
    "丽江": ["丽江"],
    "昆明": ["昆明"],
    "西双版纳": ["西双版纳"],
    "香格里拉": ["香格里拉"],
    "成都": ["成都"],
    "重庆": ["重庆"],
    "西安": ["西安"],
    "北京": ["北京"],
    "上海": ["上海"],
    "三亚": ["三亚"],
    "厦门": ["厦门"],
    "杭州": ["杭州"],
}


@dataclass
class ChatResult:
    conversation_id: int
    intent: str
    reply: str
    slots: dict[str, str] = field(default_factory=dict)
    missing_slots: list[str] = field(default_factory=list)
    trip: dict | None = None
    tool_calls: list[dict] = field(default_factory=list)
    degraded: list[str] = field(default_factory=list)
    trace_id: str | None = None
    latency_ms: int = 0
    user_message_id: int | None = None
    assistant_message_id: int | None = None

    def as_dict(self) -> dict:
        return {
            "conversation_id": self.conversation_id,
            "intent": self.intent,
            "reply": self.reply,
            "slots": self.slots,
            "missing_slots": self.missing_slots,
            "trip": self.trip,
            "tool_calls": self.tool_calls,
            "degraded": self.degraded,
            "trace_id": self.trace_id,
            "latency_ms": self.latency_ms,
            "user_message_id": self.user_message_id,
            "assistant_message_id": self.assistant_message_id,
        }


def get_or_create_user(db: Session, open_id: str, nickname: str | None = None,
                       source: str = "APP") -> User:
    user = db.scalar(select(User).where(User.open_id == open_id, User.deleted == 0))
    if not user:
        user = User(open_id=open_id, nickname=nickname or "旅行者", source=source, status=1)
        db.add(user)
        db.flush()
    user.last_login_at = datetime.now()
    if nickname:
        user.nickname = nickname
    return user


def create_conversation(db: Session, user: User, title: str | None = None) -> Conversation:
    conversation = Conversation(user_id=user.id, title=title or "新的旅行规划", status=1, message_count=0)
    db.add(conversation)
    db.flush()
    return conversation


def _message(db: Session, conversation: Conversation, role: str, content: str,
             intent: str | None = None, stream_flag: int = 0, latency_ms: int = 0) -> Message:
    seq = (db.scalar(
        select(func.max(Message.seq)).where(Message.conversation_id == conversation.id)
    ) or 0) + 1
    message = Message(
        conversation_id=conversation.id,
        seq=seq,
        role=role,
        content=content,
        content_type="MARKDOWN" if role == "ASSISTANT" else "TEXT",
        intent=intent,
        stream_flag=stream_flag,
        token_count=max(0, len(content) // 2),
        latency_ms=latency_ms,
    )
    db.add(message)
    db.flush()
    conversation.message_count = seq
    conversation.last_message_at = datetime.now()
    return message


def _load_slot_map(db: Session, conversation: Conversation) -> dict[str, RequirementSlot]:
    rows = db.scalars(
        select(RequirementSlot).where(
            RequirementSlot.conversation_id == conversation.id,
            RequirementSlot.deleted == 0,
        )
    ).all()
    return {row.slot_key: row for row in rows}


def _upsert_slots(db: Session, conversation: Conversation,
                  extracted: dict[str, ExtractedSlot], trip_id: int | None = None) -> None:
    existing = _load_slot_map(db, conversation)
    for key, slot in extracted.items():
        if key not in SLOT_KEYS:
            continue
        required = 1 if key in REQUIRED_SLOTS else 0
        row = existing.get(key)
        if row:
            row.slot_value = slot.value
            row.value_type = slot.value_type
            row.filled_flag = 1 if slot.value else 0
            row.confidence = slot.confidence
            row.slot_source = slot.source
            row.required_flag = required
            if trip_id:
                row.trip_id = trip_id
        else:
            db.add(RequirementSlot(
                conversation_id=conversation.id,
                trip_id=trip_id,
                slot_key=key,
                slot_value=slot.value,
                value_type=slot.value_type,
                required_flag=required,
                filled_flag=1 if slot.value else 0,
                confidence=slot.confidence,
                slot_source=slot.source,
            ))
    db.flush()


def _slot_values(db: Session, conversation: Conversation) -> dict[str, str]:
    return {
        row.slot_key: row.slot_value or ""
        for row in _load_slot_map(db, conversation).values()
        if row.slot_value
    }


def _missing(db: Session, conversation: Conversation) -> list[str]:
    rows = _load_slot_map(db, conversation)
    return [key for key in REQUIRED_SLOTS if not rows.get(key) or not rows.get(key).filled_flag]


def _ask_clarify(db: Session, conversation: Conversation, key: str) -> None:
    row = _load_slot_map(db, conversation).get(key)
    if row:
        row.ask_count = (row.ask_count or 0) + 1
    _message(db, conversation, "ASSISTANT", clarify_question(key), intent=INTENT_NEW)


def _parse_days(value: str) -> tuple[int, int]:
    m = re.search(r"(\d+)\s*天\s*(\d+)\s*晚", value or "")
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"(\d+)", value or "")
    days = int(m.group(1)) if m else 3
    return days, max(0, days - 1)


def resolve_cities(db: Session, raw: str) -> list[str]:
    raw = raw.strip()
    if not raw:
        return []
    raw = raw.replace("省", "").replace("市", "")
    known = set(db.scalars(select(TravelTips.city).where(TravelTips.city.is_not(None))))
    hits: list[tuple[int, list[str]]] = []
    for alias, cities in DEST_ALIASES.items():
        index = raw.find(alias)
        if index >= 0:
            hits.append((index, cities))
    if hits:
        matched: list[str] = []
        for _, cities in sorted(hits, key=lambda hit: hit[0]):
            for city in cities:
                if city not in matched:
                    matched.append(city)
        return matched[:3]
    tokens = [t.strip() for t in re.split(r"[、/+,，和\s]+", raw) if t.strip()]
    tokens = [t for t in tokens if t in known] or tokens
    return tokens[:3] if tokens else [raw]


def _plan_input_from_slots(db: Session, slots: dict[str, str],
                           start_date: date | None = None) -> PlanInput | None:
    if not slots.get("ORIGIN") or not slots.get("DEST"):
        return None
    days, _ = _parse_days(slots.get("NIGHTS", "3天2晚"))
    days = max(1, min(days, settings.max_day_count))
    people = int(float(slots.get("PEOPLE") or 2))
    people = max(1, min(people, settings.max_people))
    budget = float(slots["BUDGET"]) if slots.get("BUDGET") else None
    taboos = [t for t in (slots.get("TABOO") or "").split(",") if t]
    return PlanInput(
        origin=slots["ORIGIN"],
        dest_cities=resolve_cities(db, slots["DEST"]),
        day_count=days,
        people=people,
        budget_total=budget,
        style_code=slots.get("STYLE") or "COMMON",
        transport_mode=slots.get("TRANSPORT") or None,
        taboos=taboos,
        start_date=start_date or (date.today() + timedelta(days=settings.default_start_offset_days)),
    )


def _tool_request(input_: PlanInput) -> ToolRequest:
    return ToolRequest(
        origin=input_.origin,
        dest_cities=input_.dest_cities,
        day_count=input_.day_count,
        people=input_.people,
        transport_mode=input_.transport_mode,
        start_date=input_.start_date,
        taboos=input_.taboos,
    )


def _plan_summary(plan: dict) -> str:
    trip = plan["trip"]
    budget = plan.get("budget") or {}
    lines = [
        f'已生成 **{trip["title"]}**，共 {trip["day_count"]} 天 {trip["night_count"]} 晚。',
        "",
    ]
    for day in plan.get("days", [])[:6]:
        poi = [i["ref_name"] for i in day.get("items", []) if i.get("item_type") == "POI"]
        lines.append(f'- Day {day["day_index"]}｜{day.get("city")}｜{day.get("theme")}'
                     + (f'：{"、".join(poi)}' if poi else ""))
    lines.append("")
    budget_line = f'预算合计约 **{budget.get("total", 0):.0f} 元**（人均 {budget.get("per_person", 0):.0f} 元）'
    if budget.get("budget_total"):
        if budget.get("over_budget"):
            budget_line += f'，超出预算 {budget.get("over_amount", 0):.0f} 元。'
        else:
            budget_line += f'，在 {budget.get("budget_total", 0):.0f} 元预算内。'
    lines.append(budget_line)
    if plan.get("degrade_notes"):
        lines.append("")
        lines.append("信息待确认：" + "；".join(plan["degrade_notes"][:4]))
    lines.append("")
    lines.append("右侧可查看每日安排、手动编辑或导出；也可以继续对我说「加一天」「住得离景区近一点」。")
    return "\n".join(lines)


def _consult(db: Session, conversation: Conversation, text: str, slots: dict[str, str]) -> ChatResult:
    cities = [c for c in (slots.get("DEST") or "").replace("/", " ").replace("、", " ").split() if c]
    stmt = select(TravelTips).where(TravelTips.status == 1, TravelTips.deleted == 0)
    if cities:
        stmt = stmt.where(or_(TravelTips.city.in_(cities), TravelTips.city.is_(None)))
    tips = db.scalars(stmt.limit(40)).all()
    keywords = [w for w in ("预约", "天气", "安全", "习俗", "交通", "美食", "门票", "签证", "避坑") if w in text]
    matched = [
        t for t in tips
        if not keywords or any(k in (t.title or "") + (t.content or "") + (t.tags or "") for k in keywords)
    ][:3]
    if not matched:
        matched = [t for t in tips if not t.city][:3]
    if matched:
        lines = ["根据旅行锦囊，给你这些建议：", ""]
        for t in matched:
            lines.append(f"- **{t.title}**：{t.content}")
        lines.append("")
        lines.append("需要我按这些建议生成一份行程吗？告诉我出发地、目的地和天数即可。")
    else:
        lines = ["暂时没有匹配的锦囊内容。你可以告诉我出发地、目的地和天数，我来生成完整行程。"]
    reply = "\n".join(lines)
    msg = _message(db, conversation, "ASSISTANT", reply, intent=INTENT_CONSULT)
    conversation.last_intent = INTENT_CONSULT
    return ChatResult(
        conversation_id=conversation.id,
        intent=INTENT_CONSULT,
        reply=reply,
        slots=slots,
        assistant_message_id=msg.id,
    )


def _trip_plan_input(db: Session, trip: Trip) -> PlanInput:
    version = current_version(db, trip)
    content = version.content_json or {}
    start = content.get("trip", {}).get("start_date")
    return PlanInput(
        origin=trip.origin_city or "",
        dest_cities=[c.strip() for c in (trip.dest_cities or "").split("/") if c.strip()],
        day_count=trip.day_count,
        people=trip.people_count or 2,
        budget_total=float(trip.budget_total) if trip.budget_total else None,
        style_code=trip.style_code,
        transport_mode=trip.transport_mode,
        taboos=[t for t in (trip.taboos or "").split(",") if t],
        start_date=date.fromisoformat(start) if start else None,
    )


def _apply_adjustment(db: Session, trip: Trip, text: str) -> tuple[PlanInput, list[str]]:
    input_ = _trip_plan_input(db, trip)
    changes: list[str] = []

    m = re.search(r"(?:加|多|增加)\s*([一二三四五六七八九十两\d]+)?\s*天\s*([\u4e00-\u9fa5]{2,8})?", text)
    if m and any(k in text for k in ("加", "多", "增加")):
        add = 1
        input_.day_count += add
        changes.append(f"行程延长到 {input_.day_count} 天 {input_.day_count - 1} 晚")
        city = (m.group(2) or "").strip()
        if city and city not in input_.dest_cities:
            input_.dest_cities.append(city)
            changes.append(f"增加目的地「{city}」")
    m = re.search(r"(?:减|少|缩短)\s*([一二三四五六七八九十两\d]+)?\s*天", text)
    if m:
        input_.day_count = max(2, input_.day_count - 1)
        changes.append(f"行程缩短到 {input_.day_count} 天 {input_.day_count - 1} 晚")
    if any(k in text for k in ("住得离景区近", "住近", "靠近景区", "离景区近")):
        input_.near_scenic = True
        changes.append("住宿改为优先靠近景区")
    if any(k in text for k in ("不要购物", "不购物", "别安排购物", "拒绝购物")):
        if "不购物" not in input_.taboos:
            input_.taboos.append("不购物")
        changes.append("全程不安排购物点")
    if any(k in text for k in ("当地特色", "本地特色", "必吃", "特色美食")):
        input_.local_food = True
        changes.append("餐饮优先本地必吃与特色菜")
    if any(k in text for k in ("恐高", "怕高")):
        if "恐高" not in input_.taboos:
            input_.taboos.append("恐高")
        changes.append("避开高海拔与索道类景点")
    if any(k in text for k in ("不吃辣", "忌辣", "清淡")):
        if "不吃辣" not in input_.taboos:
            input_.taboos.append("不吃辣")
        changes.append("餐饮标注不吃辣")
    return input_, changes


def _prepare_extraction(text: str, history: list[str], has_trip: bool) -> tuple[str, dict[str, ExtractedSlot]]:
    intent, _ = detect_intent(text, has_trip)
    slots = extract_slots(text)
    data = llm_client.analyse(text, history)
    if data:
        llm_intent = data.get("intent")
        if llm_intent in (INTENT_NEW, INTENT_ADJUST, INTENT_CONSULT):
            intent = llm_intent
        raw_slots = data.get("slots") or {}
        if isinstance(raw_slots, dict):
            for key, value in raw_slots.items():
                if key in SLOT_KEYS and key not in slots and value not in (None, ""):
                    value_type = "NUMBER" if key in ("PEOPLE", "BUDGET") else "TEXT"
                    slots[key] = ExtractedSlot(key, str(value), value_type, 0.88, "LLM")
    return intent, slots


def handle_message(db: Session, conversation: Conversation, user: User, text: str,
                   start_date: date | None = None, stream: bool = False) -> ChatResult:
    started = time.perf_counter()
    text = (text or "").strip()
    if not text:
        raise NotFoundError("消息内容不能为空")

    passed, risk = audit_text(db, text, "MESSAGE", conversation_id=conversation.id)
    user_msg = _message(db, conversation, "USER", text)
    history = [
        m.content or ""
        for m in db.scalars(
            select(Message).where(Message.conversation_id == conversation.id, Message.deleted == 0)
            .order_by(Message.seq.desc()).limit(8)
        ).all()
    ][::-1]

    if not passed:
        reply = "这条消息包含不适内容，已被拦截。请调整表述后重试。"
        msg = _message(db, conversation, "ASSISTANT", reply, intent=conversation.last_intent)
        return ChatResult(
            conversation_id=conversation.id, intent="BLOCKED", reply=reply,
            assistant_message_id=msg.id, user_message_id=user_msg.id,
        )

    has_trip = bool(conversation.current_trip_id)
    intent, extracted = _prepare_extraction(text, history, has_trip)
    if extracted:
        _upsert_slots(db, conversation, extracted)
    slots = _slot_values(db, conversation)

    if intent == INTENT_CONSULT and not extracted:
        result = _consult(db, conversation, text, slots)
        result.slots = slots
        result.user_message_id = user_msg.id
        result.latency_ms = int((time.perf_counter() - started) * 1000)
        return result

    if intent == INTENT_ADJUST and conversation.current_trip_id:
        trip = db.scalar(select(Trip).where(Trip.id == conversation.current_trip_id, Trip.deleted == 0))
        if not trip:
            conversation.current_trip_id = None
            has_trip = False
        else:
            input_, changes = _apply_adjustment(db, trip, text)
            if input_.day_count != trip.day_count:
                _upsert_slots(db, conversation, {
                    "NIGHTS": ExtractedSlot(
                        "NIGHTS", f"{input_.day_count}天{input_.day_count - 1}晚", "TEXT", 0.9, "USER_INPUT"
                    )
                }, trip_id=trip.id)
            if input_.taboos:
                _upsert_slots(db, conversation, {
                    "TABOO": ExtractedSlot("TABOO", ",".join(input_.taboos), "LIST", 0.9, "USER_INPUT")
                }, trip_id=trip.id)
            slots = _slot_values(db, conversation)
            # 先持久化本轮消息与槽位，避免工具日志写入与主事务争抢写锁
            db.commit()
            tools = collect(_tool_request(input_), f"TRACE{datetime.now():%Y%m%d%H%M%S}{conversation.id}", conversation.id, trip.id)
            style = get_style(db, input_.style_code)
            plan = build_plan(input_, tools, style)
            base = current_version(db, trip)
            summary = "；".join(changes) if changes else "按最新指令局部重排"
            save_version(db, trip, plan, "CHAT_ADJUST", summary, base_version_id=base.id)
            trip.degrade_flag = 1 if plan.get("degrade_flag") else 0
            conversation.current_trip_id = trip.id
            conversation.last_intent = INTENT_ADJUST
            _upsert_slots(db, conversation, {
                "STYLE": ExtractedSlot("STYLE", input_.style_code, "TEXT", 0.8, "DEFAULT")
            }, trip_id=trip.id)
            budget = plan.get("budget") or {}
            delta = budget.get("total", 0) - float(base.total_cost or 0)
            reply = (
                f"已按你的要求调整：{'；'.join(changes) if changes else '重新排布行程'}。\n\n"
                f"当前版本 v{trip.current_version_no} 费用约 **{budget.get('total', 0):.0f} 元**"
                + (f"（较上一版 {'+' if delta >= 0 else ''}{delta:.0f} 元）" if delta else "")
                + "。\n"
            )
            if plan.get("degrade_notes"):
                reply += "待确认：" + "；".join(plan["degrade_notes"][:3]) + "。"
            msg = _message(db, conversation, "ASSISTANT", reply, intent=INTENT_ADJUST)
            serialized = serialize_trip(db, trip)
            return ChatResult(
                conversation_id=conversation.id,
                intent=INTENT_ADJUST,
                reply=reply,
                slots=slots,
                trip=serialized,
                tool_calls=tools.calls,
                degraded=tools.degraded_types,
                trace_id=tools.trace_id,
                latency_ms=int((time.perf_counter() - started) * 1000),
                user_message_id=user_msg.id,
                assistant_message_id=msg.id,
            )

    missing = _missing(db, conversation)
    if missing:
        _ask_clarify(db, conversation, missing[0])
        conversation.last_intent = INTENT_NEW
        reply = clarify_question(missing[0])
        slots = _slot_values(db, conversation)
        assistant = db.scalar(
            select(Message).where(Message.conversation_id == conversation.id).order_by(Message.seq.desc())
        )
        return ChatResult(
            conversation_id=conversation.id, intent=INTENT_NEW, reply=reply, slots=slots,
            missing_slots=missing, user_message_id=user_msg.id,
            assistant_message_id=assistant.id if assistant else None,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    input_ = _plan_input_from_slots(db, slots, start_date)
    if not input_ or not input_.dest_cities:
        reply = "我还需要确认一下目的地，能告诉我具体城市或省份吗？"
        msg = _message(db, conversation, "ASSISTANT", reply, intent=INTENT_NEW)
        return ChatResult(
            conversation_id=conversation.id, intent=INTENT_NEW, reply=reply, slots=slots,
            missing_slots=["DEST"], user_message_id=user_msg.id, assistant_message_id=msg.id,
        )

    # 先持久化本轮消息与槽位，避免工具日志写入与主事务争抢写锁
    db.commit()
    tools = collect(_tool_request(input_), f"TRACE{datetime.now():%Y%m%d%H%M%S}{conversation.id}", conversation.id, None)
    style = get_style(db, input_.style_code)
    plan = build_plan(input_, tools, style)
    trip = create_plan(db, user.id, conversation.id, plan)
    conversation.current_trip_id = trip.id
    conversation.last_intent = INTENT_NEW
    if not conversation.title or conversation.title == "新的旅行规划":
        conversation.title = plan["trip"]["title"]
    _upsert_slots(db, conversation, {
        "STYLE": ExtractedSlot("STYLE", input_.style_code, "TEXT", 0.8, "DEFAULT")
    }, trip_id=trip.id)

    reply = _plan_summary(plan)
    msg = _message(
        db, conversation, "ASSISTANT", reply, intent=INTENT_NEW,
        stream_flag=1 if stream else 0, latency_ms=int((time.perf_counter() - started) * 1000),
    )
    return ChatResult(
        conversation_id=conversation.id,
        intent=INTENT_NEW,
        reply=reply,
        slots=slots,
        trip=serialize_trip(db, trip),
        tool_calls=tools.calls,
        degraded=tools.degraded_types,
        trace_id=tools.trace_id,
        latency_ms=int((time.perf_counter() - started) * 1000),
        user_message_id=user_msg.id,
        assistant_message_id=msg.id,
    )


def conversation_detail(db: Session, conversation: Conversation) -> dict:
    messages = db.scalars(
        select(Message).where(Message.conversation_id == conversation.id, Message.deleted == 0)
        .order_by(Message.seq)
    ).all()
    slots = _load_slot_map(db, conversation)
    trip = None
    if conversation.current_trip_id:
        trip_row = db.scalar(
            select(Trip).where(Trip.id == conversation.current_trip_id, Trip.deleted == 0)
        )
        if trip_row:
            trip = serialize_trip(db, trip_row)
    return {
        "id": conversation.id,
        "user_id": conversation.user_id,
        "title": conversation.title,
        "last_intent": conversation.last_intent,
        "status": conversation.status,
        "current_trip_id": conversation.current_trip_id,
        "message_count": conversation.message_count,
        "messages": [
            {
                "id": m.id,
                "seq": m.seq,
                "role": m.role,
                "content": m.content,
                "content_type": m.content_type,
                "intent": m.intent,
                "stream_flag": m.stream_flag,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
        "slots": {
            key: {
                "value": row.slot_value,
                "label": slot_label(key),
                "required": bool(row.required_flag),
                "filled": bool(row.filled_flag),
                "confidence": float(row.confidence) if row.confidence is not None else None,
                "ask_count": row.ask_count,
            }
            for key, row in slots.items()
        },
        "missing_slots": _missing(db, conversation),
        "trip": trip,
    }

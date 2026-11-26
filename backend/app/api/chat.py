"""旅行顾问实时聊天：WebSocket 长连接 + 消息落库 + seq 排序 + 离线补投。

对应《实时聊天系统技术与实现》中的关键机制：
握手鉴权、心跳保活、指数退避重连、ACK 与 clientId 去重、会话级 seq、
断线后按 lastSeq 增量同步、在线状态 TTL。
"""
import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.auth import get_current_user
from app.common.auth_session import get_session
from app.common.db import SessionLocal, get_db
from app.common.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.common.redis_client import get_redis
from app.common.security import decode_token
from app.models import ChatMessage, ChatThread, User

router = APIRouter(prefix="/chat", tags=["chat"])

ONLINE_TTL_S = 90
GATEWAY_ID = "local"
# user_id -> 该用户当前所有连接（多端并存）
CONNECTIONS: dict[int, set[WebSocket]] = {}
# thread_id -> 订阅该会话的连接（用户端 + 顾问端）
THREAD_SUBS: dict[int, set[WebSocket]] = {}

MAX_CONTENT = 2000


class ReadIn(BaseModel):
    seq: int = Field(ge=0)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _msg_dict(message: ChatMessage) -> dict:
    return {
        "id": message.id,
        "seq": message.seq,
        "sender_id": message.sender_id,
        "sender_role": message.sender_role,
        "content": message.content,
        "client_id": message.client_id,
        "read_flag": message.read_flag,
        "created_at": _iso(message.created_at),
    }


def _get_or_create_thread(db: Session, user: User) -> ChatThread:
    thread = db.scalar(
        select(ChatThread).where(ChatThread.user_id == user.id, ChatThread.deleted == 0)
    )
    if thread:
        return thread
    thread = ChatThread(user_id=user.id, title="旅行顾问咨询")
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


def _get_thread_for(db: Session, user: User, thread_id: int) -> ChatThread:
    thread = db.scalar(
        select(ChatThread).where(ChatThread.id == thread_id, ChatThread.deleted == 0)
    )
    if not thread:
        raise NotFoundError("聊天会话不存在")
    if user.role != "ADMIN" and thread.user_id != user.id:
        raise ForbiddenError("无权访问他人的聊天会话")
    return thread


def _unread_count(db: Session, thread: ChatThread) -> int:
    return (
        db.scalar(
            select(func.count(ChatMessage.id)).where(
                ChatMessage.thread_id == thread.id,
                ChatMessage.sender_role != "USER",
                ChatMessage.read_flag == 0,
                ChatMessage.deleted == 0,
            )
        )
        or 0
    )


@router.get("/thread")
def my_thread(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    thread = _get_or_create_thread(db, current)
    return {
        "thread_id": thread.id,
        "title": thread.title,
        "last_seq": thread.last_seq,
        "last_message_at": _iso(thread.last_message_at),
        "unread": _unread_count(db, thread),
        "online": True,
    }


@router.get("/threads/{thread_id}/messages")
def list_messages(
    thread_id: int,
    after_seq: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    thread = _get_thread_for(db, current, thread_id)
    rows = db.scalars(
        select(ChatMessage)
        .where(
            ChatMessage.thread_id == thread.id,
            ChatMessage.seq > after_seq,
            ChatMessage.deleted == 0,
        )
        .order_by(ChatMessage.seq.asc())
        .limit(limit)
    ).all()
    items = [_msg_dict(row) for row in rows]
    return {
        "items": items,
        "last_seq": items[-1]["seq"] if items else after_seq,
        "has_more": len(items) == limit,
        "thread_last_seq": thread.last_seq,
    }


@router.post("/threads/{thread_id}/read")
def mark_read(
    thread_id: int,
    payload: ReadIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    thread = _get_thread_for(db, current, thread_id)
    rows = db.scalars(
        select(ChatMessage).where(
            ChatMessage.thread_id == thread.id,
            ChatMessage.seq <= payload.seq,
            ChatMessage.sender_role != ("ADVISOR" if current.role == "ADMIN" else "USER"),
            ChatMessage.read_flag == 0,
        )
    ).all()
    for row in rows:
        row.read_flag = 1
    db.commit()
    return {"message": "ok", "updated": len(rows)}


def _next_seq(thread_id: int, db: Session) -> int:
    client = get_redis()
    key = f"chat:seq:{thread_id}"
    seq = int(client.incr(key))
    if seq == 1:
        db_max = (
            db.scalar(select(func.max(ChatMessage.seq)).where(ChatMessage.thread_id == thread_id))
            or 0
        )
        if db_max:
            seq = db_max + 1
            client.set(key, seq)
    return seq


def _load_user(token: str) -> User | None:
    try:
        payload = decode_token(token)
    except UnauthorizedError:
        return None
    session = get_session(token)
    if not session or int(session.get("user_id", 0)) != int(payload.get("sub", 0)):
        return None
    with SessionLocal() as db:
        user = db.scalar(
            select(User).where(User.id == int(payload.get("sub", 0)), User.deleted == 0)
        )
        if not user or (user.status or 1) != 1:
            return None
        db.expunge(user)
        return user


def _online_key(user_id: int) -> str:
    return f"chat:online:{user_id}"


def _register_online(user_id: int) -> None:
    get_redis().set(_online_key(user_id), f"{GATEWAY_ID}|web", ex=ONLINE_TTL_S)


def _unregister_online(user_id: int) -> None:
    if CONNECTIONS.get(user_id):
        return
    client = get_redis()
    if client.get(_online_key(user_id)) == f"{GATEWAY_ID}|web":
        client.delete(_online_key(user_id))


async def _broadcast(thread_id: int, payload: dict, exclude: WebSocket | None = None) -> None:
    dead: list[WebSocket] = []
    for ws in list(THREAD_SUBS.get(thread_id, ())):
        if ws is exclude:
            continue
        try:
            await ws.send_json(payload)
        except Exception:  # noqa: BLE001
            dead.append(ws)
    for ws in dead:
        THREAD_SUBS.get(thread_id, set()).discard(ws)


ADVISOR_REPLIES = [
    ("预算", "收到，预算这块我帮你拆一下：交通约占 35%、住宿 30%、餐饮 20%，剩下留给门票和机动。你希望我按人均还是总价控制？"),
    ("酒店", "住宿我建议优先看「离地铁/景区步行 15 分钟内」的选项，旺季提前 7-10 天订价格更稳。需要我按亲子或情侣偏好筛一版吗？"),
    ("天气", "出行前 3 天我再帮你核对一次天气，雨天会把户外点位替换成室内备选，行程不用你手动改。"),
    ("交通", "城际交通建议优先高铁，市内用公共交通 + 打车补位；如果是早班机，我会把第一天的行程整体后移两小时。"),
    ("签证", "签证材料一般需要护照、照片、行程单和在读/在职证明，我可以在行程定稿后直接导出中英文版本。"),
    ("行程", "行程已经按「上午一个主景点、下午一个次景点」的节奏排了，避免来回折返。你想更紧凑还是更松弛？"),
]

DEFAULT_REPLY = "收到，我先记下你的需求。你可以补充出发地、天数、人数和预算，我会给你一版可直接出发的方案。"


def _advisor_reply(text: str) -> str:
    for keyword, reply in ADVISOR_REPLIES:
        if keyword in text:
            return reply
    return DEFAULT_REPLY


async def _auto_reply(thread_id: int, user_text: str) -> None:
    await asyncio.sleep(1.2)
    with SessionLocal() as db:
        thread = db.get(ChatThread, thread_id)
        if not thread:
            return
        seq = _next_seq(thread_id, db)
        message = ChatMessage(
            thread_id=thread_id,
            seq=seq,
            sender_id=None,
            sender_role="ADVISOR",
            content=_advisor_reply(user_text),
        )
        db.add(message)
        thread.last_seq = seq
        thread.last_message_at = datetime.now()
        db.commit()
        db.refresh(message)
        payload = _msg_dict(message)
    await _broadcast(thread_id, {"type": "message", "message": payload})


async def _handle_send(ws: WebSocket, user: User, thread_id: int, payload: dict) -> None:
    content = (payload.get("content") or "").strip()
    client_id = (payload.get("client_id") or "").strip() or None
    if not content:
        await ws.send_json({"type": "error", "code": "EMPTY", "message": "消息不能为空"})
        return
    if len(content) > MAX_CONTENT:
        await ws.send_json({"type": "error", "code": "TOO_LONG", "message": "消息过长"})
        return

    with SessionLocal() as db:
        if client_id:
            existing = db.scalar(
                select(ChatMessage).where(ChatMessage.client_id == client_id)
            )
            if existing:
                await ws.send_json(
                    {
                        "type": "ack",
                        "client_id": client_id,
                        "id": existing.id,
                        "seq": existing.seq,
                        "duplicate": True,
                    }
                )
                return
        seq = _next_seq(thread_id, db)
        message = ChatMessage(
            thread_id=thread_id,
            seq=seq,
            sender_id=user.id,
            sender_role="ADVISOR" if user.role == "ADMIN" else "USER",
            content=content,
            client_id=client_id,
        )
        db.add(message)
        thread = db.get(ChatThread, thread_id)
        thread.last_seq = seq
        thread.last_message_at = datetime.now()
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = (
                db.scalar(select(ChatMessage).where(ChatMessage.client_id == client_id))
                if client_id
                else None
            )
            if existing:
                await ws.send_json(
                    {
                        "type": "ack",
                        "client_id": client_id,
                        "id": existing.id,
                        "seq": existing.seq,
                        "duplicate": True,
                    }
                )
            return
        db.refresh(message)
        data = _msg_dict(message)

    await ws.send_json(
        {"type": "ack", "client_id": client_id, "id": data["id"], "seq": data["seq"]}
    )
    await _broadcast(thread_id, {"type": "message", "message": data}, exclude=ws)
    if user.role != "ADMIN":
        asyncio.create_task(_auto_reply(thread_id, content))


async def _handle_sync(ws: WebSocket, thread_id: int, after_seq: int) -> None:
    with SessionLocal() as db:
        rows = db.scalars(
            select(ChatMessage)
            .where(
                ChatMessage.thread_id == thread_id,
                ChatMessage.seq > after_seq,
                ChatMessage.deleted == 0,
            )
            .order_by(ChatMessage.seq.asc())
            .limit(500)
        ).all()
        messages = [_msg_dict(row) for row in rows]
    await ws.send_json(
        {
            "type": "sync",
            "messages": messages,
            "last_seq": messages[-1]["seq"] if messages else after_seq,
        }
    )


async def _handle_read(ws: WebSocket, user: User, thread_id: int, seq: int) -> None:
    with SessionLocal() as db:
        rows = db.scalars(
            select(ChatMessage).where(
                ChatMessage.thread_id == thread_id,
                ChatMessage.seq <= seq,
                ChatMessage.sender_role != ("ADVISOR" if user.role == "ADMIN" else "USER"),
                ChatMessage.read_flag == 0,
            )
        ).all()
        for row in rows:
            row.read_flag = 1
        db.commit()
    await _broadcast(thread_id, {"type": "read", "seq": seq}, exclude=ws)


@router.websocket("/ws")
async def chat_socket(
    websocket: WebSocket,
    token: str | None = Query(None),
    thread_id: int | None = Query(None),
) -> None:
    user = _load_user(token or "")
    if not user:
        await websocket.close(code=4401)
        return

    with SessionLocal() as db:
        if user.role == "ADMIN":
            if not thread_id:
                await websocket.close(code=4404)
                return
            thread = _get_thread_for(db, user, thread_id)
        else:
            thread = _get_or_create_thread(db, user)
        active_thread_id = thread.id
        last_seq = thread.last_seq

    await websocket.accept()
    CONNECTIONS.setdefault(user.id, set()).add(websocket)
    THREAD_SUBS.setdefault(active_thread_id, set()).add(websocket)
    _register_online(user.id)

    await websocket.send_json(
        {
            "type": "ready",
            "user_id": user.id,
            "role": user.role,
            "thread_id": active_thread_id,
            "last_seq": last_seq,
            "heartbeat_s": 30,
        }
    )

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            kind = payload.get("type")
            if kind == "ping":
                _register_online(user.id)
                await websocket.send_json({"type": "pong"})
            elif kind == "send":
                await _handle_send(websocket, user, active_thread_id, payload)
            elif kind == "sync":
                await _handle_sync(websocket, active_thread_id, int(payload.get("last_seq") or 0))
            elif kind == "read":
                await _handle_read(websocket, user, active_thread_id, int(payload.get("seq") or 0))
    except WebSocketDisconnect:
        pass
    finally:
        CONNECTIONS.get(user.id, set()).discard(websocket)
        THREAD_SUBS.get(active_thread_id, set()).discard(websocket)
        if not CONNECTIONS.get(user.id):
            CONNECTIONS.pop(user.id, None)
        _unregister_online(user.id)

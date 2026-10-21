import json
import time

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent_core.dialog import conversation_detail, handle_message
from app.common.db import get_db
from app.common.errors import NotFoundError
from app.models import Conversation, User
from app.schemas.requests import ChatIn

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _get_conversation(db: Session, conversation_id: int) -> Conversation:
    conversation = db.scalar(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.deleted == 0)
    )
    if not conversation:
        raise NotFoundError("会话不存在")
    return conversation


def _get_user(db: Session, conversation: Conversation) -> User:
    user = db.scalar(select(User).where(User.id == conversation.user_id, User.deleted == 0))
    if not user:
        raise NotFoundError("用户不存在")
    return user


@router.get("")
def list_conversations(user_id: int, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(
        select(Conversation).where(
            Conversation.user_id == user_id, Conversation.deleted == 0
        ).order_by(Conversation.id.desc()).limit(50)
    ).all()
    return [
        {
            "id": c.id,
            "title": c.title,
            "last_intent": c.last_intent,
            "current_trip_id": c.current_trip_id,
            "message_count": c.message_count,
            "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
        }
        for c in rows
    ]


@router.get("/{conversation_id}")
def detail(conversation_id: int, db: Session = Depends(get_db)) -> dict:
    return conversation_detail(db, _get_conversation(db, conversation_id))


@router.post("/{conversation_id}/messages")
def send_message(conversation_id: int, payload: ChatIn, db: Session = Depends(get_db)) -> dict:
    conversation = _get_conversation(db, conversation_id)
    user = _get_user(db, conversation)
    result = handle_message(db, conversation, user, payload.content, payload.start_date)
    db.commit()
    return result.as_dict()


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/{conversation_id}/messages/stream")
def send_message_stream(conversation_id: int, payload: ChatIn, db: Session = Depends(get_db)):
    conversation = _get_conversation(db, conversation_id)
    user = _get_user(db, conversation)

    def event_stream():
        yield _sse("start", {"conversation_id": conversation.id})
        try:
            started = time.perf_counter()
            result = handle_message(
                db, conversation, user, payload.content, payload.start_date, stream=True
            )
            db.commit()
            yield _sse("slots", {"slots": result.slots, "missing_slots": result.missing_slots})
            for call in result.tool_calls:
                yield _sse("tool", call)
            if result.degraded:
                yield _sse("degrade", {"tools": result.degraded})
            # 分段输出文本，保证前端渐进渲染
            text = result.reply
            step = 18
            for i in range(0, len(text), step):
                yield _sse("chunk", {"content": text[i:i + step]})
            yield _sse("done", {
                "intent": result.intent,
                "conversation_id": result.conversation_id,
                "trip": result.trip,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "assistant_message_id": result.assistant_message_id,
            })
        except Exception as exc:  # 流式响应中无法再抛 HTTP 异常
            db.rollback()
            yield _sse("error", {"message": str(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

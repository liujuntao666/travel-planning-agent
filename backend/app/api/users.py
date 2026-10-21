from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent_core.dialog import get_or_create_user
from app.common.db import get_db
from app.models import Conversation, User
from app.schemas.requests import ConversationIn, LoginIn

router = APIRouter(tags=["users"])


@router.post("/users/login")
def login(payload: LoginIn, db: Session = Depends(get_db)) -> dict:
    user = get_or_create_user(db, payload.open_id, payload.nickname, payload.source)
    db.commit()
    return {
        "id": user.id,
        "open_id": user.open_id,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "source": user.source,
        "status": user.status,
    }


@router.get("/users/{user_id}")
def user_detail(user_id: int, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.id == user_id, User.deleted == 0))
    if not user:
        return {"id": user_id, "error": "not found"}
    conversations = db.scalars(
        select(Conversation).where(Conversation.user_id == user.id, Conversation.deleted == 0)
        .order_by(Conversation.id.desc()).limit(20)
    ).all()
    return {
        "id": user.id,
        "open_id": user.open_id,
        "nickname": user.nickname,
        "conversations": [
            {"id": c.id, "title": c.title, "last_intent": c.last_intent,
             "current_trip_id": c.current_trip_id, "last_message_at": c.last_message_at}
            for c in conversations
        ],
    }


@router.post("/conversations")
def create_conversation(payload: ConversationIn, db: Session = Depends(get_db)) -> dict:
    from app.agent_core.dialog import create_conversation as _create

    user = db.scalar(select(User).where(User.id == payload.user_id, User.deleted == 0))
    if not user:
        from app.common.errors import NotFoundError

        raise NotFoundError("用户不存在")
    conversation = _create(db, user, payload.title)
    db.commit()
    return {"id": conversation.id, "user_id": conversation.user_id, "title": conversation.title}

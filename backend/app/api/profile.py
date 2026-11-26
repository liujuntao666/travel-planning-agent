"""个人画像接口：仅本人可读、可刷新、可清除自己的标签。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common.auth import get_current_user
from app.common.db import get_db
from app.common.ratelimit import enforce
from app.models import User
from app.profile.service import clear_user_tags, list_user_tags, refresh_user_tags

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/tags")
def my_tags(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    items = list_user_tags(db, current.id)
    return {"items": items, "total": len(items)}


@router.post("/tags/refresh")
def refresh_tags(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    enforce(f"profile:tags:{current.id}", 5, 300, "刷新过于频繁，请稍后再试")
    items = refresh_user_tags(db, current.id)
    db.commit()
    return {"message": "标签已刷新", "items": items, "total": len(items)}


@router.delete("/tags")
def clear_tags(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    removed = clear_user_tags(db, current.id)
    db.commit()
    return {"message": f"已清除 {removed} 个标签", "removed": removed}

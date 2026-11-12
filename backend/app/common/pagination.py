from typing import Any

from fastapi import Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.config import settings
from app.common.errors import ValidationError


class PageParams:
    """列表三件套：分页、过滤（由各接口显式声明）、排序。"""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="页码，从 1 开始"),
        page_size: int = Query(
            settings.default_page_size,
            ge=1,
            le=settings.max_page_size,
            description="每页条数，上限 100",
        ),
        sort: str | None = Query(None, description="排序字段:asc|desc，字段需在白名单内"),
    ) -> None:
        self.page = page
        self.page_size = page_size
        self.sort = sort


def _resolve_sort(sort: str | None, allowed: dict[str, Any], default: str):
    raw = (sort or default).strip()
    field, _, direction = raw.partition(":")
    direction = (direction or "desc").lower()
    if field not in allowed:
        raise ValidationError(
            f"不支持的排序字段「{field}」，可选：{', '.join(sorted(allowed))}"
        )
    if direction not in {"asc", "desc"}:
        raise ValidationError("排序方向仅支持 asc 或 desc")
    return allowed[field], direction == "desc"


def paginate(
    db: Session,
    stmt,
    params: PageParams,
    allowed_sort: dict[str, Any],
    default_sort: str,
) -> dict:
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    column, desc = _resolve_sort(params.sort, allowed_sort, default_sort)
    rows = db.scalars(
        stmt.order_by(column.desc() if desc else column.asc())
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    ).all()
    return {
        "items": rows,
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
    }

from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.db import get_db
from app.common.errors import NotFoundError
from app.common.helpers import paginate
from app.common.security import fmt_dt
from app.deps import require_perm
from app.models import OperationLog, User

router = APIRouter(tags=["logs"])


@router.get("/logs")
def list_logs(
    account: str | None = None,
    module: str | None = None,
    method: str | None = None,
    result: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(require_perm("log", "browse")),
    db: Session = Depends(get_db),
) -> dict:
    conditions = []
    if account:
        conditions.append(OperationLog.account == account)
    if module:
        conditions.append(OperationLog.module == module)
    if method:
        conditions.append(OperationLog.method == method)
    if result:
        conditions.append(OperationLog.result == result)
    if date_from:
        start = datetime.combine(datetime.strptime(date_from, "%Y-%m-%d").date(), time.min)
        conditions.append(OperationLog.created_at >= start)
    if date_to:
        end_day = datetime.strptime(date_to, "%Y-%m-%d").date()
        conditions.append(OperationLog.created_at < datetime.combine(end_day, time.min) + timedelta(days=1))

    page, page_size, offset = paginate(page, page_size)
    total = db.scalar(select(func.count()).select_from(OperationLog).where(*conditions)) or 0
    rows = db.scalars(
        select(OperationLog)
        .where(*conditions)
        .order_by(OperationLog.created_at.desc(), OperationLog.id.desc())
        .offset(offset)
        .limit(page_size)
    ).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": row.id,
                "account": row.account,
                "realname": row.realname,
                "module": row.module,
                "method": row.method,
                "ip": row.ip,
                "result": row.result,
                "created_at": fmt_dt(row.created_at),
            }
            for row in rows
        ],
    }


@router.get("/logs/{log_id}")
def get_log(
    log_id: int,
    user: User = Depends(require_perm("log", "view")),
    db: Session = Depends(get_db),
) -> dict:
    row = db.get(OperationLog, log_id)
    if row is None:
        raise NotFoundError("日志不存在")
    return {
        "id": row.id,
        "account": row.account,
        "module": row.module,
        "method": row.method,
        "ip": row.ip,
        "result": row.result,
        "message": row.message,
        "params": row.params,
        "created_at": fmt_dt(row.created_at),
    }

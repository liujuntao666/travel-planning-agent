from datetime import datetime
from typing import Any

from fastapi import Request
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.common.security import fmt_dt
from app.models import Dept, Group, GroupMember, GroupPriv, OperationLog, Privilege, User


def client_ip(request: Request | None) -> str:
    if request is None:
        return ""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def sanitize_params(params: Any) -> dict | None:
    if params is None:
        return None
    if hasattr(params, "model_dump"):
        params = params.model_dump()
    if not isinstance(params, dict):
        return {"value": str(params)}
    masked: dict = {}
    for key, value in params.items():
        lower = str(key).lower()
        if any(word in lower for word in ("password", "token", "secret")):
            masked[key] = "***"
        elif isinstance(value, dict):
            masked[key] = sanitize_params(value)
        elif isinstance(value, list):
            masked[key] = [
                sanitize_params(item) if isinstance(item, dict) else item for item in value
            ]
        else:
            masked[key] = value
    return masked


def log_action(
    db: Session,
    *,
    request: Request | None = None,
    user: User | None = None,
    account: str | None = None,
    realname: str | None = None,
    module: str,
    method: str,
    result: str = "SUCCESS",
    message: str | None = None,
    params: Any = None,
) -> None:
    if user is not None:
        account = account or user.account
        realname = realname or user.realname
    db.add(
        OperationLog(
            account=account or "-",
            realname=realname,
            module=module,
            method=method,
            ip=client_ip(request),
            result=result,
            message=message,
            params=sanitize_params(params),
            created_at=datetime.now(),
        )
    )


def group_briefs(db: Session, account: str) -> list[dict]:
    groups = db.scalars(
        select(Group)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .where(GroupMember.account == account)
        .order_by(Group.id)
    ).all()
    return [{"id": g.id, "name": g.name, "role": g.role} for g in groups]


def dept_name(db: Session, dept_id: int | None) -> str:
    if not dept_id:
        return ""
    return db.scalar(select(Dept.name).where(Dept.id == dept_id)) or ""


def effective_privileges(db: Session, user: User) -> list[str]:
    if user.admin == "yes":
        rows = db.scalars(select(Privilege).order_by(Privilege.id)).all()
        return [f"{row.module}-{row.method}" for row in rows]
    rows = db.scalars(
        select(Privilege)
        .join(
            GroupPriv,
            and_(GroupPriv.module == Privilege.module, GroupPriv.method == Privilege.method),
        )
        .join(GroupMember, GroupMember.group_id == GroupPriv.group_id)
        .where(GroupMember.account == user.account)
        .order_by(Privilege.id)
        .distinct()
    ).all()
    return [f"{row.module}-{row.method}" for row in rows]


def user_payload(db: Session, user: User, *, with_groups: bool = True) -> dict:
    payload = {
        "account": user.account,
        "realname": user.realname,
        "dept_id": user.dept_id,
        "dept_name": dept_name(db, user.dept_id),
        "role": user.role,
        "admin": user.admin,
        "status": user.status,
    }
    if with_groups:
        payload["groups"] = group_briefs(db, user.account)
    return payload


def data_scope_ids(db: Session, user: User) -> dict:
    """当前用户可见的产品 / 项目 ID 集合；超级管理员视为全量。"""
    from app.models import Product, ProductAcl, Project, ProjectAcl

    if user.admin == "yes":
        return {
            "products": list(db.scalars(select(Product.id).order_by(Product.id)).all()),
            "projects": list(db.scalars(select(Project.id).order_by(Project.id)).all()),
        }
    product_ids = set(
        db.scalars(select(ProductAcl.product_id).where(ProductAcl.account == user.account)).all()
    )
    product_ids.update(
        db.scalars(select(Product.id).where(Product.acl_open.is_(True))).all()
    )
    project_ids = set(
        db.scalars(select(ProjectAcl.project_id).where(ProjectAcl.account == user.account)).all()
    )
    return {
        "products": sorted(product_ids),
        "projects": sorted(project_ids),
    }


def fmt_user_row(user: User, dept_name_value: str) -> dict:
    return {
        "account": user.account,
        "realname": user.realname,
        "dept_id": user.dept_id,
        "dept_name": dept_name_value or "",
        "role": user.role,
        "admin": user.admin,
        "status": user.status,
        "last_login": fmt_dt(user.last_login),
    }


def paginate(page: int, page_size: int) -> tuple[int, int, int]:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    return page, page_size, (page - 1) * page_size

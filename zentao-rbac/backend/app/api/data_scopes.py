from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.common.db import get_db
from app.common.errors import ForbiddenError, NotFoundError, ValidationError
from app.common.helpers import log_action
from app.deps import get_current_user, require_perm
from app.models import Product, ProductAcl, Project, ProjectAcl, User
from app.schemas import ProductScopeRequest, ProjectScopeRequest

router = APIRouter(tags=["data-scopes"])


def _resolve_target(db: Session, current: User, account: str | None) -> User:
    if account is None or account == current.account:
        return current
    if current.admin != "yes":
        raise ForbiddenError("仅超级管理员可为他人设置数据范围")
    target = db.scalar(select(User).where(User.account == account))
    if target is None or target.status == "deleted":
        raise NotFoundError("用户不存在")
    return target


@router.get("/data-scopes/products")
def get_product_scope(
    account: str | None = Query(default=None),
    user: User = Depends(require_perm("data", "view")),
    db: Session = Depends(get_db),
) -> dict:
    target = _resolve_target(db, user, account)
    granted = set(
        db.scalars(select(ProductAcl.product_id).where(ProductAcl.account == target.account)).all()
    )
    items = [
        {
            "product_id": product.id,
            "name": product.name,
            "acl_open": product.acl_open,
            "granted": product.acl_open or product.id in granted,
        }
        for product in db.scalars(select(Product).order_by(Product.id.asc())).all()
    ]
    return {"items": items}


@router.put("/data-scopes/products")
def set_product_scope(
    payload: ProductScopeRequest,
    request: Request,
    user: User = Depends(require_perm("data", "edit")),
    db: Session = Depends(get_db),
) -> dict:
    target = _resolve_target(db, user, payload.account)
    ids = sorted(set(payload.product_ids))
    if ids:
        found = set(db.scalars(select(Product.id).where(Product.id.in_(ids))).all())
        missing = [item for item in ids if item not in found]
        if missing:
            raise ValidationError(f"产品不存在：{missing}")

    db.execute(delete(ProductAcl).where(ProductAcl.account == target.account))
    for product_id in ids:
        db.add(ProductAcl(account=target.account, product_id=product_id))
    log_action(
        db, request=request, user=user, module="data", method="editproduct",
        message=f"设置产品数据范围 {target.account}", params=payload,
    )
    db.commit()
    return {"success": True, "count": len(ids)}


@router.get("/data-scopes/projects")
def get_project_scope(
    account: str | None = Query(default=None),
    user: User = Depends(require_perm("data", "view")),
    db: Session = Depends(get_db),
) -> dict:
    target = _resolve_target(db, user, account)
    granted = set(
        db.scalars(select(ProjectAcl.project_id).where(ProjectAcl.account == target.account)).all()
    )
    items = [
        {
            "project_id": project.id,
            "name": project.name,
            "granted": project.id in granted,
        }
        for project in db.scalars(select(Project).order_by(Project.id.asc())).all()
    ]
    return {"items": items}


@router.put("/data-scopes/projects")
def set_project_scope(
    payload: ProjectScopeRequest,
    request: Request,
    user: User = Depends(require_perm("data", "edit")),
    db: Session = Depends(get_db),
) -> dict:
    target = _resolve_target(db, user, payload.account)
    ids = sorted(set(payload.project_ids))
    if ids:
        found = set(db.scalars(select(Project.id).where(Project.id.in_(ids))).all())
        missing = [item for item in ids if item not in found]
        if missing:
            raise ValidationError(f"项目不存在：{missing}")

    db.execute(delete(ProjectAcl).where(ProjectAcl.account == target.account))
    for project_id in ids:
        db.add(ProjectAcl(account=target.account, project_id=project_id))
    log_action(
        db, request=request, user=user, module="data", method="editproject",
        message=f"设置项目数据范围 {target.account}", params=payload,
    )
    db.commit()
    return {"success": True, "count": len(ids)}

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.common.db import get_db
from app.common.errors import ConflictError, NotFoundError, ValidationError
from app.common.helpers import log_action
from app.deps import require_perm
from app.models import Dept, User
from app.schemas import DeptCreateRequest, DeptMoveRequest, DeptPatchRequest

router = APIRouter(tags=["depts"])


def _build_tree(rows: list[Dept], counts: dict[int, int] | None = None) -> list[dict]:
    nodes = {
        dept.id: {
            "id": dept.id,
            "name": dept.name,
            "parent": dept.parent,
            "path": dept.path,
            "manager": dept.manager,
            "user_count": (counts or {}).get(dept.id, 0),
            "children": [],
        }
        for dept in rows
    }
    roots: list[dict] = []
    for dept in rows:
        node = nodes[dept.id]
        parent = nodes.get(dept.parent)
        if parent is None:
            roots.append(node)
        else:
            parent["children"].append(node)
    return roots


@router.get("/depts/tree")
def dept_tree(
    with_users: bool = False,
    user: User = Depends(require_perm("dept", "browse")),
    db: Session = Depends(get_db),
) -> dict:
    rows = db.scalars(select(Dept).order_by(Dept.parent.asc(), Dept.position.asc(), Dept.id.asc())).all()
    counts: dict[int, int] | None = None
    if with_users:
        counts = {
            row[0]: row[1]
            for row in db.execute(
                select(User.dept_id, func.count())
                .where(User.status != "deleted")
                .group_by(User.dept_id)
            ).all()
        }
    return {"tree": _build_tree(list(rows), counts)}


@router.post("/depts")
def create_dept(
    payload: DeptCreateRequest,
    request: Request,
    user: User = Depends(require_perm("dept", "create")),
    db: Session = Depends(get_db),
) -> dict:
    if payload.parent_id != 0 and db.get(Dept, payload.parent_id) is None:
        raise ValidationError("父部门不存在")
    exists = db.scalar(
        select(Dept.id).where(Dept.name == payload.name, Dept.parent == payload.parent_id)
    )
    if exists is not None:
        raise ConflictError("同级部门名称已存在")

    dept = Dept(
        name=payload.name,
        parent=payload.parent_id,
        path="",
        manager=payload.manager,
        position=payload.position if payload.position is not None else 0,
    )
    db.add(dept)
    db.flush()
    parent_path = ""
    if payload.parent_id:
        parent_path = db.scalar(select(Dept.path).where(Dept.id == payload.parent_id)) or ""
    dept.path = f"{parent_path}{dept.id}," if payload.parent_id else f",{dept.id},"
    log_action(
        db, request=request, user=user, module="dept", method="create",
        message=f"新建部门 {dept.name}", params=payload,
    )
    db.commit()
    return {"id": dept.id}


@router.patch("/depts/{dept_id}")
def update_dept(
    dept_id: int,
    payload: DeptPatchRequest,
    request: Request,
    user: User = Depends(require_perm("dept", "edit")),
    db: Session = Depends(get_db),
) -> dict:
    dept = db.get(Dept, dept_id)
    if dept is None:
        raise NotFoundError("部门不存在")

    if payload.name is not None and payload.name != dept.name:
        exists = db.scalar(
            select(Dept.id).where(
                Dept.name == payload.name, Dept.parent == dept.parent, Dept.id != dept.id
            )
        )
        if exists is not None:
            raise ConflictError("同级部门名称已存在")
        dept.name = payload.name
    if payload.manager is not None:
        dept.manager = payload.manager or None
    if payload.position is not None:
        dept.position = payload.position

    log_action(
        db, request=request, user=user, module="dept", method="edit",
        message=f"修改部门 {dept.id}", params=payload,
    )
    db.commit()
    return {"success": True}


@router.delete("/depts/{dept_id}")
def delete_dept(
    dept_id: int,
    request: Request,
    move_users_to: int | None = Query(default=None),
    user: User = Depends(require_perm("dept", "delete")),
    db: Session = Depends(get_db),
) -> dict:
    dept = db.get(Dept, dept_id)
    if dept is None:
        raise NotFoundError("部门不存在")

    children = db.scalar(select(func.count()).select_from(Dept).where(Dept.parent == dept_id)) or 0
    if children:
        raise ConflictError("存在子部门，无法删除")

    user_count = (
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.dept_id == dept_id, User.status != "deleted")
        )
        or 0
    )
    if user_count:
        if move_users_to is None:
            raise ConflictError("部门下仍有用户，请指定迁入部门")
        target = db.get(Dept, move_users_to)
        if target is None:
            raise ValidationError("迁入部门不存在")
        db.execute(
            update(User).where(User.dept_id == dept_id).values(dept_id=move_users_to)
        )

    db.delete(dept)
    log_action(
        db, request=request, user=user, module="dept", method="delete",
        message=f"删除部门 {dept_id}", params={"move_users_to": move_users_to},
    )
    db.commit()
    return {"success": True}


@router.put("/depts/{dept_id}/move")
def move_dept(
    dept_id: int,
    payload: DeptMoveRequest,
    request: Request,
    user: User = Depends(require_perm("dept", "move")),
    db: Session = Depends(get_db),
) -> dict:
    dept = db.get(Dept, dept_id)
    if dept is None:
        raise NotFoundError("部门不存在")

    if payload.parent_id == dept_id:
        raise ConflictError("不能移动到自身")

    new_parent_path = ""
    if payload.parent_id != 0:
        parent = db.get(Dept, payload.parent_id)
        if parent is None:
            raise ValidationError("新父部门不存在")
        if parent.path.startswith(dept.path):
            raise ConflictError("不能移动到自身或子孙节点下")
        new_parent_path = parent.path

    old_path = dept.path
    new_path = f"{new_parent_path}{dept.id},"
    dept.parent = payload.parent_id
    dept.path = new_path

    descendants = db.scalars(select(Dept).where(Dept.path.like(f"{old_path}%"))).all()
    for node in descendants:
        if node.id == dept.id:
            continue
        node.path = node.path.replace(old_path, new_path, 1)

    log_action(
        db, request=request, user=user, module="dept", method="move",
        message=f"移动部门 {dept.id} 到 {payload.parent_id}", params=payload,
    )
    db.commit()
    return {"success": True}

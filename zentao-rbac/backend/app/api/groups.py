from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.common.constants import MODULE_NAMES, MODULE_ORDER, PRIVILEGES, priv_key
from app.common.db import get_db
from app.common.errors import ConflictError, NotFoundError, ValidationError
from app.common.helpers import log_action, paginate
from app.deps import require_perm
from app.models import Dept, Group, GroupMember, GroupPriv, Privilege, User
from app.schemas import GroupCreateRequest, GroupPatchRequest, GroupPrivRequest, GroupUsersRequest

router = APIRouter(tags=["groups"])

VALID_KEYS = {priv_key(module, method) for module, _name, method, _label in PRIVILEGES}


def _get_group(db: Session, group_id: int) -> Group:
    group = db.get(Group, group_id)
    if group is None:
        raise NotFoundError("用户组不存在")
    return group


def _parse_privileges(keys: list[str]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for key in keys:
        if key not in VALID_KEYS:
            raise ValidationError(f"权限标识不存在：{key}")
        module, method = key.split("-", 1)
        if (module, method) in seen:
            continue
        seen.add((module, method))
        pairs.append((module, method))
    return pairs


def _replace_privileges(db: Session, group_id: int, pairs: list[tuple[str, str]]) -> None:
    db.execute(delete(GroupPriv).where(GroupPriv.group_id == group_id))
    for module, method in pairs:
        db.add(GroupPriv(group_id=group_id, module=module, method=method))


@router.get("/groups")
def list_groups(
    keyword: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(require_perm("group", "browse")),
    db: Session = Depends(get_db),
) -> dict:
    conditions = []
    if keyword:
        conditions.append(Group.name.like(f"%{keyword}%"))

    page, page_size, offset = paginate(page, page_size)
    total = db.scalar(select(func.count()).select_from(Group).where(*conditions)) or 0
    groups = db.scalars(
        select(Group)
        .where(*conditions)
        .order_by(Group.id.asc())
        .offset(offset)
        .limit(page_size)
    ).all()

    user_counts = dict(
        db.execute(
            select(GroupMember.group_id, func.count())
            .join(User, User.account == GroupMember.account)
            .where(User.status != "deleted")
            .group_by(GroupMember.group_id)
        ).all()
    )
    priv_counts = dict(
        db.execute(select(GroupPriv.group_id, func.count()).group_by(GroupPriv.group_id)).all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": group.id,
                "name": group.name,
                "role": group.role,
                "desc": group.description,
                "user_count": user_counts.get(group.id, 0),
                "priv_count": priv_counts.get(group.id, 0),
            }
            for group in groups
        ],
    }


@router.post("/groups")
def create_group(
    payload: GroupCreateRequest,
    request: Request,
    user: User = Depends(require_perm("group", "create")),
    db: Session = Depends(get_db),
) -> dict:
    if db.scalar(select(Group.id).where(Group.name == payload.name)) is not None:
        raise ConflictError("用户组名称已存在")
    pairs = _parse_privileges(payload.privileges)

    group = Group(name=payload.name, role=payload.role, description=payload.desc)
    db.add(group)
    db.flush()
    _replace_privileges(db, group.id, pairs)
    log_action(
        db, request=request, user=user, module="group", method="create",
        message=f"新建用户组 {group.name}", params=payload,
    )
    db.commit()
    return {"id": group.id}


@router.get("/groups/{group_id}")
def get_group(
    group_id: int,
    user: User = Depends(require_perm("group", "view")),
    db: Session = Depends(get_db),
) -> dict:
    group = _get_group(db, group_id)
    members = db.execute(
        select(User.account, User.realname, Dept.name)
        .outerjoin(Dept, Dept.id == User.dept_id)
        .join(GroupMember, GroupMember.account == User.account)
        .where(GroupMember.group_id == group_id, User.status != "deleted")
        .order_by(User.account.asc())
    ).all()
    privileges = db.execute(
        select(Privilege.module, Privilege.method, Privilege.name)
        .join(
            GroupPriv,
            (GroupPriv.module == Privilege.module) & (GroupPriv.method == Privilege.method),
        )
        .where(GroupPriv.group_id == group_id)
        .order_by(Privilege.id.asc())
    ).all()

    return {
        "id": group.id,
        "name": group.name,
        "role": group.role,
        "desc": group.description,
        "members": [
            {"account": row[0], "realname": row[1], "dept_name": row[2] or ""} for row in members
        ],
        "privileges": [
            {"module": row[0], "method": row[1], "name": row[2]} for row in privileges
        ],
    }


@router.patch("/groups/{group_id}")
def update_group(
    group_id: int,
    payload: GroupPatchRequest,
    request: Request,
    user: User = Depends(require_perm("group", "edit")),
    db: Session = Depends(get_db),
) -> dict:
    group = _get_group(db, group_id)
    if payload.name is not None and payload.name != group.name:
        if db.scalar(select(Group.id).where(Group.name == payload.name, Group.id != group_id)):
            raise ConflictError("用户组名称已存在")
        group.name = payload.name
    if payload.role is not None:
        group.role = payload.role or None
    if payload.desc is not None:
        group.description = payload.desc

    log_action(
        db, request=request, user=user, module="group", method="edit",
        message=f"修改用户组 {group.id}", params=payload,
    )
    db.commit()
    return {"success": True}


@router.delete("/groups/{group_id}")
def delete_group(
    group_id: int,
    request: Request,
    force: bool = False,
    user: User = Depends(require_perm("group", "delete")),
    db: Session = Depends(get_db),
) -> dict:
    group = _get_group(db, group_id)
    member_count = (
        db.scalar(
            select(func.count()).select_from(GroupMember).where(GroupMember.group_id == group_id)
        )
        or 0
    )
    if member_count and not force:
        raise ConflictError("组内仍有用户，如需删除请传 force=true")

    db.execute(delete(GroupPriv).where(GroupPriv.group_id == group_id))
    db.execute(delete(GroupMember).where(GroupMember.group_id == group_id))
    db.delete(group)
    log_action(
        db, request=request, user=user, module="group", method="delete",
        message=f"删除用户组 {group_id}", params={"force": force},
    )
    db.commit()
    return {"success": True}


@router.put("/groups/{group_id}/users")
def set_group_users(
    group_id: int,
    payload: GroupUsersRequest,
    request: Request,
    user: User = Depends(require_perm("group", "assignuser")),
    db: Session = Depends(get_db),
) -> dict:
    _get_group(db, group_id)
    accounts = sorted(set(payload.accounts))
    if accounts:
        found = set(
            db.scalars(
                select(User.account).where(User.account.in_(accounts), User.status != "deleted")
            ).all()
        )
        missing = [account for account in accounts if account not in found]
        if missing:
            raise ValidationError(f"账号不存在：{','.join(missing)}")

    db.execute(delete(GroupMember).where(GroupMember.group_id == group_id))
    for account in accounts:
        db.add(GroupMember(account=account, group_id=group_id))
    log_action(
        db, request=request, user=user, module="group", method="assignuser",
        message=f"设置组成员 {group_id}", params=payload,
    )
    db.commit()
    return {"success": True, "count": len(accounts)}


@router.get("/groups/{group_id}/privileges")
def get_group_privileges(
    group_id: int,
    user: User = Depends(require_perm("group", "viewpriv")),
    db: Session = Depends(get_db),
) -> dict:
    _get_group(db, group_id)
    checked = {
        (row[0], row[1])
        for row in db.execute(
            select(GroupPriv.module, GroupPriv.method).where(GroupPriv.group_id == group_id)
        ).all()
    }
    modules: dict[str, dict] = {}
    for module, _name, method, _label in PRIVILEGES:
        node = modules.setdefault(
            module, {"module": module, "module_name": MODULE_NAMES[module], "methods": []}
        )
        node["methods"].append(
            {"method": method, "name": _label, "checked": (module, method) in checked}
        )
    ordered = sorted(modules.values(), key=lambda item: MODULE_ORDER[item["module"]])
    return {"privileges": ordered}


@router.put("/groups/{group_id}/privileges")
def set_group_privileges(
    group_id: int,
    payload: GroupPrivRequest,
    request: Request,
    user: User = Depends(require_perm("group", "editpriv")),
    db: Session = Depends(get_db),
) -> dict:
    _get_group(db, group_id)
    pairs = _parse_privileges(payload.privileges)
    _replace_privileges(db, group_id, pairs)
    log_action(
        db, request=request, user=user, module="group", method="editpriv",
        message=f"设置组权限 {group_id}", params=payload,
    )
    db.commit()
    return {"success": True, "count": len(pairs)}

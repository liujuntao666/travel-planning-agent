from fastapi import APIRouter, Depends, Query

from app.common.constants import MENUS, MODULE_NAMES, MODULE_ORDER, PRIVILEGES
from app.common.db import get_db
from app.deps import get_current_user, permission_source
from app.models import User

from sqlalchemy.orm import Session

router = APIRouter(tags=["privileges"])


@router.get("/privileges")
def list_privileges(
    module: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if permission_source(db, user, "privilege", "browse") == "NONE":
        from app.common.errors import ForbiddenError

        raise ForbiddenError("无权限：privilege-browse")

    modules: dict[str, dict] = {}
    for mod, _name, method, label in PRIVILEGES:
        if module and mod != module:
            continue
        node = modules.setdefault(
            mod, {"module": mod, "name": MODULE_NAMES[mod], "methods": []}
        )
        node["methods"].append({"method": method, "name": label})
    ordered = sorted(modules.values(), key=lambda item: MODULE_ORDER[item["module"]])
    return {"modules": ordered}


@router.get("/privileges/check")
def check_privilege(
    module: str = Query(...),
    method: str = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    via = permission_source(db, user, module, method)
    allowed = via != "NONE"
    return {
        "allowed": allowed,
        "via": via,
        "reason": None if allowed else f"用户所属用户组未被授予 {module}-{method}",
    }


@router.get("/menus")
def get_menus(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    def allowed(node: dict) -> bool:
        return permission_source(db, user, node["module"], node["method"]) != "NONE"

    menus = []
    for node in MENUS:
        if not allowed(node):
            continue
        item = dict(node)
        item["children"] = [dict(child) for child in node["children"] if allowed(child)]
        menus.append(item)
    return {"menus": menus}

"""权限清单、模块与菜单定义，与《接口设计文档》34 个接口一一对应。"""

MODULES = [
    (
        "user",
        "用户管理",
        [
            ("browse", "查看用户"),
            ("create", "创建用户"),
            ("view", "查看用户详情"),
            ("edit", "修改用户"),
            ("delete", "删除用户"),
            ("unlock", "解锁账号"),
            ("resetpwd", "重置密码"),
            ("assigngroup", "设置用户组"),
        ],
    ),
    (
        "dept",
        "部门管理",
        [
            ("browse", "查看部门树"),
            ("create", "新建部门"),
            ("edit", "修改部门"),
            ("delete", "删除部门"),
            ("move", "移动部门"),
        ],
    ),
    (
        "group",
        "用户组管理",
        [
            ("browse", "查看用户组"),
            ("create", "新建用户组"),
            ("view", "查看组详情"),
            ("edit", "修改用户组"),
            ("delete", "删除用户组"),
            ("assignuser", "设置组成员"),
            ("viewpriv", "查看组权限"),
            ("editpriv", "设置组权限"),
        ],
    ),
    (
        "privilege",
        "权限管理",
        [
            ("browse", "查看权限清单"),
        ],
    ),
    (
        "data",
        "数据范围",
        [
            ("view", "查看数据范围"),
            ("edit", "设置数据范围"),
        ],
    ),
    (
        "log",
        "操作日志",
        [
            ("browse", "查看操作日志"),
            ("view", "查看日志详情"),
        ],
    ),
]

PRIVILEGES = [
    (module, module_name, method, name)
    for module, module_name, methods in MODULES
    for method, name in methods
]

MODULE_ORDER = {module: index for index, (module, _name, _methods) in enumerate(MODULES)}
MODULE_NAMES = {module: name for module, name, _methods in MODULES}


def priv_key(module: str, method: str) -> str:
    return f"{module}-{method}"


MENUS = [
    {"id": "user", "name": "用户管理", "module": "user", "method": "browse",
     "url": "/user-browse", "icon": "users", "children": []},
    {"id": "dept", "name": "部门管理", "module": "dept", "method": "browse",
     "url": "/dept-browse", "icon": "sitemap", "children": []},
    {"id": "group", "name": "用户组管理", "module": "group", "method": "browse",
     "url": "/group-browse", "icon": "usergroup", "children": []},
    {"id": "privilege", "name": "权限管理", "module": "privilege", "method": "browse",
     "url": "/privilege-browse", "icon": "key", "children": []},
    {"id": "data", "name": "数据范围", "module": "data", "method": "view",
     "url": "/data-scope", "icon": "database", "children": []},
    {"id": "log", "name": "操作日志", "module": "log", "method": "browse",
     "url": "/log-browse", "icon": "file-text", "children": []},
]

from sqlalchemy import select

from app.common.constants import PRIVILEGES
from app.common.db import SessionLocal
from app.models import (
    Dept,
    Group,
    GroupMember,
    GroupPriv,
    Privilege,
    Product,
    ProductAcl,
    Project,
    ProjectAcl,
    User,
)

DEPTS = [
    (1, "总公司", 0, ",1,", "admin", 1),
    (2, "研发中心", 1, ",1,2,", "lisi", 2),
    (3, "研发部", 2, ",1,2,3,", "lisi", 3),
    (4, "测试部", 2, ",1,2,4,", "wangwu", 4),
    (5, "产品部", 1, ",1,5,", "zhaoliu", 5),
    (6, "项目管理部", 1, ",1,6,", "sunqi", 6),
]

GROUPS = [
    (1, "研发-开发", "dev", "研发人员默认权限"),
    (2, "测试-质量", "qa", "测试人员默认权限"),
    (3, "产品-产品经理", "po", "产品人员默认权限"),
    (4, "项目-项目经理", "pm", "项目管理人员默认权限"),
]

GROUP_PRIVS = {
    1: ["user-browse", "dept-browse", "group-browse", "privilege-browse", "data-view", "log-browse"],
    2: ["user-browse", "dept-browse", "data-view", "log-browse"],
    3: ["user-browse", "privilege-browse", "data-view"],
    4: ["user-browse", "dept-browse", "group-browse", "data-view", "log-browse"],
}

# 密码均为 MD5 摘要：admin888 / 123456
USERS = [
    (1, "admin", "系统管理员", "7fef6171469e80d32c0559f88b377245", 1, "td", "yes", "admin@example.com"),
    (2, "zhangsan", "张三", "e10adc3949ba59abbe56e057f20f883e", 3, "dev", "no", "zhangsan@example.com"),
    (3, "lisi", "李四", "e10adc3949ba59abbe56e057f20f883e", 3, "dev", "no", "lisi@example.com"),
    (4, "wangwu", "王五", "e10adc3949ba59abbe56e057f20f883e", 4, "qa", "no", "wangwu@example.com"),
    (5, "zhaoliu", "赵六", "e10adc3949ba59abbe56e057f20f883e", 5, "po", "no", "zhaoliu@example.com"),
    (6, "sunqi", "孙七", "e10adc3949ba59abbe56e057f20f883e", 6, "pm", "no", "sunqi@example.com"),
]

MEMBERS = [
    (2, 1),
    (3, 1),
    (4, 2),
    (5, 3),
    (6, 4),
]

PRODUCTS = [
    (1, "禅道开源版", True),
    (2, "禅道企业版", False),
    (3, "禅道移动端", False),
]

PROJECTS = [
    (1, "RBAC 权限模块重构",),
    (2, "报表平台",),
    (3, "移动端适配",),
]

PRODUCT_ACLS = [(2, 2), (3, 2)]
PROJECT_ACLS = [(2, 1), (3, 2)]


def seed_initial_data() -> None:
    """幂等写入演示数据；admin 已存在时直接跳过。"""
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.account == "admin")) is not None:
            return

        for dept_id, name, parent, path, manager, position in DEPTS:
            db.add(Dept(id=dept_id, name=name, parent=parent, path=path,
                        manager=manager, position=position))

        for module, module_name, method, name in PRIVILEGES:
            db.add(Privilege(module=module, module_name=module_name, method=method, name=name))

        for group_id, name, role, desc in GROUPS:
            db.add(Group(id=group_id, name=name, role=role, description=desc))

        for group_id, keys in GROUP_PRIVS.items():
            for key in keys:
                module, method = key.split("-", 1)
                db.add(GroupPriv(group_id=group_id, module=module, method=method))

        for user_id, account, realname, password, dept_id, role, admin, email in USERS:
            db.add(User(id=user_id, account=account, realname=realname, password=password,
                        dept_id=dept_id, role=role, admin=admin, status="active", email=email))

        for account_id, group_id in MEMBERS:
            account = next(row[1] for row in USERS if row[0] == account_id)
            db.add(GroupMember(account=account, group_id=group_id))

        for product_id, name, acl_open in PRODUCTS:
            db.add(Product(id=product_id, name=name, acl_open=acl_open))

        for project_id, name in PROJECTS:
            db.add(Project(id=project_id, name=name))

        for account_id, product_id in PRODUCT_ACLS:
            account = next(row[1] for row in USERS if row[0] == account_id)
            db.add(ProductAcl(account=account, product_id=product_id))

        for account_id, project_id in PROJECT_ACLS:
            account = next(row[1] for row in USERS if row[0] == account_id)
            db.add(ProjectAcl(account=account, project_id=project_id))

        db.commit()

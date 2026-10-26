-- 仿禅道项目管理系统 RBAC 权限模块 初始化数据
USE `zentao_rbac`;

-- 部门树（path 形如 ,1,3,）
INSERT INTO `zt_dept` (`id`, `name`, `parent`, `path`, `manager`, `position`) VALUES
  (1, '总公司', 0, ',1,', 'admin', 1),
  (2, '研发中心', 1, ',1,2,', 'lisi', 2),
  (3, '研发部', 2, ',1,2,3,', 'lisi', 3),
  (4, '测试部', 2, ',1,2,4,', 'wangwu', 4),
  (5, '产品部', 1, ',1,5,', 'zhaoliu', 5),
  (6, '项目管理部', 1, ',1,6,', 'sunqi', 6);

-- 权限清单（module-method，与接口设计文档 34 个接口一一对应）
INSERT INTO `zt_privilege` (`module`, `module_name`, `method`, `name`) VALUES
  ('user', '用户管理', 'browse', '查看用户'),
  ('user', '用户管理', 'create', '创建用户'),
  ('user', '用户管理', 'view', '查看用户详情'),
  ('user', '用户管理', 'edit', '修改用户'),
  ('user', '用户管理', 'delete', '删除用户'),
  ('user', '用户管理', 'unlock', '解锁账号'),
  ('user', '用户管理', 'resetpwd', '重置密码'),
  ('user', '用户管理', 'assigngroup', '设置用户组'),
  ('dept', '部门管理', 'browse', '查看部门树'),
  ('dept', '部门管理', 'create', '新建部门'),
  ('dept', '部门管理', 'edit', '修改部门'),
  ('dept', '部门管理', 'delete', '删除部门'),
  ('dept', '部门管理', 'move', '移动部门'),
  ('group', '用户组管理', 'browse', '查看用户组'),
  ('group', '用户组管理', 'create', '新建用户组'),
  ('group', '用户组管理', 'view', '查看组详情'),
  ('group', '用户组管理', 'edit', '修改用户组'),
  ('group', '用户组管理', 'delete', '删除用户组'),
  ('group', '用户组管理', 'assignuser', '设置组成员'),
  ('group', '用户组管理', 'viewpriv', '查看组权限'),
  ('group', '用户组管理', 'editpriv', '设置组权限'),
  ('privilege', '权限管理', 'browse', '查看权限清单'),
  ('data', '数据范围', 'view', '查看数据范围'),
  ('data', '数据范围', 'edit', '设置数据范围'),
  ('log', '操作日志', 'browse', '查看操作日志'),
  ('log', '操作日志', 'view', '查看日志详情');

-- 用户组
INSERT INTO `zt_group` (`id`, `name`, `role`, `description`) VALUES
  (1, '研发-开发', 'dev', '研发人员默认权限'),
  (2, '测试-质量', 'qa', '测试人员默认权限'),
  (3, '产品-产品经理', 'po', '产品人员默认权限'),
  (4, '项目-项目经理', 'pm', '项目管理人员默认权限');

-- 组权限（module-method 粒度）
INSERT INTO `zt_grouppriv` (`group_id`, `module`, `method`) VALUES
  (1, 'user', 'browse'), (1, 'dept', 'browse'), (1, 'group', 'browse'),
  (1, 'privilege', 'browse'), (1, 'data', 'view'), (1, 'log', 'browse'),
  (2, 'user', 'browse'), (2, 'dept', 'browse'), (2, 'data', 'view'), (2, 'log', 'browse'),
  (3, 'user', 'browse'), (3, 'privilege', 'browse'), (3, 'data', 'view'),
  (4, 'user', 'browse'), (4, 'dept', 'browse'), (4, 'group', 'browse'),
  (4, 'data', 'view'), (4, 'log', 'browse');

-- 用户（密码为 MD5 摘要：admin888 / 123456）
INSERT INTO `zt_user` (`id`, `account`, `realname`, `password`, `dept_id`, `role`, `admin`, `status`, `email`) VALUES
  (1, 'admin', '系统管理员', '7fef6171469e80d32c0559f88b377245', 1, 'td', 'yes', 'active', 'admin@example.com'),
  (2, 'zhangsan', '张三', 'e10adc3949ba59abbe56e057f20f883e', 3, 'dev', 'no', 'active', 'zhangsan@example.com'),
  (3, 'lisi', '李四', 'e10adc3949ba59abbe56e057f20f883e', 3, 'dev', 'no', 'active', 'lisi@example.com'),
  (4, 'wangwu', '王五', 'e10adc3949ba59abbe56e057f20f883e', 4, 'qa', 'no', 'active', 'wangwu@example.com'),
  (5, 'zhaoliu', '赵六', 'e10adc3949ba59abbe56e057f20f883e', 5, 'po', 'no', 'active', 'zhaoliu@example.com'),
  (6, 'sunqi', '孙七', 'e10adc3949ba59abbe56e057f20f883e', 6, 'pm', 'no', 'active', 'sunqi@example.com');

-- 组成员
INSERT INTO `zt_usergroup` (`account`, `group_id`) VALUES
  ('zhangsan', 1), ('lisi', 1), ('wangwu', 2), ('zhaoliu', 3), ('sunqi', 4);

-- 产品与项目
INSERT INTO `zt_product` (`id`, `name`, `acl_open`) VALUES
  (1, '禅道开源版', 1), (2, '禅道企业版', 0), (3, '禅道移动端', 0);

INSERT INTO `zt_project` (`id`, `name`) VALUES
  (1, 'RBAC 权限模块重构'), (2, '报表平台'), (3, '移动端适配');

-- 数据范围（产品 / 项目白名单）
INSERT INTO `zt_productacl` (`account`, `product_id`) VALUES
  ('zhangsan', 2), ('lisi', 3);

INSERT INTO `zt_projectacl` (`account`, `project_id`) VALUES
  ('zhangsan', 1), ('lisi', 2);

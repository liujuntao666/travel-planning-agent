-- 仿禅道项目管理系统 RBAC 权限模块 建表脚本（MySQL 8.0）
CREATE DATABASE IF NOT EXISTS `zentao_rbac` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE `zentao_rbac`;

DROP TABLE IF EXISTS `zt_auth_token`;
DROP TABLE IF EXISTS `zt_operationlog`;
DROP TABLE IF EXISTS `zt_projectacl`;
DROP TABLE IF EXISTS `zt_productacl`;
DROP TABLE IF EXISTS `zt_project`;
DROP TABLE IF EXISTS `zt_product`;
DROP TABLE IF EXISTS `zt_grouppriv`;
DROP TABLE IF EXISTS `zt_privilege`;
DROP TABLE IF EXISTS `zt_usergroup`;
DROP TABLE IF EXISTS `zt_group`;
DROP TABLE IF EXISTS `zt_user`;
DROP TABLE IF EXISTS `zt_dept`;

CREATE TABLE `zt_dept` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '部门 ID',
  `name` VARCHAR(100) NOT NULL COMMENT '部门名称',
  `parent` INT NOT NULL DEFAULT 0 COMMENT '父部门 ID，根为 0',
  `path` VARCHAR(255) NOT NULL DEFAULT '' COMMENT '路径，形如 ,1,3,',
  `manager` VARCHAR(30) DEFAULT NULL COMMENT '负责人账号',
  `position` INT NOT NULL DEFAULT 0 COMMENT '排序值',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_dept_parent` (`parent`),
  KEY `idx_dept_path` (`path`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='部门表';

CREATE TABLE `zt_user` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '用户 ID',
  `account` VARCHAR(30) NOT NULL COMMENT '登录账号',
  `realname` VARCHAR(50) NOT NULL COMMENT '真实姓名',
  `password` VARCHAR(64) NOT NULL COMMENT '密码（MD5 摘要）',
  `dept_id` INT NOT NULL COMMENT '所属部门 ID',
  `role` VARCHAR(10) NOT NULL DEFAULT 'dev' COMMENT '角色标签',
  `admin` VARCHAR(3) NOT NULL DEFAULT 'no' COMMENT '是否超级管理员 yes/no',
  `status` VARCHAR(10) NOT NULL DEFAULT 'active' COMMENT 'active/locked/deleted',
  `email` VARCHAR(100) DEFAULT NULL,
  `phone` VARCHAR(30) DEFAULT NULL,
  `login_fails` INT NOT NULL DEFAULT 0 COMMENT '连续登录失败次数',
  `locked_until` DATETIME DEFAULT NULL COMMENT '锁定截止时间',
  `last_login` DATETIME DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_account` (`account`),
  KEY `idx_user_dept` (`dept_id`),
  KEY `idx_user_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

CREATE TABLE `zt_group` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '用户组 ID',
  `name` VARCHAR(100) NOT NULL COMMENT '组名',
  `role` VARCHAR(10) DEFAULT NULL COMMENT '角色标签',
  `description` VARCHAR(255) DEFAULT NULL COMMENT '描述',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_group_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户组表';

CREATE TABLE `zt_usergroup` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `account` VARCHAR(30) NOT NULL COMMENT '用户账号',
  `group_id` INT NOT NULL COMMENT '用户组 ID',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_usergroup` (`account`, `group_id`),
  KEY `idx_usergroup_group` (`group_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户-用户组关系表';

CREATE TABLE `zt_privilege` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `module` VARCHAR(30) NOT NULL COMMENT '模块标识',
  `module_name` VARCHAR(50) NOT NULL COMMENT '模块名称',
  `method` VARCHAR(30) NOT NULL COMMENT '方法标识',
  `name` VARCHAR(50) NOT NULL COMMENT '权限名称',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_privilege` (`module`, `method`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='权限清单表';

CREATE TABLE `zt_grouppriv` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `group_id` INT NOT NULL COMMENT '用户组 ID',
  `module` VARCHAR(30) NOT NULL COMMENT '模块标识',
  `method` VARCHAR(30) NOT NULL COMMENT '方法标识',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_grouppriv` (`group_id`, `module`, `method`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户组权限表';

CREATE TABLE `zt_product` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(100) NOT NULL,
  `acl_open` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否全员开放',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='产品表';

CREATE TABLE `zt_project` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(100) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='项目表';

CREATE TABLE `zt_productacl` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `account` VARCHAR(30) NOT NULL,
  `product_id` INT NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_productacl` (`account`, `product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='产品白名单';

CREATE TABLE `zt_projectacl` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `account` VARCHAR(30) NOT NULL,
  `project_id` INT NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_projectacl` (`account`, `project_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='项目白名单';

CREATE TABLE `zt_operationlog` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `account` VARCHAR(30) NOT NULL COMMENT '操作人账号',
  `realname` VARCHAR(50) DEFAULT NULL,
  `module` VARCHAR(30) NOT NULL,
  `method` VARCHAR(30) NOT NULL,
  `ip` VARCHAR(64) NOT NULL DEFAULT '',
  `result` VARCHAR(10) NOT NULL DEFAULT 'SUCCESS' COMMENT 'SUCCESS/FAIL',
  `message` TEXT DEFAULT NULL,
  `params` JSON DEFAULT NULL COMMENT '请求参数摘要（敏感字段已脱敏）',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_log_account` (`account`),
  KEY `idx_log_module` (`module`),
  KEY `idx_log_result` (`result`),
  KEY `idx_log_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='操作日志表';

CREATE TABLE `zt_auth_token` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `token` VARCHAR(64) NOT NULL,
  `account` VARCHAR(30) NOT NULL,
  `expires_at` DATETIME NOT NULL,
  `revoked` TINYINT(1) NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_token` (`token`),
  KEY `idx_token_account` (`account`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='访问令牌表';

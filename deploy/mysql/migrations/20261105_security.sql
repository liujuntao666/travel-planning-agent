-- ============================================================================
-- 增量迁移：Token+RBAC 鉴权与接口幂等控制
-- 适用对象：已初始化过 deploy/mysql/init/01_schema.sql 的存量数据库
-- 执行方式：mysql -u travel -p travel_planning < 20261105_security.sql
-- ============================================================================

SET NAMES utf8mb4;

-- 1. 用户角色（RBAC）
ALTER TABLE `t_user`
  ADD COLUMN `role` varchar(16) NOT NULL DEFAULT 'USER'
  COMMENT 'RBAC 角色：USER / ADMIN' AFTER `source`;

-- 2. 幂等请求记录
CREATE TABLE IF NOT EXISTS `t_idempotency_record` (
  `request_id` varchar(64) NOT NULL COMMENT '唯一请求标识（Idempotency-Key）',
  `user_id` bigint NULL COMMENT '调用用户ID',
  `method` varchar(8) NOT NULL COMMENT 'HTTP 方法',
  `path` varchar(255) NOT NULL COMMENT '请求路径',
  `request_hash` varchar(64) NOT NULL COMMENT '请求体 SHA-256 摘要，用于识别标识复用',
  `state` varchar(16) NOT NULL DEFAULT 'PROCESSING' COMMENT '状态：PROCESSING / DONE',
  `status_code` int NULL COMMENT '首次响应状态码',
  `response_body` mediumtext NULL COMMENT '首次成功响应体，用于幂等回放',
  `expires_at` datetime NULL COMMENT '记录过期时间',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`request_id`),
  KEY `idx_idem_expire` (`expires_at`),
  KEY `idx_idem_user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='幂等请求记录表：写操作按唯一请求标识去重并回放首次成功响应';

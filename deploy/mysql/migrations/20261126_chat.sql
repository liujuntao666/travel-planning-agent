-- ============================================================================
-- 增量迁移：旅行顾问实时聊天（WebSocket 长连接）
-- 适用对象：已初始化过 deploy/mysql/init/01_schema.sql 的存量数据库
-- 执行方式：mysql -u travel -p travel_planning < 20261126_chat.sql
-- ============================================================================

SET NAMES utf8mb4;

-- 会话：一个咨询用户对应一条会话
CREATE TABLE IF NOT EXISTS `t_chat_thread` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `user_id` bigint NOT NULL COMMENT '咨询用户ID',
  `advisor_id` bigint NULL COMMENT '接待顾问ID，未分配为空',
  `title` varchar(128) NULL DEFAULT '旅行顾问咨询' COMMENT '会话标题',
  `last_seq` int NOT NULL DEFAULT 0 COMMENT '会话内最大消息序号',
  `last_message_at` datetime NULL COMMENT '最后一条消息时间',
  `status` tinyint NOT NULL DEFAULT 1 COMMENT '状态：1-进行中，0-已关闭',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_chat_thread_user` (`user_id`),
  KEY `idx_chat_thread_advisor` (`advisor_id`),
  CONSTRAINT `FK_t_chat_thread_t_user` FOREIGN KEY (`user_id`) REFERENCES `t_user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `FK_t_chat_thread_advisor` FOREIGN KEY (`advisor_id`) REFERENCES `t_user` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='实时聊天会话表：用户与旅行顾问的一对一会话';

-- 消息：seq 由服务端按会话发号，client_id 用于幂等去重
CREATE TABLE IF NOT EXISTS `t_chat_message` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `thread_id` bigint NOT NULL COMMENT '会话ID',
  `seq` int NOT NULL COMMENT '会话内单调递增序号',
  `sender_id` bigint NULL COMMENT '发送者用户ID，系统消息为空',
  `sender_role` varchar(16) NOT NULL DEFAULT 'USER' COMMENT '发送方角色：USER / ADVISOR / SYSTEM',
  `content` text NOT NULL COMMENT '消息正文',
  `client_id` varchar(64) NULL COMMENT '客户端消息唯一标识，用于 ACK 重发去重',
  `read_flag` tinyint NOT NULL DEFAULT 0 COMMENT '已读标记：0-未读，1-已读',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_chat_thread_seq` (`thread_id`, `seq`),
  UNIQUE KEY `uk_chat_client_id` (`client_id`),
  KEY `idx_chat_msg_thread` (`thread_id`, `seq`),
  CONSTRAINT `FK_t_chat_message_t_thread` FOREIGN KEY (`thread_id`) REFERENCES `t_chat_thread` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='实时聊天消息表：落库后按 seq 游标做增量同步';

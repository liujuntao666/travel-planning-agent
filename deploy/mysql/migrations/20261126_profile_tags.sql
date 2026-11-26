-- ============================================================================
-- 增量迁移：用户行为采集与规则打标
-- 适用对象：已初始化过 deploy/mysql/init/01_schema.sql 的存量数据库
-- 执行方式：mysql -u travel -p travel_planning < 20261126_profile_tags.sql
-- 说明：脚本可重复执行；只新增表与字典数据，不改动既有业务表
-- ============================================================================

SET NAMES utf8mb4;

-- 1. 用户行为事件（只记录动作与对象，不保存对话原文）
CREATE TABLE IF NOT EXISTS `t_user_event` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `user_id` bigint NOT NULL COMMENT '用户ID',
  `event_type` varchar(32) NOT NULL COMMENT '事件类型：new_conversation / replan / rollback_version / export / adjust_item',
  `target_type` varchar(32) NULL COMMENT '对象类型：conversation / trip / trip_version',
  `target_id` bigint NULL COMMENT '对象ID',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '发生时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  KEY `idx_user_event_user_time` (`user_id`, `created_at`),
  CONSTRAINT `FK_t_user_event_t_user` FOREIGN KEY (`user_id`) REFERENCES `t_user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='用户行为事件表：只记录动作与对象，不保存对话原文';

-- 2. 标签字典
CREATE TABLE IF NOT EXISTS `t_tag_dict` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `tag_code` varchar(64) NOT NULL COMMENT '标签编码，全局唯一',
  `tag_name` varchar(64) NOT NULL COMMENT '标签名称',
  `category` varchar(32) NOT NULL COMMENT '标签维度：预算 / 行程时长 / 旅行风格 / 活跃度 / 导出偏好',
  `description` varchar(255) NULL COMMENT '标签说明',
  `status` tinyint NOT NULL DEFAULT 1 COMMENT '状态：1-启用，0-停用',
  `sort_no` int NOT NULL DEFAULT 0 COMMENT '排序号',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  UNIQUE KEY `AK_t_tag_dict_code` (`tag_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='用户标签字典表：规则打标只允许落到字典内的编码';

-- 3. 用户标签
CREATE TABLE IF NOT EXISTS `t_user_tag` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `user_id` bigint NOT NULL COMMENT '用户ID',
  `tag_code` varchar(64) NOT NULL COMMENT '标签编码，对应 t_tag_dict.tag_code',
  `score` decimal(5,2) NOT NULL DEFAULT 0 COMMENT '标签得分（0～100）',
  `confidence` decimal(5,4) NOT NULL DEFAULT 1 COMMENT '置信度（0～1）',
  `source` varchar(16) NOT NULL DEFAULT 'RULE' COMMENT '标签来源：RULE / LLM / MANUAL',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  UNIQUE KEY `AK_t_user_tag_user_code` (`user_id`, `tag_code`),
  KEY `idx_user_tag_user` (`user_id`),
  CONSTRAINT `FK_t_user_tag_t_user` FOREIGN KEY (`user_id`) REFERENCES `t_user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='用户标签表：带来源与置信度，支持按用户整体清除';

-- 4. 标签字典数据
INSERT INTO `t_tag_dict` (`tag_code`, `tag_name`, `category`, `description`, `sort_no`, `status`) VALUES
  ('BUDGET_ECONOMY', '经济型预算', '预算', '人均预算 1500 元以内', 10, 1),
  ('BUDGET_COMFORT', '舒适型预算', '预算', '人均预算 1500～3000 元', 11, 1),
  ('BUDGET_LUXURY', '高端型预算', '预算', '人均预算 3000 元以上', 12, 1),
  ('LENGTH_SHORT', '短途出行', '行程时长', '偏好 3 天以内', 20, 1),
  ('LENGTH_MEDIUM', '中程出行', '行程时长', '偏好 4～6 天', 21, 1),
  ('LENGTH_LONG', '长途出行', '行程时长', '偏好 7 天及以上', 22, 1),
  ('STYLE_COMMON', '均衡节奏', '旅行风格', '兼顾观景与体验', 30, 1),
  ('STYLE_RELAX', '休闲节奏', '旅行风格', '每日 1～2 个主点位', 31, 1),
  ('STYLE_COUPLE', '情侣出游', '旅行风格', '偏好景观、街区与咖啡馆', 32, 1),
  ('STYLE_FAMILY', '家庭出游', '旅行风格', '含午休，点位集中', 33, 1),
  ('STYLE_KIDS', '亲子出游', '旅行风格', '亲子友好，安排午休', 34, 1),
  ('STYLE_HIKE', '徒步偏好', '旅行风格', '自然线路优先', 35, 1),
  ('STYLE_PHOTO', '摄影偏好', '旅行风格', '围绕日出日落机位排期', 36, 1),
  ('STYLE_FOOD', '美食偏好', '旅行风格', '围绕市集与老字号', 37, 1),
  ('ACTIVITY_HIGH', '高频使用', '活跃度', '近 30 天频繁规划或调整行程', 40, 1),
  ('ACTIVITY_MEDIUM', '中频使用', '活跃度', '近 30 天有多次使用', 41, 1),
  ('ACTIVITY_LOW', '低频使用', '活跃度', '近期使用较少', 42, 1),
  ('EXPORT_PDF', 'PDF 行程单', '导出偏好', '偏好导出 PDF 行程单', 50, 1),
  ('EXPORT_LONG_IMAGE', '长图分享', '导出偏好', '偏好导出长图分享', 51, 1),
  ('EXPORT_WECHAT_ARTICLE', '公众号文章', '导出偏好', '偏好导出公众号文章', 52, 1)
ON DUPLICATE KEY UPDATE
  `tag_name` = VALUES(`tag_name`),
  `category` = VALUES(`category`),
  `description` = VALUES(`description`),
  `sort_no` = VALUES(`sort_no`);

-- ============================================================================
-- 旅游规划智能体系统  数据库建表脚本
-- 目标数据库：MySQL 8.0    字符集：utf8mb4 / utf8mb4_general_ci
-- 依据文档  ：《旅游规划智能体系统 需求分析文档（第一版）》
--               第 3 章 需求建模、第 4 章 功能需求、第 5 章 非功能需求
-- 表数量    ：20 张（含 17 个外键约束）
-- 生成方式  ：由 data-model/schema_model.py 自动生成，请勿手工修改
-- ============================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ---------------------------------------------------------------- 清理旧表
DROP TABLE IF EXISTS `t_content_audit_log`;
DROP TABLE IF EXISTS `t_trip_style`;
DROP TABLE IF EXISTS `t_travel_tips`;
DROP TABLE IF EXISTS `t_tool_call_log`;
DROP TABLE IF EXISTS `t_restaurant`;
DROP TABLE IF EXISTS `t_weather`;
DROP TABLE IF EXISTS `t_transport_option`;
DROP TABLE IF EXISTS `t_hotel`;
DROP TABLE IF EXISTS `t_poi`;
DROP TABLE IF EXISTS `t_trip_export`;
DROP TABLE IF EXISTS `t_trip_transport`;
DROP TABLE IF EXISTS `t_trip_lodging`;
DROP TABLE IF EXISTS `t_trip_item`;
DROP TABLE IF EXISTS `t_trip_day`;
DROP TABLE IF EXISTS `t_trip_version`;
DROP TABLE IF EXISTS `t_trip`;
DROP TABLE IF EXISTS `t_requirement_slot`;
DROP TABLE IF EXISTS `t_message`;
DROP TABLE IF EXISTS `t_conversation`;
DROP TABLE IF EXISTS `t_user`;

-- ---------------------------------------------------------------- t_user  游客用户
CREATE TABLE `t_user` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `open_id` varchar(64) NOT NULL COMMENT '微信 / 小程序 / App 的 OpenID',
  `nickname` varchar(64) NULL COMMENT '昵称',
  `avatar_url` varchar(255) NULL COMMENT '头像地址',
  `phone` varchar(32) NULL COMMENT '手机号',
  `gender` tinyint NULL DEFAULT 0 COMMENT '性别：0-未知，1-男，2-女',
  `source` varchar(32) NULL DEFAULT 'APP' COMMENT '接入入口：APP / H5 / MINI',
  `status` tinyint NULL DEFAULT 1 COMMENT '状态：1-正常，0-禁用',
  `last_login_at` datetime NULL COMMENT '最近登录时间',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  UNIQUE KEY `AK_t_user_open_id` (`open_id`),
  KEY `idx_user_phone` (`phone`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='游客用户表：记录 C 端游客的身份与入口信息（FR-01）';

-- ---------------------------------------------------------------- t_conversation  会话
CREATE TABLE `t_conversation` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `user_id` bigint NOT NULL COMMENT '所属游客ID',
  `title` varchar(128) NULL COMMENT '会话标题，默认取首句需求',
  `last_intent` varchar(32) NULL COMMENT '最近一次识别意图：NEW_PLAN / ADJUST / CONSULT（NFR-02）',
  `status` tinyint NULL DEFAULT 1 COMMENT '状态：1-进行中，2-已结束',
  `current_trip_id` bigint NULL COMMENT '会话当前关联的行程ID',
  `message_count` int NULL DEFAULT 0 COMMENT '消息条数',
  `last_message_at` datetime NULL COMMENT '最近消息时间',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  KEY `idx_conv_user` (`user_id`),
  KEY `idx_conv_last_msg` (`last_message_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='会话表：对话式规划的一次完整会话，承载多轮上下文（FR-01 / 场景二）';

-- ---------------------------------------------------------------- t_message  会话消息
CREATE TABLE `t_message` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `conversation_id` bigint NOT NULL COMMENT '所属会话ID',
  `seq` int NOT NULL COMMENT '会话内递增序号',
  `role` varchar(16) NOT NULL COMMENT '角色：USER / ASSISTANT / SYSTEM / TOOL',
  `content` mediumtext NULL COMMENT '消息正文',
  `content_type` varchar(16) NULL DEFAULT 'TEXT' COMMENT '内容类型：TEXT / MARKDOWN / CARD',
  `intent` varchar(32) NULL COMMENT '该条消息识别出的意图：NEW_PLAN / ADJUST / CONSULT',
  `stream_flag` tinyint NULL DEFAULT 0 COMMENT '是否流式输出：1-是，0-否（NFR-06）',
  `token_count` int NULL DEFAULT 0 COMMENT '消耗 Token 数',
  `latency_ms` int NULL DEFAULT 0 COMMENT '响应耗时（毫秒，NFR-07）',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  KEY `idx_msg_conv_seq` (`conversation_id`, `seq`),
  KEY `idx_msg_conv_time` (`conversation_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='会话消息表：逐条留存对话内容，构成会话上下文（FR-01）';

-- ---------------------------------------------------------------- t_requirement_slot  需求要素槽位
CREATE TABLE `t_requirement_slot` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `conversation_id` bigint NOT NULL COMMENT '所属会话ID',
  `trip_id` bigint NULL COMMENT '已落到行程时回填行程ID',
  `slot_key` varchar(32) NOT NULL COMMENT '要素键：ORIGIN / DEST / NIGHTS / PEOPLE / BUDGET / STYLE / TRANSPORT / TABOO',
  `slot_value` varchar(255) NULL COMMENT '抽取到的要素值',
  `value_type` varchar(16) NULL DEFAULT 'TEXT' COMMENT '值类型：TEXT / NUMBER / LIST / DATE',
  `required_flag` tinyint NULL DEFAULT 0 COMMENT '是否必填：1-必填，0-选填（出发地 / 目的地 / 天数 为必填）',
  `filled_flag` tinyint NULL DEFAULT 0 COMMENT '是否已填：1-已填，0-缺失待追问',
  `ask_count` int NULL DEFAULT 0 COMMENT '追问次数',
  `confidence` decimal(5,4) NULL COMMENT '抽取置信度，用于 NFR-01 准确率评测',
  `slot_source` varchar(16) NULL DEFAULT 'EXTRACT' COMMENT '来源：EXTRACT / USER_INPUT / DEFAULT',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  UNIQUE KEY `AK_slot_conv_key` (`conversation_id`, `slot_key`),
  KEY `idx_slot_trip` (`trip_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='需求要素槽位表：八类要素的抽取结果与追问状态（FR-01 / NFR-01）';

-- ---------------------------------------------------------------- t_trip  行程
CREATE TABLE `t_trip` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `trip_no` varchar(32) NOT NULL COMMENT '业务行程编号',
  `user_id` bigint NOT NULL COMMENT '所属游客ID',
  `conversation_id` bigint NULL COMMENT '来源会话ID',
  `title` varchar(128) NULL COMMENT '行程标题',
  `origin_city` varchar(64) NULL COMMENT '出发地城市',
  `dest_cities` varchar(255) NULL COMMENT '目的地，多城市以 / 分隔',
  `day_count` int NOT NULL DEFAULT 1 COMMENT '行程天数',
  `night_count` int NULL DEFAULT 0 COMMENT '住宿晚数',
  `people_count` int NULL DEFAULT 2 COMMENT '出行人数',
  `budget_total` decimal(12,2) NULL COMMENT '预算总额（元）',
  `budget_level` varchar(16) NULL COMMENT '预算档次：经济 / 舒适 / 高端',
  `style_code` varchar(32) NOT NULL DEFAULT 'COMMON' COMMENT '行程风格编码，关联 t_trip_style',
  `transport_mode` varchar(32) NULL COMMENT '出行方式：飞机优先 / 高铁优先 / 自驾 等',
  `taboos` varchar(255) NULL COMMENT '禁忌与偏好，一经提出全程生效',
  `current_version_no` int NULL DEFAULT 0 COMMENT '当前生效版本号',
  `status` tinyint NULL DEFAULT 1 COMMENT '状态：1-草稿，2-已生成，3-已确认，4-已导出',
  `degrade_flag` tinyint NULL DEFAULT 0 COMMENT '是否含「信息待确认」降级标注：1-是，0-否（NFR-05）',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  UNIQUE KEY `AK_t_trip_no` (`trip_no`),
  KEY `idx_trip_user` (`user_id`),
  KEY `idx_trip_conv` (`conversation_id`),
  KEY `idx_trip_style` (`style_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='行程表：一次规划任务的行程主体，指向当前生效版本（FR-02 / FR-04）';

-- ---------------------------------------------------------------- t_trip_version  行程版本
CREATE TABLE `t_trip_version` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `trip_id` bigint NOT NULL COMMENT '所属行程ID',
  `version_no` int NOT NULL COMMENT '版本号，从 1 递增',
  `change_type` varchar(32) NOT NULL DEFAULT 'INIT' COMMENT '变更类型：INIT / CHAT_ADJUST / MANUAL_EDIT / AI_RERANK',
  `change_summary` varchar(512) NULL COMMENT '变更点说明',
  `base_version_id` bigint NULL COMMENT '派生自哪个版本，可空',
  `content_json` json NULL COMMENT '版本结构化快照，用于对比与回退',
  `total_cost` decimal(12,2) NULL COMMENT '该版本费用合计（元）',
  `current_flag` tinyint NULL DEFAULT 0 COMMENT '是否当前生效版本：1-是，0-否',
  `valid_flag` tinyint NULL DEFAULT 0 COMMENT '合理性校验是否通过：1-通过，0-未通过（NFR-04）',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  UNIQUE KEY `AK_trip_version` (`trip_id`, `version_no`),
  KEY `idx_version_trip_cur` (`trip_id`, `current_flag`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='行程版本表：每次生成 / 调整 / 编辑 / 重排产生一个可回溯版本（FR-04）';

-- ---------------------------------------------------------------- t_trip_day  行程日
CREATE TABLE `t_trip_day` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `trip_version_id` bigint NOT NULL COMMENT '所属行程版本ID',
  `day_index` int NOT NULL COMMENT '第几天，从 1 开始',
  `day_date` date NULL COMMENT '该天对应日期',
  `city` varchar(64) NULL COMMENT '当日所在城市',
  `theme` varchar(128) NULL COMMENT '当日主题，如「古城漫步」',
  `pace` varchar(16) NULL COMMENT '节奏：宽松 / 适中 / 紧凑',
  `remark` varchar(512) NULL COMMENT '备注与提醒',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  UNIQUE KEY `AK_version_day` (`trip_version_id`, `day_index`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='行程日表：版本内按天组织的日程（FR-02）';

-- ---------------------------------------------------------------- t_trip_item  行程条目
CREATE TABLE `t_trip_item` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `trip_day_id` bigint NOT NULL COMMENT '所属行程日ID',
  `period` varchar(16) NOT NULL COMMENT '时段：MORNING / AFTERNOON / EVENING / MEAL',
  `item_type` varchar(16) NOT NULL DEFAULT 'POI' COMMENT '条目类型：POI / RESTAURANT / HOTEL / TRANSPORT / FREE',
  `ref_id` bigint NULL COMMENT '关联 t_poi / t_restaurant / t_hotel 的主键（多态，不建外键）',
  `ref_name` varchar(128) NULL COMMENT '资源名称冗余，便于导出渲染',
  `start_time` time NULL COMMENT '计划开始时间',
  `end_time` time NULL COMMENT '计划结束时间',
  `duration_min` int NULL COMMENT '停留时长（分钟）',
  `seq` int NOT NULL DEFAULT 1 COMMENT '当日排序号',
  `distance_km` decimal(8,2) NULL COMMENT '距上一点距离（公里）',
  `travel_min` int NULL COMMENT '与上一点之间的车程（分钟）',
  `ticket_price` decimal(10,2) NULL COMMENT '门票价格（元）',
  `booking_required` tinyint NULL DEFAULT 0 COMMENT '是否需预约：1-是，0-否',
  `booking_advance_days` int NULL COMMENT '需提前预约的天数',
  `degrade_flag` tinyint NULL DEFAULT 0 COMMENT '该条目是否降级为「信息待确认」：1-是，0-否（NFR-05）',
  `note` varchar(512) NULL COMMENT '注意事项',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  KEY `idx_item_day_seq` (`trip_day_id`, `seq`),
  KEY `idx_item_ref` (`item_type`, `ref_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='行程条目表：每日上午 / 下午 / 晚上 / 餐饮的时段安排（FR-02 / FR-04）';

-- ---------------------------------------------------------------- t_trip_lodging  行程住宿安排
CREATE TABLE `t_trip_lodging` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `trip_day_id` bigint NOT NULL COMMENT '所属行程日ID',
  `hotel_id` bigint NULL COMMENT '关联 t_hotel 主键，可空',
  `hotel_name` varchar(128) NULL COMMENT '住宿名称',
  `room_type` varchar(64) NULL COMMENT '房型',
  `check_in` date NULL COMMENT '入住日期',
  `check_out` date NULL COMMENT '离店日期',
  `nights` int NULL DEFAULT 1 COMMENT '住宿晚数',
  `price_per_night` decimal(10,2) NULL COMMENT '每晚房价（元）',
  `total_price` decimal(10,2) NULL COMMENT '住宿合计（元）',
  `distance_to_scenic` decimal(8,2) NULL COMMENT '距主要景区距离（公里）',
  `score` decimal(4,2) NULL COMMENT '评分',
  `degrade_flag` tinyint NULL DEFAULT 0 COMMENT '是否降级为「信息待确认」：1-是，0-否',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  KEY `idx_lodging_day` (`trip_day_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='行程住宿表：每日住宿安排与房态价格（FR-02 / FR-03）';

-- ---------------------------------------------------------------- t_trip_transport  行程交通安排
CREATE TABLE `t_trip_transport` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `trip_version_id` bigint NOT NULL COMMENT '所属行程版本ID',
  `leg_index` int NOT NULL DEFAULT 1 COMMENT '第几段交通',
  `transport_type` varchar(24) NOT NULL COMMENT '交通类型：FLIGHT / HIGHSPEED / TRAIN / CAR_RENTAL / TAXI / BUS',
  `option_id` bigint NULL COMMENT '关联 t_transport_option 主键，可空',
  `carrier` varchar(64) NULL COMMENT '航司 / 铁路局 / 租车公司',
  `trip_no` varchar(32) NULL COMMENT '航班号 / 车次号',
  `from_city` varchar(64) NULL COMMENT '出发城市',
  `to_city` varchar(64) NULL COMMENT '到达城市',
  `dep_station` varchar(128) NULL COMMENT '出发机场 / 车站',
  `arr_station` varchar(128) NULL COMMENT '到达机场 / 车站',
  `dep_time` datetime NULL COMMENT '出发时间',
  `arr_time` datetime NULL COMMENT '到达时间',
  `duration_min` int NULL COMMENT '历时（分钟）',
  `price` decimal(10,2) NULL COMMENT '票价（元）',
  `transfer_desc` varchar(255) NULL COMMENT '换乘说明',
  `degrade_flag` tinyint NULL DEFAULT 0 COMMENT '是否降级为「信息待确认」：1-是，0-否',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  KEY `idx_transport_version` (`trip_version_id`, `leg_index`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='行程交通表：版本内城际 / 市内交通衔接（FR-02 / FR-03）';

-- ---------------------------------------------------------------- t_trip_export  行程导出记录
CREATE TABLE `t_trip_export` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `export_no` varchar(32) NOT NULL COMMENT '业务导出编号',
  `trip_id` bigint NOT NULL COMMENT '所属行程ID',
  `trip_version_id` bigint NOT NULL COMMENT '导出所依据的行程版本ID（保证导出与版本一致）',
  `format` varchar(16) NOT NULL COMMENT '导出格式：PDF / LONG_IMAGE / WECHAT_ARTICLE',
  `file_url` varchar(512) NULL COMMENT '导出文件地址',
  `file_size` bigint NULL COMMENT '文件大小（字节）',
  `page_count` int NULL COMMENT '页数',
  `degrade_notice_count` int NULL DEFAULT 0 COMMENT '行程单中「待确认」字段数量，用于汇总提示',
  `status` tinyint NULL DEFAULT 1 COMMENT '状态：1-生成中，2-成功，3-失败',
  `fail_reason` varchar(255) NULL COMMENT '失败原因',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  UNIQUE KEY `AK_t_trip_export_no` (`export_no`),
  KEY `idx_export_trip` (`trip_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='行程导出记录表：行程单导出与版本对应关系（FR-05）';

-- ---------------------------------------------------------------- t_poi  景点
CREATE TABLE `t_poi` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `poi_code` varchar(64) NOT NULL COMMENT '外部服务景点唯一编码',
  `name` varchar(128) NOT NULL COMMENT '景点名称',
  `city` varchar(64) NULL COMMENT '所在城市',
  `address` varchar(255) NULL COMMENT '详细地址',
  `longitude` decimal(10,6) NULL COMMENT '经度',
  `latitude` decimal(10,6) NULL COMMENT '纬度',
  `category` varchar(32) NULL COMMENT '景点类型：自然 / 人文 / 街区 等',
  `ticket_price` decimal(10,2) NULL COMMENT '门票价格（元）',
  `open_time_desc` varchar(64) NULL COMMENT '开放时间说明',
  `open_time_start` time NULL COMMENT '开放开始时间',
  `open_time_end` time NULL COMMENT '开放结束时间',
  `booking_required` tinyint NULL DEFAULT 0 COMMENT '是否需预约：1-是，0-否',
  `booking_channel` varchar(128) NULL COMMENT '预约方式与渠道',
  `booking_advance_days` int NULL COMMENT '需提前预约天数',
  `suggest_duration_min` int NULL COMMENT '建议游玩时长（分钟）',
  `queue_minutes` int NULL COMMENT '排队时长（分钟）',
  `sunrise_time` time NULL COMMENT '日出时间，供摄影风格排期',
  `sunset_time` time NULL COMMENT '日落时间，供摄影风格排期',
  `rating` decimal(4,2) NULL COMMENT '评分',
  `data_source` varchar(32) NULL COMMENT '数据来源标识（NFR-03）',
  `query_time` datetime NULL COMMENT '实时查询时间戳（NFR-03）',
  `degrade_flag` tinyint NULL DEFAULT 0 COMMENT '是否降级为「信息待确认」：1-是，0-否',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  UNIQUE KEY `AK_t_poi_code` (`poi_code`),
  KEY `idx_poi_city_cate` (`city`, `category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='景点表：景点门票、开放时间、预约要求等实时信息（FR-03 / UC-03）';

-- ---------------------------------------------------------------- t_hotel  住宿资源
CREATE TABLE `t_hotel` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `hotel_code` varchar(64) NOT NULL COMMENT '外部服务住宿唯一编码',
  `name` varchar(128) NOT NULL COMMENT '住宿名称',
  `city` varchar(64) NULL COMMENT '所在城市',
  `address` varchar(255) NULL COMMENT '详细地址',
  `longitude` decimal(10,6) NULL COMMENT '经度',
  `latitude` decimal(10,6) NULL COMMENT '纬度',
  `hotel_type` varchar(24) NULL DEFAULT 'HOTEL' COMMENT '住宿类型：HOTEL / HOMESTAY',
  `star` tinyint NULL COMMENT '星级：1-5',
  `score` decimal(4,2) NULL COMMENT '评分',
  `price_min` decimal(10,2) NULL COMMENT '最低房价（元 / 晚）',
  `price_max` decimal(10,2) NULL COMMENT '最高房价（元 / 晚）',
  `room_type` varchar(64) NULL COMMENT '房型',
  `available_rooms` int NULL COMMENT '指定日期可订房量',
  `query_date` date NULL COMMENT '房态对应的查询日期',
  `data_source` varchar(32) NULL COMMENT '数据来源标识（NFR-03）',
  `query_time` datetime NULL COMMENT '实时查询时间戳（NFR-03）',
  `degrade_flag` tinyint NULL DEFAULT 0 COMMENT '是否降级为「信息待确认」：1-是，0-否',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  UNIQUE KEY `AK_t_hotel_code` (`hotel_code`),
  KEY `idx_hotel_city` (`city`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='住宿资源表：酒店 / 民宿的位置、价格、评分与指定日期空房（FR-03）';

-- ---------------------------------------------------------------- t_transport_option  交通班次
CREATE TABLE `t_transport_option` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `option_code` varchar(64) NOT NULL COMMENT '外部服务班次唯一编码',
  `transport_type` varchar(24) NOT NULL COMMENT '交通类型：FLIGHT / HIGHSPEED / TRAIN / CAR_RENTAL / TAXI / BUS',
  `carrier` varchar(64) NULL COMMENT '航司 / 铁路局 / 租车公司',
  `trip_no` varchar(32) NULL COMMENT '航班号 / 车次号',
  `dep_city` varchar(64) NULL COMMENT '出发城市',
  `arr_city` varchar(64) NULL COMMENT '到达城市',
  `dep_station` varchar(128) NULL COMMENT '出发站',
  `arr_station` varchar(128) NULL COMMENT '到达站',
  `dep_time` datetime NULL COMMENT '出发时间',
  `arr_time` datetime NULL COMMENT '到达时间',
  `duration_min` int NULL COMMENT '历时（分钟）',
  `price` decimal(10,2) NULL COMMENT '票价（元）',
  `seat_left` int NULL COMMENT '余票 / 余座数量',
  `transfer_desc` varchar(255) NULL COMMENT '换乘说明',
  `query_date` date NULL COMMENT '班次对应的查询日期',
  `data_source` varchar(32) NULL COMMENT '数据来源标识（NFR-03）',
  `query_time` datetime NULL COMMENT '实时查询时间戳（NFR-03）',
  `degrade_flag` tinyint NULL DEFAULT 0 COMMENT '是否降级为「信息待确认」：1-是，0-否',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  UNIQUE KEY `AK_t_transport_option_code` (`option_code`),
  KEY `idx_option_city_time` (`dep_city`, `arr_city`, `dep_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='交通班次表：航班 / 高铁 / 火车 / 租车 / 打车 / 公交 实时班次（FR-03）';

-- ---------------------------------------------------------------- t_weather  天气
CREATE TABLE `t_weather` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `city` varchar(64) NOT NULL COMMENT '城市',
  `forecast_date` date NOT NULL COMMENT '预报日期',
  `weather_text` varchar(64) NULL COMMENT '天气现象：晴 / 小雨 等',
  `temp_min` decimal(5,1) NULL COMMENT '最低气温（摄氏度）',
  `temp_max` decimal(5,1) NULL COMMENT '最高气温（摄氏度）',
  `wind` varchar(64) NULL COMMENT '风力风向',
  `humidity` tinyint NULL COMMENT '相对湿度（百分比）',
  `precipitation` decimal(5,1) NULL COMMENT '降水量（毫米）',
  `dressing_tip` varchar(255) NULL COMMENT '穿衣建议',
  `data_source` varchar(32) NULL COMMENT '数据来源标识（NFR-03）',
  `query_time` datetime NULL COMMENT '实时查询时间戳（NFR-03）',
  `degrade_flag` tinyint NULL DEFAULT 0 COMMENT '是否降级为「信息待确认」：1-是，0-否',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  UNIQUE KEY `AK_weather_city_date` (`city`, `forecast_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='天气表：出行期间逐日天气预报与穿衣建议（FR-03）';

-- ---------------------------------------------------------------- t_restaurant  美食
CREATE TABLE `t_restaurant` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `restaurant_code` varchar(64) NOT NULL COMMENT '外部服务餐厅唯一编码',
  `name` varchar(128) NOT NULL COMMENT '餐厅名称',
  `city` varchar(64) NULL COMMENT '所在城市',
  `address` varchar(255) NULL COMMENT '详细地址',
  `longitude` decimal(10,6) NULL COMMENT '经度',
  `latitude` decimal(10,6) NULL COMMENT '纬度',
  `category` varchar(32) NULL COMMENT '餐饮类别：小吃 / 老字号 / 火锅 等',
  `avg_price` decimal(10,2) NULL COMMENT '人均消费（元）',
  `score` decimal(4,2) NULL COMMENT '评分',
  `signature_dish` varchar(255) NULL COMMENT '招牌菜',
  `open_time_desc` varchar(64) NULL COMMENT '营业时间说明',
  `local_must_flag` tinyint NULL DEFAULT 0 COMMENT '是否本地必吃：1-是，0-否',
  `data_source` varchar(32) NULL COMMENT '数据来源标识（NFR-03）',
  `query_time` datetime NULL COMMENT '实时查询时间戳（NFR-03）',
  `degrade_flag` tinyint NULL DEFAULT 0 COMMENT '是否降级为「信息待确认」：1-是，0-否',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  UNIQUE KEY `AK_t_restaurant_code` (`restaurant_code`),
  KEY `idx_rest_city` (`city`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='美食表：本地必吃、餐厅推荐、人均消费与位置（FR-03）';

-- ---------------------------------------------------------------- t_tool_call_log  工具调用日志
CREATE TABLE `t_tool_call_log` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `call_id` varchar(64) NOT NULL COMMENT '单次工具调用唯一ID，生成链路凭此溯源（NFR-03）',
  `trace_id` varchar(64) NULL COMMENT '一次生成任务的链路追踪ID',
  `conversation_id` bigint NULL COMMENT '所属会话ID',
  `trip_id` bigint NULL COMMENT '所属行程ID',
  `tool_type` varchar(24) NOT NULL COMMENT '工具类型：POI / TRANSPORT / HOTEL / WEATHER / FOOD',
  `request_params` json NULL COMMENT '调用入参快照',
  `response_summary` varchar(512) NULL COMMENT '返回结果摘要',
  `result_count` int NULL COMMENT '返回结果条数',
  `status` varchar(16) NULL DEFAULT 'SUCCESS' COMMENT '状态：SUCCESS / FAIL / TIMEOUT（NFR-08 单工具超时 ≤ 5 秒）',
  `degrade_flag` tinyint NULL DEFAULT 0 COMMENT '是否触发降级：1-是，0-否',
  `cost_ms` int NULL COMMENT '调用耗时（毫秒）',
  `error_code` varchar(64) NULL COMMENT '错误码',
  `error_msg` varchar(512) NULL COMMENT '错误信息',
  `called_at` datetime NULL COMMENT '调用发生时间',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  UNIQUE KEY `AK_t_tool_call_log_call_id` (`call_id`),
  KEY `idx_tool_trace` (`trace_id`),
  KEY `idx_tool_type_time` (`tool_type`, `called_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='工具调用日志表：记录每次工具调用的明细、耗时与降级事件（NFR-03 / NFR-08 / NFR-10）';

-- ---------------------------------------------------------------- t_travel_tips  旅行锦囊知识
CREATE TABLE `t_travel_tips` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `tips_code` varchar(64) NOT NULL COMMENT '锦囊知识唯一编码',
  `title` varchar(255) NOT NULL COMMENT '标题',
  `city` varchar(64) NULL COMMENT '适用城市，为空表示通用',
  `category` varchar(32) NULL COMMENT '类别：签证 / 交通 / 安全 / 习俗 / 避坑 / 预约',
  `content` mediumtext NULL COMMENT '知识正文',
  `tags` varchar(255) NULL COMMENT '标签，逗号分隔，用于检索',
  `source` varchar(128) NULL COMMENT '来源',
  `status` tinyint NULL DEFAULT 1 COMMENT '状态：1-启用，0-停用',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  UNIQUE KEY `AK_t_travel_tips_code` (`tips_code`),
  KEY `idx_tips_city_cate` (`city`, `category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='旅行锦囊知识表：避坑、签证、习俗等知识条目，支撑旅行咨询（数据与知识层）';

-- ---------------------------------------------------------------- t_trip_style  行程风格字典
CREATE TABLE `t_trip_style` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `style_code` varchar(32) NOT NULL COMMENT '风格编码：RELAX / COUPLE / FAMILY / KIDS / HIKE / PHOTO / FOOD / COMMON',
  `style_name` varchar(32) NOT NULL COMMENT '风格名称',
  `min_poi_per_day` int NULL DEFAULT 1 COMMENT '每日最少点位数',
  `max_poi_per_day` int NULL DEFAULT 2 COMMENT '每日最多点位数',
  `pace` varchar(16) NULL DEFAULT '宽松' COMMENT '节奏：宽松 / 紧凑',
  `poi_weight` varchar(255) NULL COMMENT '点位类型偏好权重，如「景观:3,街区:2,咖啡馆:1」',
  `drive_limit_km` decimal(8,2) NULL COMMENT '单日车程上限（公里）',
  `nap_required` tinyint NULL DEFAULT 0 COMMENT '是否安排午休：1-是，0-否（亲子风格）',
  `description` varchar(255) NULL COMMENT '风格说明',
  `status` tinyint NULL DEFAULT 1 COMMENT '状态：1-启用，0-停用',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  UNIQUE KEY `AK_t_trip_style_code` (`style_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='行程风格字典表：七类风格的排期参数，驱动行程引擎（FR-02）';

-- ---------------------------------------------------------------- t_content_audit_log  内容安全审核日志
CREATE TABLE `t_content_audit_log` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `biz_type` varchar(32) NOT NULL COMMENT '业务类型：MESSAGE / EXPORT',
  `biz_id` bigint NULL COMMENT '对应业务主键ID',
  `conversation_id` bigint NULL COMMENT '所属会话ID',
  `content_digest` varchar(64) NULL COMMENT '内容哈希摘要，避免留存原文',
  `audit_result` varchar(16) NULL DEFAULT 'PASS' COMMENT '审核结论：PASS / REJECT / REVIEW',
  `risk_level` varchar(16) NULL COMMENT '风险等级：LOW / MID / HIGH',
  `risk_label` varchar(64) NULL COMMENT '风险标签，如「涉政」「广告」',
  `auditor` varchar(32) NULL DEFAULT 'MACHINE' COMMENT '审核方：MACHINE / MANUAL',
  `handle_action` varchar(64) NULL COMMENT '处置动作：拦截 / 放行 / 留痕',
  `audited_at` datetime NULL COMMENT '审核时间',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint NOT NULL DEFAULT 0 COMMENT '逻辑删除：0-未删除，1-已删除',
  PRIMARY KEY (`id`),
  KEY `idx_audit_biz` (`biz_type`, `biz_id`),
  KEY `idx_audit_result_time` (`audit_result`, `audited_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='内容安全审核日志表：生成内容过审与违规拦截留痕（NFR-09）';

-- ---------------------------------------------------------------- 外键约束
-- 会话属于游客
ALTER TABLE `t_conversation` ADD CONSTRAINT `FK_t_conversation_t_user` FOREIGN KEY (`user_id`) REFERENCES `t_user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;
-- 消息属于会话
ALTER TABLE `t_message` ADD CONSTRAINT `FK_t_message_t_conversation` FOREIGN KEY (`conversation_id`) REFERENCES `t_conversation` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;
-- 槽位属于会话
ALTER TABLE `t_requirement_slot` ADD CONSTRAINT `FK_t_requirement_slot_t_conversation` FOREIGN KEY (`conversation_id`) REFERENCES `t_conversation` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;
-- 槽位归属行程
ALTER TABLE `t_requirement_slot` ADD CONSTRAINT `FK_t_requirement_slot_t_trip` FOREIGN KEY (`trip_id`) REFERENCES `t_trip` (`id`) ON DELETE SET NULL ON UPDATE CASCADE;
-- 行程属于游客
ALTER TABLE `t_trip` ADD CONSTRAINT `FK_t_trip_t_user` FOREIGN KEY (`user_id`) REFERENCES `t_user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;
-- 行程来源会话
ALTER TABLE `t_trip` ADD CONSTRAINT `FK_t_trip_t_conversation` FOREIGN KEY (`conversation_id`) REFERENCES `t_conversation` (`id`) ON DELETE SET NULL ON UPDATE CASCADE;
-- 行程采用某风格参数
ALTER TABLE `t_trip` ADD CONSTRAINT `FK_t_trip_t_trip_style` FOREIGN KEY (`style_code`) REFERENCES `t_trip_style` (`style_code`) ON DELETE CASCADE ON UPDATE CASCADE;
-- 版本属于行程
ALTER TABLE `t_trip_version` ADD CONSTRAINT `FK_t_trip_version_t_trip` FOREIGN KEY (`trip_id`) REFERENCES `t_trip` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;
-- 版本派生自基线版本
ALTER TABLE `t_trip_version` ADD CONSTRAINT `FK_t_trip_version_base` FOREIGN KEY (`base_version_id`) REFERENCES `t_trip_version` (`id`) ON DELETE SET NULL ON UPDATE CASCADE;
-- 日程属于版本
ALTER TABLE `t_trip_day` ADD CONSTRAINT `FK_t_trip_day_t_trip_version` FOREIGN KEY (`trip_version_id`) REFERENCES `t_trip_version` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;
-- 条目属于日程
ALTER TABLE `t_trip_item` ADD CONSTRAINT `FK_t_trip_item_t_trip_day` FOREIGN KEY (`trip_day_id`) REFERENCES `t_trip_day` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;
-- 住宿属于日程
ALTER TABLE `t_trip_lodging` ADD CONSTRAINT `FK_t_trip_lodging_t_trip_day` FOREIGN KEY (`trip_day_id`) REFERENCES `t_trip_day` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;
-- 住宿引用住宿资源
ALTER TABLE `t_trip_lodging` ADD CONSTRAINT `FK_t_trip_lodging_t_hotel` FOREIGN KEY (`hotel_id`) REFERENCES `t_hotel` (`id`) ON DELETE SET NULL ON UPDATE CASCADE;
-- 交通属于版本
ALTER TABLE `t_trip_transport` ADD CONSTRAINT `FK_t_trip_transport_t_trip_version` FOREIGN KEY (`trip_version_id`) REFERENCES `t_trip_version` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;
-- 交通引用班次资源
ALTER TABLE `t_trip_transport` ADD CONSTRAINT `FK_t_trip_transport_t_option` FOREIGN KEY (`option_id`) REFERENCES `t_transport_option` (`id`) ON DELETE SET NULL ON UPDATE CASCADE;
-- 导出属于行程
ALTER TABLE `t_trip_export` ADD CONSTRAINT `FK_t_trip_export_t_trip` FOREIGN KEY (`trip_id`) REFERENCES `t_trip` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;
-- 导出对应版本
ALTER TABLE `t_trip_export` ADD CONSTRAINT `FK_t_trip_export_t_trip_version` FOREIGN KEY (`trip_version_id`) REFERENCES `t_trip_version` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;

SET FOREIGN_KEY_CHECKS = 1;

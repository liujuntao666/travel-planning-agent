-- ============================================================================
-- 旅游规划智能体系统  初始化数据脚本
-- 内容：行程风格字典 + 旅行锦囊知识 + 一条完整行程闭环演示数据
-- 说明：演示数据与 01_schema.sql 的表结构、外键关系一一对应，
--       覆盖 游客 → 会话 → 需求槽位 → 行程 → 版本 → 日程 → 条目/住宿/交通
--       → 导出记录 → 工具调用日志 → 内容审核日志 的完整持久化链路。
-- 生成方式：由 data-model/schema_model.py 自动生成，请勿手工修改
-- ============================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- 行程风格字典（FR-02：七类预设风格参数）
INSERT INTO `t_trip_style` (`style_code`, `style_name`, `min_poi_per_day`, `max_poi_per_day`, `pace`, `poi_weight`, `drive_limit_km`, `nap_required`, `description`, `status`) VALUES
  ('COMMON', '均衡', 1, 2, '适中', '景观:2,街区:2,博物馆:1', 120.0, 0, '默认风格，兼顾观景与体验', 1),
  ('RELAX', '休闲', 1, 2, '宽松', '景观:3,街区:2,咖啡馆:1', 100.0, 0, '每日 1～2 个主点位，节奏宽松', 1),
  ('COUPLE', '情侣', 1, 2, '宽松', '景观:3,街区:2,咖啡馆:2', 100.0, 0, '偏好景观、街区与咖啡馆', 1),
  ('FAMILY', '家庭', 2, 2, '宽松', '亲子乐园:3,动植物园:2,博物馆:2', 90.0, 1, '含午休，点位集中', 1),
  ('KIDS', '亲子', 2, 2, '宽松', '亲子乐园:3,动植物园:2,博物馆:2', 90.0, 1, '亲子友好，安排午休', 1),
  ('HIKE', '徒步', 1, 3, '紧凑', '自然线路:3,山野:2', 150.0, 0, '自然线路优先，节奏紧凑', 1),
  ('PHOTO', '摄影', 1, 3, '紧凑', '日出日落机位:3,景观:2', 150.0, 0, '围绕日出日落机位排期', 1),
  ('FOOD', '美食', 2, 2, '随餐安排', '市集:3,老字号:2,小吃街:2', 80.0, 0, '围绕市集、老字号与小吃街', 1);

-- 旅行锦囊知识库（数据与知识层）
INSERT INTO `t_travel_tips` (`tips_code`, `title`, `city`, `category`, `content`, `tags`, `source`, `status`) VALUES
  ('TIP-YN-001', '玉龙雪山索道需提前实名预约', '丽江', '预约', '大索道每日限量，需提前 1～3 天在官方渠道实名预约，现场不保证有余票；旺季建议提前 3 天。', '丽江,玉龙雪山,预约,索道', '官方公告', 1),
  ('TIP-YN-002', '高原反应预防要点', '丽江', '安全', '海拔 2400 米以上可能出现轻微高反，抵达首日避免剧烈运动与洗澡受凉，可备便携氧气瓶。', '高原,安全,丽江', '旅行锦囊', 1),
  ('TIP-YN-003', '洱海环湖交通建议', '大理', '交通', '环洱海约 130 公里，电动车适合分段骑行，自驾注意部分路段限速与停车管控。', '大理,洱海,交通,自驾', '旅行锦囊', 1),
  ('TIP-YN-004', '古城维护费与门票政策', '丽江', '避坑', '丽江古城维护费按政策执行，部分景点联票更划算，避免在非官方渠道购买低价票。', '丽江,门票,避坑', '官方公告', 1),
  ('TIP-YN-005', '雨季出行装备提醒', '云南', '安全', '6～9 月为雨季，山区易起雾，建议携带防滑鞋与雨具，山区道路谨慎驾驶。', '雨季,安全,装备', '旅行锦囊', 1),
  ('TIP-YN-006', '少数民族地区习俗提醒', '云南', '习俗', '进入村寨请尊重当地习俗，拍摄人物前先征得同意，寺庙内注意着装与安静。', '习俗,礼仪', '旅行锦囊', 1),
  ('TIP-YN-007', '当地饮食禁忌与特色', '云南', '避坑', '部分菜品偏辣偏酸，忌辣游客点单时主动说明；野生菌需在正规餐馆食用。', '美食,避坑,饮食', '旅行锦囊', 1),
  ('TIP-GEN-001', '证件与保险准备', NULL, '签证', '身份证、驾照、学生证等随身携带；高原、徒步类行程建议购买含意外医疗的旅行保险。', '通用,证件,保险', '旅行锦囊', 1),
  ('TIP-GEN-002', '旺季错峰与订房技巧', NULL, '避坑', '法定节假日与寒暑假为旺季，房价与票价上浮明显，建议提前 2～4 周预订可免费取消的房型。', '通用,旺季,订房', '旅行锦囊', 1),
  ('TIP-GEN-003', '天气突变应对', NULL, '安全', '出行前 3 天复查天气，遇台风、暴雨预警及时调整行程，景区封闭时以官方通知为准。', '通用,天气,安全', '旅行锦囊', 1);

-- 演示：游客用户
INSERT INTO `t_user` (`id`, `open_id`, `nickname`, `avatar_url`, `phone`, `gender`, `source`, `status`, `last_login_at`) VALUES
  (1, 'wx_openid_demo_0001', '小旅', 'https://cdn.example.com/avatar/0001.png', '13800000001', 1, 'MINI', 1, '2026-10-15 09:00:00');

-- 演示：会话（承载多轮上下文）
INSERT INTO `t_conversation` (`id`, `user_id`, `title`, `last_intent`, `status`, `current_trip_id`, `message_count`, `last_message_at`) VALUES
  (1, 1, '成都出发 云南 5 天 4 晚', 'NEW_PLAN', 1, 1, 4, '2026-10-15 09:02:30');

-- 演示：会话消息（流式输出 + 耗时记录）
INSERT INTO `t_message` (`id`, `conversation_id`, `seq`, `role`, `content`, `content_type`, `intent`, `stream_flag`, `token_count`, `latency_ms`) VALUES
  (1, 1, 1, 'USER', '成都出发，去云南 5 天 4 晚，两个人，预算 8000，休闲不累。', 'TEXT', 'NEW_PLAN', 0, 0, 0),
  (2, 1, 2, 'ASSISTANT', '已识别需求要素：出发地成都、目的地云南、5 天 4 晚、2 人、预算 8000 元、风格休闲。正在并行查询景点、交通、住宿、天气与美食实时信息。', 'MARKDOWN', 'NEW_PLAN', 1, 412, 2680),
  (3, 1, 3, 'ASSISTANT', '行程已生成：大理 2 天 + 丽江 3 天，含往返高铁、住宿与每日餐饮，合计约 7620 元，在预算内。', 'MARKDOWN', 'NEW_PLAN', 1, 1860, 11800),
  (4, 1, 4, 'USER', '住得离景区近一点。', 'TEXT', 'ADJUST', 0, 0, 0);

-- 演示：需求要素槽位（八类要素抽取结果，NFR-01 置信度）
INSERT INTO `t_requirement_slot` (`id`, `conversation_id`, `trip_id`, `slot_key`, `slot_value`, `value_type`, `required_flag`, `filled_flag`, `ask_count`, `confidence`, `slot_source`) VALUES
  (1, 1, 1, 'ORIGIN', '成都', 'TEXT', 1, 1, 0, 0.982, 'EXTRACT'),
  (2, 1, 1, 'DEST', '云南（大理 / 丽江）', 'LIST', 1, 1, 0, 0.965, 'EXTRACT'),
  (3, 1, 1, 'NIGHTS', '5 天 4 晚', 'TEXT', 1, 1, 0, 0.99, 'EXTRACT'),
  (4, 1, 1, 'PEOPLE', '2', 'NUMBER', 0, 1, 0, 0.97, 'EXTRACT'),
  (5, 1, 1, 'BUDGET', '8000', 'NUMBER', 0, 1, 0, 0.95, 'EXTRACT'),
  (6, 1, 1, 'STYLE', '休闲', 'TEXT', 0, 1, 0, 0.94, 'EXTRACT'),
  (7, 1, 1, 'TRANSPORT', '高铁优先', 'TEXT', 0, 1, 1, 0.78, 'DEFAULT'),
  (8, 1, 1, 'TABOO', '不吃辣', 'LIST', 0, 1, 1, 0.91, 'EXTRACT');

-- 演示：行程主体
INSERT INTO `t_trip` (`id`, `trip_no`, `user_id`, `conversation_id`, `title`, `origin_city`, `dest_cities`, `day_count`, `night_count`, `people_count`, `budget_total`, `budget_level`, `style_code`, `transport_mode`, `taboos`, `current_version_no`, `status`, `degrade_flag`) VALUES
  (1, 'TRIP202610150001', 1, 1, '成都出发 云南 5 天 4 晚休闲行', '成都', '大理 / 丽江', 5, 4, 2, 8000.0, '舒适', 'RELAX', '高铁优先', '不吃辣', 1, 2, 0);

-- 演示：行程版本（初始版本 v1，可回溯）
INSERT INTO `t_trip_version` (`id`, `trip_id`, `version_no`, `change_type`, `change_summary`, `base_version_id`, `total_cost`, `current_flag`, `valid_flag`) VALUES
  (1, 1, 1, 'INIT', '首次生成：大理 2 天 + 丽江 3 天', NULL, 7620.0, 1, 1);

-- 演示：行程日（按天组织）
INSERT INTO `t_trip_day` (`id`, `trip_version_id`, `day_index`, `day_date`, `city`, `theme`, `pace`, `remark`) VALUES
  (1, 1, 1, '2026-10-20', '大理', '抵达与古城漫步', '宽松', '抵达后先办理入住，避免剧烈活动'),
  (2, 1, 2, '2026-10-21', '大理', '洱海环湖', '宽松', '环湖分段游览，注意防晒'),
  (3, 1, 3, '2026-10-22', '丽江', '古城与束河', '宽松', '上午动车转场'),
  (4, 1, 4, '2026-10-23', '丽江', '玉龙雪山', '紧凑', '需提前预约大索道'),
  (5, 1, 5, '2026-10-24', '丽江', '返程', '宽松', '预留 2 小时到站时间');

-- 演示：行程条目（上午 / 下午 / 晚上 / 餐饮时段安排）
INSERT INTO `t_trip_item` (`id`, `trip_day_id`, `period`, `item_type`, `ref_id`, `ref_name`, `start_time`, `end_time`, `duration_min`, `seq`, `distance_km`, `travel_min`, `ticket_price`, `booking_required`, `booking_advance_days`, `degrade_flag`, `note`) VALUES
  (1, 1, 'AFTERNOON', 'POI', 1, '大理古城', '14:00:00', '17:30:00', 210, 1, NULL, NULL, 0.0, 0, NULL, 0, '古城内步行为主'),
  (2, 1, 'MEAL', 'RESTAURANT', 1, '大理白族风味馆', '18:00:00', '19:30:00', 90, 2, 1.2, 6, 68.0, 0, NULL, 0, '人均约 68 元'),
  (3, 2, 'MORNING', 'POI', 2, '洱海生态廊道', '09:00:00', '12:00:00', 180, 1, NULL, NULL, 0.0, 0, NULL, 0, '建议骑行分段'),
  (4, 2, 'AFTERNOON', 'POI', 3, '喜洲古镇', '14:00:00', '17:00:00', 180, 2, 18.6, 35, 0.0, 0, NULL, 0, '可尝喜洲粑粑'),
  (5, 2, 'MEAL', 'RESTAURANT', 2, '喜洲小吃街', '17:30:00', '19:00:00', 90, 3, 0.8, 5, 45.0, 0, NULL, 0, '人均约 45 元'),
  (6, 3, 'MORNING', 'TRANSPORT', NULL, '大理站 → 丽江站', '09:12:00', '11:05:00', 113, 1, NULL, NULL, 136.0, 1, 1, 0, '动车 D 字头'),
  (7, 3, 'AFTERNOON', 'POI', 4, '丽江古城', '14:30:00', '18:00:00', 210, 2, 2.4, 12, 0.0, 0, NULL, 0, '古城维护费按政策执行'),
  (8, 4, 'MORNING', 'POI', 5, '玉龙雪山', '08:00:00', '13:00:00', 300, 1, NULL, NULL, 240.0, 1, 3, 0, '含大索道，需实名预约'),
  (9, 4, 'MEAL', 'RESTAURANT', 3, '丽江腊排骨火锅', '18:30:00', '20:00:00', 90, 2, 12.3, 25, 88.0, 0, NULL, 0, '忌辣请提前说明'),
  (10, 5, 'MORNING', 'TRANSPORT', NULL, '丽江站 → 成都南站', '09:40:00', '17:20:00', 460, 1, NULL, NULL, 512.0, 1, 1, 0, '高铁 G 字头');

-- 演示：行程住宿安排
INSERT INTO `t_trip_lodging` (`id`, `trip_day_id`, `hotel_id`, `hotel_name`, `room_type`, `check_in`, `check_out`, `nights`, `price_per_night`, `total_price`, `distance_to_scenic`, `score`, `degrade_flag`) VALUES
  (1, 1, 1, '大理古城观景民宿', '观景大床房', '2026-10-20', '2026-10-22', 2, 420.0, 840.0, 1.5, 4.72, 0),
  (2, 2, 2, '洱海海景酒店', '海景双床房', '2026-10-21', '2026-10-22', 1, 560.0, 560.0, 0.8, 4.68, 0),
  (3, 3, 3, '丽江古城客栈', '庭院大床房', '2026-10-22', '2026-10-24', 2, 380.0, 760.0, 0.6, 4.75, 0),
  (4, 4, 3, '丽江古城客栈', '庭院大床房', '2026-10-23', '2026-10-24', 1, 380.0, 380.0, 0.6, 4.75, 0);

-- 演示：行程交通衔接
INSERT INTO `t_trip_transport` (`id`, `trip_version_id`, `leg_index`, `transport_type`, `option_id`, `carrier`, `trip_no`, `from_city`, `to_city`, `dep_station`, `arr_station`, `dep_time`, `arr_time`, `duration_min`, `price`, `transfer_desc`, `degrade_flag`) VALUES
  (1, 1, 1, 'HIGHSPEED', 1, '中国铁路', 'G2836', '成都', '大理', '成都南站', '大理站', '2026-10-20 07:30:00', '2026-10-20 13:05:00', 335, 462.0, '直达', 0),
  (2, 1, 2, 'HIGHSPEED', 2, '中国铁路', 'D8788', '大理', '丽江', '大理站', '丽江站', '2026-10-22 09:12:00', '2026-10-22 11:05:00', 113, 136.0, '直达', 0),
  (3, 1, 3, 'HIGHSPEED', 3, '中国铁路', 'G2838', '丽江', '成都', '丽江站', '成都南站', '2026-10-24 09:40:00', '2026-10-24 17:20:00', 460, 512.0, '直达', 0);

-- 演示：行程单导出记录（导出与版本一一对应）
INSERT INTO `t_trip_export` (`id`, `export_no`, `trip_id`, `trip_version_id`, `format`, `file_url`, `file_size`, `page_count`, `degrade_notice_count`, `status`, `fail_reason`) VALUES
  (1, 'EXP202610150001', 1, 1, 'PDF', 'https://cdn.example.com/export/EXP202610150001.pdf', 524288, 6, 0, 2, NULL);

-- 演示：景点实时信息（含 query_time 时间戳，NFR-03）
INSERT INTO `t_poi` (`id`, `poi_code`, `name`, `city`, `address`, `longitude`, `latitude`, `category`, `ticket_price`, `open_time_desc`, `open_time_start`, `open_time_end`, `booking_required`, `booking_channel`, `booking_advance_days`, `suggest_duration_min`, `queue_minutes`, `sunrise_time`, `sunset_time`, `rating`, `data_source`, `query_time`, `degrade_flag`) VALUES
  (1, 'POI-DL-0001', '大理古城', '大理', '云南省大理白族自治州大理市古城', 100.164, 25.692, '人文', 0.0, '全天开放', '00:00:00', '23:59:59', 0, NULL, NULL, 210, 10, NULL, NULL, 4.62, 'TUNIU_OPEN_API', '2026-10-15 09:01:10', 0),
  (2, 'POI-DL-0002', '洱海生态廊道', '大理', '云南省大理白族自治州大理市环洱海', 100.19, 25.76, '自然', 0.0, '全天开放', '00:00:00', '23:59:59', 0, NULL, NULL, 180, 0, '06:50:00', '19:20:00', 4.7, 'TUNIU_OPEN_API', '2026-10-15 09:01:10', 0),
  (3, 'POI-DL-0003', '喜洲古镇', '大理', '云南省大理白族自治州大理市喜洲镇', 100.133, 25.856, '人文', 0.0, '08:00-18:00', '08:00:00', '18:00:00', 0, NULL, NULL, 180, 0, NULL, NULL, 4.55, 'TUNIU_OPEN_API', '2026-10-15 09:01:10', 0),
  (4, 'POI-LJ-0001', '丽江古城', '丽江', '云南省丽江市古城区', 100.234, 26.872, '人文', 0.0, '全天开放', '00:00:00', '23:59:59', 0, NULL, NULL, 210, 5, NULL, NULL, 4.66, 'TUNIU_OPEN_API', '2026-10-15 09:01:10', 0),
  (5, 'POI-LJ-0002', '玉龙雪山', '丽江', '云南省丽江市玉龙纳西族自治县', 100.186, 27.1, '自然', 240.0, '07:30-16:00', '07:30:00', '16:00:00', 1, '官方公众号实名预约', 3, 300, 45, '06:40:00', '19:30:00', 4.71, 'TUNIU_OPEN_API', '2026-10-15 09:01:10', 0);

-- 演示：住宿资源（含指定日期空房）
INSERT INTO `t_hotel` (`id`, `hotel_code`, `name`, `city`, `address`, `longitude`, `latitude`, `hotel_type`, `star`, `score`, `price_min`, `price_max`, `room_type`, `available_rooms`, `query_date`, `data_source`, `query_time`, `degrade_flag`) VALUES
  (1, 'HT-DL-0001', '大理古城观景民宿', '大理', '大理市古城人民路', 100.165, 25.693, 'HOMESTAY', 4, 4.72, 380.0, 460.0, '观景大床房', 6, '2026-10-20', 'CTRIP_HOTEL_API', '2026-10-15 09:01:14', 0),
  (2, 'HT-DL-0002', '洱海海景酒店', '大理', '大理市环海西路', 100.188, 25.758, 'HOTEL', 5, 4.68, 520.0, 680.0, '海景双床房', 3, '2026-10-21', 'CTRIP_HOTEL_API', '2026-10-15 09:01:14', 0),
  (3, 'HT-LJ-0001', '丽江古城客栈', '丽江', '丽江市古城区五一街', 100.233, 26.873, 'HOMESTAY', 4, 4.75, 320.0, 420.0, '庭院大床房', 9, '2026-10-22', 'CTRIP_HOTEL_API', '2026-10-15 09:01:14', 0);

-- 演示：交通班次（航班 / 高铁实时班次）
INSERT INTO `t_transport_option` (`id`, `option_code`, `transport_type`, `carrier`, `trip_no`, `dep_city`, `arr_city`, `dep_station`, `arr_station`, `dep_time`, `arr_time`, `duration_min`, `price`, `seat_left`, `transfer_desc`, `query_date`, `data_source`, `query_time`, `degrade_flag`) VALUES
  (1, 'OP-G2836-20261020', 'HIGHSPEED', '中国铁路', 'G2836', '成都', '大理', '成都南站', '大理站', '2026-10-20 07:30:00', '2026-10-20 13:05:00', 335, 462.0, 42, '直达', '2026-10-20', '12306_API', '2026-10-15 09:01:12', 0),
  (2, 'OP-D8788-20261022', 'HIGHSPEED', '中国铁路', 'D8788', '大理', '丽江', '大理站', '丽江站', '2026-10-22 09:12:00', '2026-10-22 11:05:00', 113, 136.0, 88, '直达', '2026-10-22', '12306_API', '2026-10-15 09:01:12', 0),
  (3, 'OP-G2838-20261024', 'HIGHSPEED', '中国铁路', 'G2838', '丽江', '成都', '丽江站', '成都南站', '2026-10-24 09:40:00', '2026-10-24 17:20:00', 460, 512.0, 21, '直达', '2026-10-24', '12306_API', '2026-10-15 09:01:12', 0);

-- 演示：逐日天气与穿衣建议
INSERT INTO `t_weather` (`id`, `city`, `forecast_date`, `weather_text`, `temp_min`, `temp_max`, `wind`, `humidity`, `precipitation`, `dressing_tip`, `data_source`, `query_time`, `degrade_flag`) VALUES
  (1, '大理', '2026-10-20', '晴', 12.0, 23.0, '西南风 2 级', 55, 0.0, '早晚温差大，建议薄外套', 'WEATHER_API', '2026-10-15 09:01:15', 0),
  (2, '大理', '2026-10-21', '多云', 13.0, 22.0, '西南风 3 级', 60, 0.0, '适合户外环湖', 'WEATHER_API', '2026-10-15 09:01:15', 0),
  (3, '丽江', '2026-10-22', '晴', 9.0, 21.0, '西风 2 级', 48, 0.0, '紫外线强，注意防晒', 'WEATHER_API', '2026-10-15 09:01:15', 0),
  (4, '丽江', '2026-10-23', '小雨', 8.0, 17.0, '东北风 3 级', 78, 3.2, '山上气温低，需防风外套', 'WEATHER_API', '2026-10-15 09:01:15', 0),
  (5, '丽江', '2026-10-24', '阴', 9.0, 19.0, '北风 2 级', 70, 0.5, '返程日注意保暖', 'WEATHER_API', '2026-10-15 09:01:15', 0);

-- 演示：美食与餐厅推荐
INSERT INTO `t_restaurant` (`id`, `restaurant_code`, `name`, `city`, `address`, `longitude`, `latitude`, `category`, `avg_price`, `score`, `signature_dish`, `open_time_desc`, `local_must_flag`, `data_source`, `query_time`, `degrade_flag`) VALUES
  (1, 'RS-DL-0001', '大理白族风味馆', '大理', '大理市古城复兴路', 100.166, 25.694, '老字号', 68.0, 4.63, '酸辣鱼 / 乳扇', '10:00-21:30', 1, 'MEITUAN_API', '2026-10-15 09:01:20', 0),
  (2, 'RS-DL-0002', '喜洲小吃街', '大理', '大理市喜洲镇', 100.132, 25.855, '小吃街', 45.0, 4.51, '喜洲粑粑 / 米线', '08:00-20:00', 1, 'MEITUAN_API', '2026-10-15 09:01:20', 0),
  (3, 'RS-LJ-0001', '丽江腊排骨火锅', '丽江', '丽江市古城区象山市场', 100.228, 26.879, '火锅', 88.0, 4.58, '腊排骨火锅', '11:00-22:00', 1, 'MEITUAN_API', '2026-10-15 09:01:20', 1),
  (4, 'RS-LJ-0002', '丽江古城小吃铺', '丽江', '丽江市古城区四方街', 100.235, 26.872, '小吃', 38.0, 4.4, '鸡豆凉粉 / 纳西烤鱼', '09:00-22:00', 0, 'MEITUAN_API', '2026-10-15 09:01:20', 1),
  (5, 'RS-LJ-0003', '束河纳西菜馆', '丽江', '丽江市束河古镇', 100.207, 26.911, '本地菜', 72.0, 4.55, '纳西烤肉', '10:30-21:00', 0, 'MEITUAN_API', '2026-10-15 09:01:20', 0);

-- 演示：工具调用日志（含 1 条 TIMEOUT 降级事件，NFR-08 / NFR-10）
INSERT INTO `t_tool_call_log` (`id`, `call_id`, `trace_id`, `conversation_id`, `trip_id`, `tool_type`, `request_params`, `response_summary`, `result_count`, `status`, `degrade_flag`, `cost_ms`, `error_code`, `error_msg`, `called_at`) VALUES
  (1, 'TC20261015POI0001', 'TRACE20261015000001', 1, 1, 'POI', '{"city":"大理","days":5}', '返回景点 12 条', 12, 'SUCCESS', 0, 860, NULL, NULL, '2026-10-15 09:01:10'),
  (2, 'TC20261015TRA0001', 'TRACE20261015000001', 1, 1, 'TRANSPORT', '{"from":"成都","to":"大理"}', '返回班次 8 条', 8, 'SUCCESS', 0, 1240, NULL, NULL, '2026-10-15 09:01:12'),
  (3, 'TC20261015HOT0001', 'TRACE20261015000001', 1, 1, 'HOTEL', '{"city":"大理","checkin":"2026-10-20"}', '返回住宿 15 条', 15, 'SUCCESS', 0, 1080, NULL, NULL, '2026-10-15 09:01:14'),
  (4, 'TC20261015WEA0001', 'TRACE20261015000001', 1, 1, 'WEATHER', '{"city":"丽江","days":5}', '返回逐日预报 5 条', 5, 'SUCCESS', 0, 420, NULL, NULL, '2026-10-15 09:01:15'),
  (5, 'TC20261015FOOD001', 'TRACE20261015000001', 1, 1, 'FOOD', '{"city":"丽江"}', '美食服务超时，降级为待确认', 0, 'TIMEOUT', 1, 5000, 'TIMEOUT_5000', '单工具超时 5 秒，已降级', '2026-10-15 09:01:20');

-- 演示：内容安全审核留痕（NFR-09）
INSERT INTO `t_content_audit_log` (`id`, `biz_type`, `biz_id`, `conversation_id`, `content_digest`, `audit_result`, `risk_level`, `risk_label`, `auditor`, `handle_action`, `audited_at`) VALUES
  (1, 'MESSAGE', 2, 1, '3f2a9c1d5e6b7a8f', 'PASS', 'LOW', NULL, 'MACHINE', '放行', '2026-10-15 09:01:25'),
  (2, 'EXPORT', 1, 1, '8b1c4d7e2f3a5b6c', 'PASS', 'LOW', NULL, 'MACHINE', '放行', '2026-10-15 09:05:00');

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================================
-- 文件上传 / 下载模块（分片上传、断点续传）
-- 说明：基础 20 张表由 01_schema.sql 创建，本脚本只追加文件模块的 3 张表
-- ============================================================================

SET NAMES utf8mb4;

DROP TABLE IF EXISTS `t_upload_chunk`;
DROP TABLE IF EXISTS `t_upload_session`;
DROP TABLE IF EXISTS `t_file`;

-- ---------------------------------------------------------------- t_file  已归档文件
CREATE TABLE `t_file` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `file_no` varchar(32) NOT NULL COMMENT '对外文件编号',
  `name` varchar(255) NOT NULL COMMENT '原始文件名',
  `storage_name` varchar(64) NOT NULL COMMENT '磁盘存储名',
  `size` bigint NOT NULL COMMENT '字节数',
  `content_hash` varchar(64) NOT NULL COMMENT '文件内容 SHA256',
  `fingerprint` varchar(64) NOT NULL COMMENT '分片指纹，用于秒传',
  `mime` varchar(128) NULL COMMENT 'MIME 类型',
  `owner_id` bigint NOT NULL COMMENT '所属用户ID',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` int NOT NULL DEFAULT 0 COMMENT '逻辑删除',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_file_no` (`file_no`),
  KEY `idx_file_owner` (`owner_id`),
  KEY `idx_file_fingerprint` (`fingerprint`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='文件元数据';

-- ---------------------------------------------------------------- t_upload_session  分片上传会话
CREATE TABLE `t_upload_session` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `upload_id` varchar(32) NOT NULL COMMENT '上传会话ID',
  `file_name` varchar(255) NOT NULL COMMENT '原始文件名',
  `file_size` bigint NOT NULL COMMENT '文件总字节数',
  `file_hash` varchar(64) NOT NULL COMMENT '分片指纹',
  `chunk_size` int NOT NULL COMMENT '分片大小',
  `total_chunks` int NOT NULL COMMENT '分片总数',
  `status` varchar(16) NOT NULL DEFAULT 'uploading' COMMENT 'uploading/merging/done',
  `owner_id` bigint NOT NULL COMMENT '上传用户ID',
  `file_id` bigint NULL COMMENT '合并后的文件ID',
  `content_hash` varchar(64) NULL COMMENT '合并后文件内容 SHA256',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` int NOT NULL DEFAULT 0 COMMENT '逻辑删除',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_upload_id` (`upload_id`),
  KEY `idx_upload_owner` (`owner_id`),
  KEY `idx_upload_fingerprint` (`file_hash`, `file_size`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='分片上传会话';

-- ---------------------------------------------------------------- t_upload_chunk  已上传分片
CREATE TABLE `t_upload_chunk` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `upload_id` varchar(32) NOT NULL COMMENT '上传会话ID',
  `idx` int NOT NULL COMMENT '分片序号，从 0 开始',
  `size` bigint NOT NULL COMMENT '分片字节数',
  `chunk_hash` varchar(64) NOT NULL COMMENT '分片 SHA256',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_chunk_upload_idx` (`upload_id`, `idx`),
  KEY `idx_chunk_upload` (`upload_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='已上传分片';

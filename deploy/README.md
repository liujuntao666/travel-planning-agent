# deploy

演示与开发环境一条命令起停：MySQL 8.0 + FastAPI 后端 + Vue 前端（Nginx）。

```bash
cp .env.example .env      # 按需填入 LLM_API_KEY
docker compose up -d --build
```

| 服务 | 地址 | 说明 |
|---|---|---|
| 前端 | http://localhost:8080 | 对话规划、行程编辑、版本对比、导出 |
| 后端 | http://localhost:8000/docs | OpenAPI 文档与在线调试 |
| 健康检查 | http://localhost:8000/health | 数据库与工具状态 |
| MySQL | localhost:3306 | 首次启动自动执行 `mysql/init` 下建表与种子数据 |

- `.env` 为本地真实配置，已被 .gitignore 排除，禁止提交
- 仅重建后端：`docker compose up -d --build backend`
- 查看日志：`docker compose logs -f backend`
- 停止并保留数据：`docker compose down`；清库重来：`docker compose down -v`
- 降级演练：在 `.env` 中设 `TOOL_OFFLINE=true` 后重启后端，行程会标注「信息待确认」

## 生产部署（HTTPS）

前置条件：服务器安装 Docker 与 compose 插件；安全组/防火墙只放行 22、80、443；两个域名（如 `app.example.com`、`admin.example.com`）的 A 记录已指向服务器。

```bash
git clone https://github.com/liujuntao666/travel-planning-agent.git
cd travel-planning-agent/deploy

cp .env.example .env
# 必改项：
#   AUTH_SECRET=$(openssl rand -hex 32)
#   MYSQL_ROOT_PASSWORD / MYSQL_PASSWORD 改为强密码
#   APP_DOMAIN=app.example.com  ADMIN_DOMAIN=admin.example.com
#   CORS_ORIGINS=https://app.example.com,https://admin.example.com
#   APP_ENV=prod
#   SEED_ADMIN_PASSWORD / SEED_DEMO_PASSWORD 改为强密码

rm docker-compose.override.yml   # 该文件只用于本机 8001 端口映射

docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

- 对外仅暴露 80/443，MySQL、Redis、后端、两个前端都不再发布宿主机端口
- Caddy 自动申请并续期 Let's Encrypt 证书，访问 `https://app.example.com` 与 `https://admin.example.com`
- 没有域名时可把 Caddyfile 的域名改为 `:443` 并加 `tls internal` 使用自签名证书
- 反向代理后客户端 IP 由 `X-Forwarded-For` 传递，登录限流按真实 IP 生效
- 数据库备份：`docker exec travel-mysql mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction travel_planning > backup_$(date +%F).sql`
- 更新代码：`git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`

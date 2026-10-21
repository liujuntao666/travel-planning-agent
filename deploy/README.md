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

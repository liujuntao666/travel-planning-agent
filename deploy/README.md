# deploy

演示与开发环境一套起停。

```bash
cp .env.example .env    # 填入 LLM_API_KEY 等真实配置
docker compose up -d    # PostgreSQL + Redis
```

- `.env` 为本地真实配置，已被 .gitignore 排除，禁止提交
- 后端 / 前端服务容器在 M1 脚手架就绪后接入（见 docker-compose.yml 注释）

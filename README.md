# 旅游规划智能体系统（7 组）

基于大模型与智能体的全自动个性化旅行规划系统：一句话说出「去哪、几天、几人、预算」，系统自动查（实时信息）、自动算（时间与预算）、自动排（路线与节奏），输出完整可出行行程方案。

- C 端（本期已实现）：对话式行程规划、可视化编辑、AI 重排、版本对比回退、一键导出
- B 端（规划中）：旅行社线路库、智能体话术风格配置、经营统计
- 边界：支付与预订交易不在本期范围内

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + TypeScript + Vite，原生 Fetch + SSE 流式渲染 |
| 后端 | Python 3.11 + FastAPI + SQLAlchemy 2.0 |
| 数据库 | MySQL 8.0（20 张表，`deploy/mysql/init` 一键初始化） |
| 大模型 | OpenAI 兼容协议（Function Calling）；未配置 Key 时自动降级为规则引擎 |
| 部署 | Docker Compose（MySQL + 后端 + Nginx 前端） |

## 目录结构

```text
travel-planning-agent/
├─ frontend/
│  ├─ traveler/            # C 端：对话规划、行程面板、编辑、版本、导出
│  └─ admin/               # B 端（M3 规划）
├─ backend/
│  ├─ app/
│  │  ├─ agent_core/       # 意图识别、槽位抽取与追问、LLM 适配、对话编排（FR-01）
│  │  ├─ itinerary/        # 七类风格、地理聚类排期、预算核算、校验、版本（FR-02/08/10）
│  │  ├─ tools/            # 五类工具并行网关、5s 超时、降级标注、调用日志（FR-03～06）
│  │  ├─ export/           # PDF / 长图 / 微信长文渲染（FR-07）
│  │  ├─ api/              # 会话、消息 SSE、行程编辑、资源与日志接口
│  │  ├─ models/           # 20 张表 ORM 模型
│  │  └─ common/           # 配置、数据库、错误码、日志
│  └─ tests/               # 槽位、意图、端到端 API 测试
├─ deploy/                 # docker-compose、.env.example、MySQL 初始化脚本
├─ eval/                   # 评测集与回归脚本（NFR-01/02/07）
├─ docs/                   # 需求基线、接口契约、设计文档
└─ .github/                # CI（后端 ruff + pytest、前端 build）
```

## 快速开始（Docker，推荐）

```bash
cd deploy
cp .env.example .env      # 按需填入 LLM_API_KEY，不填也能完整演示
docker compose up -d --build
```

- 前端：http://localhost:8080
- 接口文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health
- MySQL 首次启动自动执行 `deploy/mysql/init/01_schema.sql` 与 `02_init_data.sql`

## 本地开发

```bash
# 1. 基础设施（仅数据库）
cd deploy && docker compose up -d mysql

# 2. 后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 3. 前端
cd frontend/traveler
npm install
npm run dev
```

前端默认请求 `http://127.0.0.1:8000/api/v1`，可通过 `VITE_API_BASE` 覆盖；容器内构建默认 `/api/v1`，由 Nginx 反向代理到后端。

## 核心接口

统一前缀 `/api/v1`，交互式文档见 `/docs`。

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/users/login` | 按 open_id 登录/创建游客 |
| POST | `/conversations` | 新建会话 |
| GET | `/conversations?user_id=` | 会话列表 |
| GET | `/conversations/{id}` | 会话详情（消息、槽位、当前行程） |
| POST | `/conversations/{id}/messages` | 发送消息（非流式） |
| POST | `/conversations/{id}/messages/stream` | 发送消息（SSE：start/slots/tool/degrade/chunk/done/error） |
| GET | `/trips/{id}` | 行程详情（按天时间轴、预算、问题、降级说明） |
| PATCH/DELETE | `/trips/{id}/items/{item_id}` | 修改时段 / 删除条目 |
| POST | `/trips/{id}/items/{item_id}/move` | 上移 / 下移 |
| POST | `/trips/{id}/items` | 新增条目 |
| POST | `/trips/{id}/lodgings/{lid}/replace` | 替换住宿 |
| POST | `/trips/{id}/replan` | AI 重新排布 |
| GET | `/trips/{id}/versions` | 版本列表 |
| GET | `/trips/{id}/versions/compare?base=&target=` | 版本对比 |
| POST | `/trips/{id}/versions/{vid}/activate` | 回退到指定版本 |
| POST | `/trips/{id}/exports` | 导出 PDF / LONG_IMAGE / WECHAT_ARTICLE |
| GET | `/trips/{id}/exports` | 导出记录 |
| GET | `/resources/cities\|pois\|hotels` | 城市、景点、酒店资源 |
| GET | `/meta/styles` | 七类行程风格 |
| GET | `/tips` | 旅行锦囊 |
| GET | `/tool-logs` | 工具调用日志（可按 trace / 会话 / 行程过滤） |
| GET | `/health` | 健康检查 |

## 演示脚本

1. 输入「从杭州出发去云南玩 5 天，2 个人，预算 8000 元，想慢节奏」→ 槽位逐项确认后生成完整行程
2. 右侧时间轴查看每日点位、用餐、住宿、交通与预算拆分
3. 手动改时段 / 删除条目 / 上下移 → 自动重算预算并生成新版本
4. 点击「AI 重排」→ 时段顺延、预算复核
5. 继续对话「帮我加一天」「住得离景区近一点」→ 生成调整版本
6. 版本记录中任意两版对比，或回退到历史版本
7. 导出 PDF / 长图 / 微信长文，浏览器直接打开产物
8. 故障演练：`TOOL_OFFLINE=true` 重启后端后重新生成，行程与对话均标注「信息待确认」

## 测试与质量

```bash
cd backend
pip install -r requirements.txt
ruff check .
pytest -q

cd ../frontend/traveler
npm run build          # vue-tsc 类型检查 + 生产构建
```

CI 在 push / PR 到 `main`、`develop` 时自动执行以上检查。

## 分支模型

`main`（受保护，仅接收里程碑合并）← `develop`（日常集成）← `feature / fix`（日常开发）

- 功能分支命名：`feature/FR-02-itinerary`（带 FR 编号）
- 紧急修复：自 `main` 拉出 `hotfix/xxx`，合回 `main` 后同步 `develop`
- 提交规范：Conventional Commits，如 `feat(agent): 槽位缺失时逐项澄清追问 (FR-01) Closes #12`

## 里程碑

| 里程碑 | 范围 | 状态 |
|---|---|---|
| M1 核心闭环 | FR-01/02/03 | 已完成：一句话生成完整行程端到端可用 |
| M2 完整体验 | FR-04～08 | 已完成：交通/住宿/美食、编辑重排、导出 |
| M3 扩展与后台 | FR-09/10/11 | 进行中：锦囊已接入；B 端后台待开发 |
| M4 回归与验收 | NFR | 进行中：单元与接口测试、降级演练、CI 已就绪 |

## 配置说明

所有配置通过环境变量覆盖（见 `deploy/.env.example`）：`LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`、`DATABASE_URL`、`TOOL_TIMEOUT_MS`、`TOOL_OFFLINE`、`CORS_ORIGINS` 等。

> 不要把真实密钥写入仓库；`.env` 已被 `.gitignore` 排除。

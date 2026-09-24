# 旅游规划智能体系统（7 组）

基于大模型与智能体的全自动个性化旅行规划系统：一句话说出「去哪、几天、几人、预算」，系统自动查（实时信息）、自动算（时间与预算）、自动排（路线与节奏），输出完整可出行行程方案。

- C 端：对话式行程规划、可视化编辑、一键导出
- B 端：旅行社线路库、智能体话术风格配置、经营统计
- 边界：支付与预订交易不在本期范围内

## 目录结构

```text
travel-planning-agent/
├─ frontend/
│  ├─ traveler/            # C 端（对话、行程、编辑器、导出）
│  └─ admin/               # B 端（线路库、产品、配置、统计）
├─ backend/
│  ├─ app/
│  │  ├─ agent_core/       # 智能体核心层（FR-01）
│  │  ├─ itinerary/        # 行程生成与优化引擎（FR-02/08/10）
│  │  ├─ tools/            # 调用网关 + 五类适配器（FR-03～06）
│  │  ├─ export/          # 行程单渲染（FR-07）
│  │  ├─ admin/            # B 端 API（FR-11）
│  │  └─ common/          # 配置、日志、错误码、鉴权
│  ├─ alembic/            # 数据库迁移
│  └─ tests/
├─ eval/                    # 评测集与回归脚本（NFR-01/02/07）
├─ docs/                    # 需求基线、接口契约、设计文档
├─ deploy/                  # docker-compose、.env.example
└─ .github/                 # CI 流水线、Issue/PR 模板、CODEOWNERS
```

## 分支模型

`main`（受保护，仅接收里程碑合并）← `develop`（日常集成）← `feature / fix`（日常开发）

- 功能分支命名：`feature/FR-02-itinerary`（带 FR 编号）
- 紧急修复：自 `main` 拉出 `hotfix/xxx`，合回 `main` 后同步 `develop`
- 提交规范：Conventional Commits，如 `feat(agent): 槽位缺失时逐项澄清追问 (FR-01) Closes #12`

## 里程碑

| 里程碑 | 范围 | 出口标准 |
|---|---|---|
| M1 核心闭环 | FR-01/02/03 | 「一句话生成完整行程」端到端演示通过 |
| M2 完整体验 | FR-04～08 | 交通/住宿/美食、编辑重排、导出可用 |
| M3 扩展与后台 | FR-09/10/11 | 锦囊、多目的地、后台链路走通 |
| M4 回归与验收 | NFR | 评测集全量回归、降级演练、文档齐套 |

## 快速开始

```bash
# 基础设施（PostgreSQL + Redis）
cd deploy && docker compose up -d

# 后端（Python 3.11 + FastAPI）
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload

# 前端（Vue 3 + TypeScript）
cd frontend/traveler && npm i && npm run dev
```

> 脚手架文件（requirements.txt、package.json 等）由各成员首次提交补齐。

## 文档

- 需求基线：`docs/需求分析文档-V1.1.docx`
- 接口契约：`docs/api/`（契约先行，OpenAPI）
- 分工与排期：见项目实施规划报告（五人五线 · 8 周 · M1～M4）

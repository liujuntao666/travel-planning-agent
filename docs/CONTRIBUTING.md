# 贡献指南

## 分支模型

- `main`：稳定版本，只通过 PR 从 develop 合入，禁止直接 push
- `develop`：日常开发基线，所有功能在此汇合
- `feature/<模块名>`：每人一个功能分支，从 develop 拉出，完工后 PR 合回 develop

## 开工流程

```bash
git clone https://github.com/liujuntao666/travel-planning-agent.git
cd travel-planning-agent
git checkout develop
git pull
git checkout -b feature/你的模块名
```

## 提交规范（Conventional Commits）

格式：`<类型>: <简要描述>`

| 类型 | 用途 |
|------|------|
| feat | 新功能 |
| fix | 缺陷修复 |
| docs | 文档变更 |
| style | 代码格式（不影响逻辑） |
| refactor | 重构（既非 feat 也非 fix） |
| test | 测试相关 |
| chore | 构建 / 工具 / 依赖变更 |

示例：

```
feat: 行程生成引擎支持五类行程风格槽位
fix: 对话轮次超过 8 轮未收齐要素时强制生成行程
docs: 补充接口契约文档
```

## Pull Request 要求

- 标题遵循提交规范，正文说明变更与动机
- 关联对应 Issue（`Closes #N`）
- 提交前本地自测通过
- CI 绿灯后方可合并

## 团队分工速查

| 成员 | 主线 | 副线 |
|------|------|------|
| 成员 A | 智能体核心（agent_core） | 评测集（eval） |
| 成员 B | 行程生成与优化（itinerary） | 行程单导出（export） |
| 成员 C | 工具调用网关（tools） | B 端 API（admin） |
| 成员 D | C 端前端（frontend/traveler） | B 端前端（frontend/admin） |
| 成员 E | B 端前端 + 后台 API | 公共组件（common） |

> 具体人名与分支分配由组长确认后更新此表。

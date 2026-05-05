# OpenGUIRobot · v0.4 PRD「企业试点」

| 字段 | 内容 |
|---|---|
| 版本号 | v0.4.x |
| 版本主题 | 企业试点（Enterprise Pilot） |
| 周期 | 6 周（接续 v0.3） |
| 上游依据 | `ARCHITECTURE.md` §14 v0.4 |
| 文档状态 | Draft |

---

## 1. 版本概述

v0.3 让平台具备规模化能力，v0.4 让它**能交付到企业试点客户**。这版的核心动作有四个：

1. 把 Heal Mode 做完整：失败用例自动 patch 代码并发 PR
2. Web Dashboard 上线（Ant Design Pro + ProComponents）
3. 多租户 + 权限模型，能给多个团队同时用
4. 离线 / 私有化部署模板，配合 OpenTelemetry 完整可观测性

---

## 2. 用户画像与场景

| 画像 | 期望 |
|---|---|
| 企业试点客户 QA | 在浏览器里看到任务、设备、用例、成本 |
| 试点客户研发负责人 | 失败用例自动 PR 给开发，不堵塞测试 |
| 私有化客户运维 | 一份 docker-compose / Helm 就能起来 |
| Anthropic / 第三方做安全审计 | trace / metric / log 全链路完整 |

**核心场景**：

- **早晨第一件事**：QA 打开 Dashboard，看见昨夜回归结果 + Top 5 不稳定 case
- **失败自愈**：CI 跑回归 → 单 step 失败 → Heal Mode 触发 → 局部 codegen → 验证 → 自动开 PR
- **多团队共享**：电商 + 社交 + 直播三个 BU 共用一套平台，权限隔离、配额隔离
- **私有化**：客户内网拉一个 Helm chart 起来即可，不需要外网模型

---

## 3. 范围（In / Out）

### In

- L4 Heal Mode 完整：定位失败 → 局部 codegen → sandbox 验证 → 自动 PR（GitHub / GitLab / Gitee）
- Web Dashboard：首页看板、Devices、Jobs、Cases、Knowledge、Graph、Cost
- 后端 OpenAPI + `swagger-typescript-api` 自动同步
- 多租户：tenant 模型 + 配额（设备 / 预算 / 并发）
- RBAC：role + permission + ProTable 权限渲染
- 认证：JWT + OAuth2（Github / 飞书 / 钉钉 / 企业微信 SSO）
- 部署模板：docker-compose（开发）+ Helm chart（生产）
- 私有化：全本地模型 + 内网部署文档
- 完整 OpenTelemetry：trace / metric / log，OTLP exporter

### Out

- 国产 / 本地 LLM 全面适配 + 安全审计（v1.0）
- LTS 分支策略（v1.0）
- 业务地图插件（v1.x）
- IDE 插件（v1.x）

---

## 4. 功能需求（FR）

### FR-1 Heal Mode 完整流程

```
回归失败 → 错误归因（定位错 / 断言错 / 异常）
        → 收集失败上下文（截图、DOM、原代码片段）
        → 局部 codegen（仅修改失败步骤代码块）
        → sandbox 验证 patch
        → 通过：开 PR；失败：fallback 到原代码 + 标记 unstable
```

PR 内容：

- 自动生成 commit message（"fix: heal step-7 in case xxx"）
- 文件：仅修改 `tests/generated/<group>/<case>.py` 中的失败步骤
- description 含失败截图链接、自愈日志链接、置信度

### FR-2 Web Dashboard

页面清单（默认）：

- **首页**（PageContainer + ProCard）：今日 / 7 日 / 30 日跑数、Top N 失败、设备健康
- **Devices**（ProTable）：注册、心跳、状态、远程操作、按 tenant 过滤
- **Jobs**（ProTable + 详情抽屉）：实时任务、按 case 聚合、单任务步骤回放
- **Cases**（ProTable + ProForm）：CRUD、explore / replay / heal 触发
- **Knowledge**（自定义 + react-markdown）：L0/L1/L2 树状导航
- **Graph**（AntV G6）：操作图谱可视化、置信度热力
- **Cost**（ECharts）：按模型 / case / team 的趋势

### FR-3 多租户

- `Tenant` 模型：tenant_id 贯穿所有数据表
- 设备 / Case / KB / 图谱按 tenant 隔离（共享数据走 `shared` tenant）
- 配额：设备数、月度 LLM 预算、并发任务数
- 数据库行级隔离（policy）+ 应用层校验双保险

### FR-4 RBAC

- 内置角色：`owner` / `admin` / `engineer` / `viewer`
- 权限点：`device.view/manage`、`case.view/edit/run`、`kb.read/write`、`cost.view`、`tenant.admin`
- 前端 Umi `access` 插件 + 后端中间件双层校验

### FR-5 SSO 认证

- 默认 JWT（用户名密码）
- 可选 OAuth2 provider：GitHub / GitLab / 飞书 / 钉钉 / 企业微信
- 配置驱动，每个 tenant 可独立配置

### FR-6 部署模板

- `deploy/compose/`：单机开发用 docker-compose（含 Postgres / Redis / Qdrant / Registry / Worker / Web）
- `deploy/k8s/`：生产用 Helm chart
- `deploy/sandbox/`：bwrap profile / sandbox-exec sb 文件
- 私有化：附 `PRIVATE-DEPLOY.md`，含本地 vLLM 部署、内网证书、镜像构建步骤

### FR-7 OpenTelemetry 全链路

- 后端 FastAPI / SQLAlchemy / Redis / httpx 全自动 instrument
- 业务 trace：每个 explore / heal / replay 一条根 span
- LLM 调用 metric：tokens / cost / latency
- 默认 exporter：OTLP；建议配 Grafana Tempo + Loki + Prometheus

### FR-8 Cost Dashboard

- 按 model / case / tenant / time 维度切分
- 月度预算对比 + 超支预警
- LLM cost 与设备耗时合并核算

---

## 5. 非功能需求（NFR）

| 维度 | 指标 |
|---|---|
| Heal Mode 自愈成功率 | ≥ 60% |
| Heal PR 通过率（人工 review 直接 merge） | ≥ 50% |
| Dashboard 首屏加载 | ≤ 2 秒 |
| Dashboard 实时任务推送延迟 | ≤ 1 秒（WebSocket） |
| 单 tenant 并发设备数 | ≥ 50（不影响其它 tenant） |
| 部署上线时间（按文档） | ≤ 1 小时 |
| Trace 全链路连续性 | 100%（无断点） |

---

## 6. 验收标准

- [ ] 选 3 个企业试点客户（含至少 1 个国内、1 个海外）
- [ ] 客户能在 1 小时内按文档跑起 Helm chart
- [ ] 提供 50 个故意制造失败的 case，Heal Mode 自动 PR 通过率 ≥ 50%
- [ ] Dashboard 7 个核心页面功能齐全，端到端 Playwright 测试通过
- [ ] 三个 tenant 各自跑 100 case，配额触达时正确告警
- [ ] OTel trace 在 Grafana Tempo 中能看到完整链路（跨 Registry / Worker / Agent）
- [ ] 安全自检：用 OWASP ZAP 跑一遍核心 API；沙箱用 fuzzer 跑 10 万样本无逃逸
- [ ] 文档：`HEAL-MODE.md`、`DASHBOARD.md`、`MULTI-TENANT.md`、`SSO.md`、`PRIVATE-DEPLOY.md`、`OBSERVABILITY.md`

---

## 7. 依赖与风险

| 项 | 风险 | 缓解 |
|---|---|---|
| Heal PR 误改业务逻辑 | LLM 改超预期 | 严格限定只改失败步骤代码块 + 强制 review |
| Dashboard 工程量大 | 6 周不够 | 砍到 7 页面 P0；高级可视化（图谱）作为 v1.0 优化 |
| 多租户数据泄漏 | 行级隔离写错 | 应用层 + 数据库双 policy；自动化渗透测试 |
| 私有化客户网络封闭 | 模型 / 镜像无法拉取 | 提供离线包（含 vLLM 镜像 + 模型权重）下载脚本 |
| OAuth provider 各家差异 | 接入成本高 | 优先 GitHub + 飞书 + 企业微信，其它社区贡献 |

---

## 8. 时间安排

| 周 | 里程碑 |
|---|---|
| W1 | Heal Mode 完整流程 + PR 接入 GitHub/GitLab |
| W2 | 后端 API 整理 + OpenAPI + swagger-typescript-api |
| W3 | Dashboard 框架（Umi + Pro）+ 首页 / Devices / Jobs |
| W4 | Cases / Knowledge / Graph / Cost 四个页面 |
| W5 | 多租户 + RBAC + SSO + 配额 |
| W6 | 部署模板（compose + helm）+ OTel + 私有化文档 + 验收 |

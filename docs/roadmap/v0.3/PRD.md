# OpenGUIRobot · v0.3 PRD「可规模」

| 字段 | 内容 |
|---|---|
| 版本号 | v0.3.x |
| 版本主题 | 可规模（Scalable） |
| 周期 | 4 周（接续 v0.2） |
| 上游依据 | `ARCHITECTURE.md` §14 v0.3 |
| 文档状态 | Draft |

---

## 1. 版本概述

v0.2 让单设备稳定，v0.3 把场景从"一台机器一个用例"扩展到**"一台调度机管 20+ 设备、跨平台并发回归"**。

引入操作图谱（KuzuDB）+ Qdrant 路径召回，让 LLM 不再凭空探索；引入设备注册中心 + 拉式任务队列，让边缘 Agent 自主消费任务；补齐鸿蒙 driver。

---

## 2. 用户画像与场景

| 画像 | 期望 |
|---|---|
| 测试平台研发 | 跑得起规模化回归（数百个 case / 数十设备） |
| 多端测试团队（含鸿蒙） | iOS / Android / 鸿蒙一套用例并行验证 |
| 知识沉淀负责人 | 看到知识库与图谱被自动反哺 |

**核心场景**：

- **三端并行**：同一 case 在 Android / iOS / 鸿蒙各 5 台真机同时跑
- **大规模回归**：500 case × 3 端 ≈ 1500 任务，单调度机一夜跑完
- **路径引导**：用户写"加购流程"，系统从图谱里捞出已有 path，LLM 只需补差异
- **失败入图**：每次失败的 step、变体路径自动写回图谱并打 stale 标签

---

## 3. 范围（In / Out）

### In

- L3 Memory 完整：操作图谱（KuzuDB）+ 向量召回（Qdrant）+ 自动反哺
- 路径引导 API：`recalledPaths` / `suggestedPaths` / `missingKnowledge` / `confidence`
- L5 Device Registry：USB + WiFi 自动注册、心跳、故障诊断、自动重连
- L5 Job 系统：APScheduler 定时 + Arq 异步 + PostgreSQL `FOR UPDATE SKIP LOCKED` 拉式队列
- 多设备并发（每设备一个 worker）
- 鸿蒙 driver（HDC wrapper）
- KB 自动反哺（成功探索 → L2 KB + 图谱节点）
- L2 KB 文件由系统生成，人工 review 修改

### Out

- Heal Mode 自动 PR（v0.4）
- Web Dashboard（v0.4）
- 多租户、权限（v0.4）
- 完整离线 / 私有化（v0.4）
- 业务地图插件（v1.x）

---

## 4. 功能需求（FR）

### FR-1 操作图谱建模与查询

- 图节点：`Page` / `Action` / `Path` / `Anchor`
- 图边：`TRIGGERS` / `PREV_OF` / `NEXT_OF` / `VARIANT_OF` / `REGRESSED_FROM`
- 查询接口：根据自然语言意图返回候选 path 子图
- 嵌入式 KuzuDB（`./data/op_graph.kuzu`）

### FR-2 路径引导

- Codegen 在 prompt 中注入 `recalledPaths`（已知精确）+ `suggestedPaths`（AI 推导）+ `missingKnowledge`（图谱空白）
- 每个 path 节点附 `confidence.perStep` 和 `confidence.overall`
- 整体置信度 < 60 → 强制 review（写日志）
- 探索成功后回写图谱，更新 success_rate

### FR-3 自动反哺 KB / 图谱

- 探索成功 → 把步骤序列结构化写入图谱
- 提取截图 / DOM 关键特征 → 生成 L2 KB Markdown 草稿（用户 review 后合入）
- 失败的 step 在图谱中打 `regressed_from` 关系

### FR-4 设备注册中心

- HTTP API：`POST /agents/register` / `POST /agents/heartbeat` / `GET /agents`
- USB 自动发现（Local Agent 周期扫 `adb`/`hdc`/`pymobiledevice3`）
- WiFi 设备：Agent 主动注册到 Registry，断线后按 Agent ID + IP 重连
- 心跳超时 30s → faulted；连续 3 次诊断失败 → offline

### FR-5 任务调度

- 定时（APScheduler）：cron / interval / date 三类触发器
- 异步任务（Arq）：codegen、heal（v0.4 才完整）、assert
- 设备 Agent 拉任务：long-poll `jobs` 表（PostgreSQL `FOR UPDATE SKIP LOCKED`）
- 调度策略：优先级 + 设备亲和 + 平台亲和 + 反亲和（同 case 多变体跨设备）

### FR-6 多设备并发

- 单设备 1 worker，避免 driver 冲突
- 同 App 全局并发上限可配
- 跨设备并发跑同一 case 的不同变体（Android / iOS / 鸿蒙、不同分辨率）
- 任务结果聚合到一份"case 多端报告"

### FR-7 鸿蒙 driver

- 实现完整 `Driver` Protocol，基于 `hdc` CLI
- 支持鸿蒙 Next 设备（API 12+）
- 至少在 1 款主流应用上验证 demo

### FR-8 KB lint v2

- 增量校验：仅校验 PR 中变化的文件
- L2 文件按业务模块归档校验
- `ogr kb stats` 输出腐坏指标（stale 比例、missingKnowledge 增长）

---

## 5. 非功能需求（NFR）

| 维度 | 指标 |
|---|---|
| 单调度机管理设备数 | ≥ 20 |
| 500 case × 3 端 总耗时 | ≤ 6 小时 |
| 路径召回率（已知 case） | ≥ 95% |
| 路径召回率（增量 case） | ≥ 70% |
| 设备故障自恢复率 | ≥ 80% |
| 任务吞吐 | 单调度机 ≥ 200 jobs/小时 |
| KB 文件腐坏识别 | 90 天未验证 + 失败率 > 30% 自动标记 |

---

## 6. 验收标准

- [ ] 起一个 PostgreSQL + Redis + Registry，注册 20 台真实/模拟器设备，连续运行 24 小时无人值守
- [ ] 跑 500 case × 3 端的全量回归，6 小时内完成
- [ ] 同一 case 在三端并行执行的 path 差异能被系统识别并写入图谱
- [ ] 探索一个新 case 后，相关的 L2 KB 草稿与图谱节点自动产出，可在 PR 中 review
- [ ] 鸿蒙 driver 在一个真实 App（如新闻 / 视频类）上跑通 demo
- [ ] 文档：`MEMORY.md`、`DEVICE-REGISTRY.md`、`SCHEDULER.md`、`HARMONY-DRIVER.md`

---

## 7. 依赖与风险

| 项 | 风险 | 缓解 |
|---|---|---|
| KuzuDB 嵌入式并发写 | 多 worker 同时写入冲突 | 写入串行化（单进程 writer + 异步 flush） |
| Qdrant 索引一致性 | 图节点变更后向量未更新 | 增量索引 + nightly rebuild |
| 鸿蒙 SDK 接口稳定性 | HDC 接口在快速演进 | pin SDK 版本，CI nightly 抓 break |
| 任务 starvation | 高优先级 case 抢光资源 | 公平调度 + per-team quota |
| pull queue 单点 | PostgreSQL 故障调度全停 | PG 主备 + Registry 无状态 |

---

## 8. 时间安排

| 周 | 里程碑 |
|---|---|
| W1 | KuzuDB schema + Qdrant 接入 + 路径召回 API |
| W2 | Device Registry + Local Agent + 心跳 + 自动重连 |
| W3 | APScheduler + Arq + PostgreSQL pull queue + 调度策略 |
| W4 | 鸿蒙 driver + 自动反哺 + 500 case × 3 端 验收 |

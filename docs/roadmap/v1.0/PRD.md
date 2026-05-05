# OpenGUIRobot · v1.0 PRD「生产可用」

| 字段 | 内容 |
|---|---|
| 版本号 | v1.0.0（LTS 起点） |
| 版本主题 | 生产可用（GA） |
| 周期 | 6–8 周（接续 v0.4） |
| 上游依据 | `ARCHITECTURE.md` §14 v1.0 |
| 文档状态 | Draft |

---

## 1. 版本概述

v0.4 把功能凑齐，v1.0 要让一个**陌生企业能在 1 周内把它正式接入生产**。这版的关键不再是"加功能"，而是"补齐文档、深入适配、通过审计、定下版本契约"。

主要工作：

- 完整的文档体系（贡献者、运维、安全、迁移）
- LLM 适配从"够用"到"全面"：国产 + 本地全量覆盖
- 第三方安全审计（沙箱、API、依赖、供应链）
- LTS 分支策略 + 公开的兼容性矩阵
- 性能基线 + 负载测试报告

---

## 2. 用户画像与场景

| 画像 | 期望 |
|---|---|
| 企业 SA / 运维 | 一份《生产部署最佳实践》能照着做完 |
| 安全合规 | 看到第三方审计报告 + SBOM + 漏洞披露流程 |
| 平台研发（贡献者） | 有完善的 `CONTRIBUTING.md` + 设计 ADR + 测试模板 |
| 国内客户 | 通义 / 豆包 / 智谱 / Kimi 任选；本地 GPU 跑 Qwen 系列 |
| 海外客户 | OpenAI / Anthropic / Bedrock / Vertex 全覆盖 |

**核心场景**：

- **生产引入决策**：客户安全团队拿着审计报告做合规决策，无需自查
- **国产化场景**：金融 / 政企客户全本地跑（无外网），完全离线
- **长期维护**：v1.0 LTS 至少维护 18 个月，明确 patch 周期

---

## 3. 范围（In / Out）

### In

- 完整文档：`README` / `QUICKSTART` / `ARCHITECTURE` / `CONTRIBUTING` / `DEPLOYMENT` / `SECURITY` / `MIGRATION` / `FAQ`
- LLM 适配全量：
  - 云：OpenAI、Anthropic、AWS Bedrock、Vertex AI、DashScope、豆包、智谱、Kimi
  - 本地：vLLM、Ollama、LM Studio
  - 网关层：支持 LiteLLM-style 抽象
- 视觉模型适配全量：Qwen-VL 系列、InternVL、MiniCPM-V、GPT-4o、Gemini Pro Vision
- 第三方安全审计：核心包 + 沙箱 + 依赖 SBOM + 供应链
- LTS 分支：`release/1.x` 长期维护，明确 EOL
- 性能基线 + 负载报告
- 兼容性矩阵：OS / Python / Appium / Driver 各组合
- 公开漏洞披露流程（SECURITY.md）
- 公共 release artifacts（PyPI + Docker Hub + Helm Chart Repo）

### Out

- 业务地图插件（v1.x）
- 视频→图谱抽取（v1.x）
- IDE 插件（v1.x）
- 商业版差异化能力（v1.x）

---

## 4. 功能需求（FR）

### FR-1 文档体系

新增或大幅完善：

- **README.md**：定位、快速上手、社区、license
- **docs/QUICKSTART.md**：30 分钟跑通
- **docs/ARCHITECTURE.md**：本仓库已有
- **docs/DEPLOYMENT.md**：单机 / K8s / 私有化 / 灾备 / 升级 / 回滚
- **docs/SECURITY.md**：威胁模型、沙箱、漏洞披露流程
- **docs/MIGRATION.md**：从 Appium / Selenium / Espresso / EarlGrey 迁入
- **docs/CONTRIBUTING.md**：开发环境、coding style、PR 流程、ADR 模板
- **docs/FAQ.md**：常见问题
- **docs/CHANGELOG.md**：从 v0.1 起的变更记录
- **docs/COMPATIBILITY.md**：兼容性矩阵
- **docs/adr/**：架构决策记录（ADR），至少包含 v0.1 起所有重大决策

### FR-2 LLM 适配全量

每个 provider 必须实现：

- 文本 chat（含 streaming）
- 嵌入（如适用）
- cost 与 token 统计
- 错误重试
- 至少一个 e2e 集成测试

支持 chain：

```yaml
llm:
  primary: anthropic:claude-sonnet
  fallback:
    - openai:gpt-4o
    - dashscope:qwen-max
    - local_vllm:qwen3-coder
```

### FR-3 视觉模型适配全量

同 LLM，覆盖云端 + 本地，提供能力矩阵：

| Provider | grounding | describe | diff | 中文 OCR |
|---|---|---|---|---|
| Qwen-VL（local/cloud）| ✓ | ✓ | ✓ | 强 |
| InternVL | ✓ | ✓ | ✓ | 中 |
| MiniCPM-V | ✓ | ✓ | ✓ | 中 |
| GPT-4o | ✓ | ✓ | ✓ | 中 |
| Gemini | ✓ | ✓ | ✓ | 中 |

### FR-4 安全审计

- 委托第三方对：
  - 核心 Python 包做静态扫描
  - 沙箱做渗透测试 + fuzz
  - Web Dashboard 做 OWASP Top 10
  - Helm chart / Docker 镜像做 CIS benchmark
- 输出审计报告（`docs/security/audit-2026-Q3.pdf`）
- 严重 / 高危问题在 v1.0 发布前清零
- SBOM（CycloneDX 格式）随 release 发布

### FR-5 LTS 分支策略

- v1.0 起每个 minor 版本（v1.0 / v1.1 …）作为 LTS 候选
- v1.0 LTS 至少维护 **18 个月**（patch + 安全更新）
- 明确 EOL 日期；至少在 EOL 前 6 个月公布
- 安全 patch 优先回移：CVE 24h 内响应、72h 内 patch
- 公开 release schedule

### FR-6 性能基线 + 负载报告

发布以下基线（在指定硬件上）：

- 单设备 explore P50 / P95 / P99 耗时
- 单设备 replay P50 / P95 / P99 耗时
- 调度机吞吐：jobs/min
- LLM 平均成本 / case
- 视觉断言时延（local vs cloud）
- 内存 / fd 长跑稳定性（72 小时）

### FR-7 兼容性矩阵

公开测试通过的组合：

| OS | Python | Appium | Android | iOS | 鸿蒙 |
|---|---|---|---|---|---|
| Ubuntu 22.04 | 3.11/3.12 | 2.5.x | 8/10/12/14 | 15/16/17 | Next API 12 |
| macOS 14 | 3.11/3.12 | 2.5.x | … | … | … |

每个组合在 CI 跑 nightly。

### FR-8 公共发布物

- PyPI：`openguirobot`（含可选 extras）
- Docker Hub：`openguirobot/api`、`openguirobot/web`
- Helm chart repo：`https://charts.openguirobot.dev`
- GitHub Release：源码 + SBOM + checksum
- Demo App 镜像：`openguirobot/demo-shop`

---

## 5. 非功能需求（NFR）

| 维度 | 指标 |
|---|---|
| 文档完整性 | 8 份核心文档 + ADR ≥ 10 份 |
| 文档覆盖率（用户问题→文档） | ≥ 90% |
| 安全审计严重问题 | 0 |
| 安全审计高危问题 | 0 |
| 兼容性矩阵覆盖 | 至少 12 组合 nightly 通过 |
| 升级（minor）成功率 | ≥ 99% |
| 降级（rollback）成功率 | 100% |

---

## 6. 验收标准

- [ ] 8 份文档 + 10+ ADR 上线，结构通过外部 reviewer 检查
- [ ] 第三方安全审计报告公开发布，无未关闭 critical / high
- [ ] LLM / 视觉 chain 在 nightly CI 全 provider 通过
- [ ] 兼容性矩阵 12+ 组合在 nightly 跑稳
- [ ] 至少 5 家试点客户升级到 v1.0，无重大问题
- [ ] PyPI / Docker Hub / Helm Chart Repo 全部就绪
- [ ] LTS 政策对外发布

---

## 7. 依赖与风险

| 项 | 风险 | 缓解 |
|---|---|---|
| 第三方审计周期长 | 排期可能拖延 | v0.4 收尾时同步开案，预留 4 周 |
| 国产 LLM 接口频繁变 | 维护成本高 | 网关抽象 + 自动 contract 测试 |
| LTS 承诺压力 | 必须保证 18 月内 patch 能力 | 自动化测试矩阵 + 至少 2 名核心维护者 |
| 文档维护成本 | 6 份新文档 + 持续更新 | 为每份文档指定 owner；CI 检查死链 |

---

## 8. 时间安排

| 周 | 里程碑 |
|---|---|
| W1 | LLM 适配全量（含 chain）+ contract test |
| W2 | 视觉模型适配全量 + 能力矩阵 |
| W3 | 文档：CONTRIBUTING / DEPLOYMENT / SECURITY / MIGRATION |
| W4 | 文档：FAQ / COMPATIBILITY / CHANGELOG / ADR 整理 |
| W5 | 安全审计配合（修复发现的问题）+ SBOM 生成 |
| W6 | 性能基线 + 负载测试 + 兼容性矩阵 |
| W7 | 5 家客户升级试点 + bug fix |
| W8 | LTS 政策发布 + v1.0.0 GA + 公关 |

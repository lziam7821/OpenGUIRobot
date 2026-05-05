# OpenGUIRobot · v0.2 PRD「稳」

| 字段 | 内容 |
|---|---|
| 版本号 | v0.2.x |
| 版本主题 | 稳（Stable Run） |
| 周期 | 4 周（接续 v0.1） |
| 上游依据 | `ARCHITECTURE.md` §14 v0.2 |
| 文档状态 | Draft |

---

## 1. 版本概述

v0.1 解决了"能跑通"，v0.2 要解决**"能反复跑通"**。

它把 v0.1 暴露的脆弱性补齐：弹窗导致失败、网络抖动导致定位错误、断言能力薄弱、视觉模型成本不稳。同时引入仓库内分层知识库（L0/L1）作为后续 v0.3 操作图谱的预先沉淀池，引入 pytest 插件让用户能用熟悉的工具跑回归。

---

## 2. 用户画像与场景

| 画像 | 期望 |
|---|---|
| 内部团队（小规模试点） | 把 50 个核心用例从手工 / Appium 老脚本迁过来，每天稳定跑一轮 |
| 测试主管 | 看见明确的稳定性数据（失败率、自愈成功率、成本曲线） |

**核心场景**：

- **晚高峰回归**：50 个 case，凌晨 2 点串行 / 并行跑，第二天看报告
- **失败定位**：失败 case 自动产出截图、DOM、自愈尝试链路，不需要工程师重现
- **成本可控**：单 case 探索 < 1.5 USD；回归全程 0 token

---

## 3. 范围（In / Out）

### In

- L1 Healer Skill：四层防护（弹窗 5 策略 / 截图相似度 / 上下文记忆 / 失败兜底）
- 异步断言 Agent（Arq worker）
- 知识库写入规范（`docs/kb/L0/`、`docs/kb/L1/`），手工编写 + 自动提示
- pytest plugin（`pytest_openguirobot`），原生 `--ogr-replay` / `--ogr-explore` 选项
- 视觉模型本地部署：Qwen2.5-VL-7B via vLLM
- Vision Adapter 多 provider fallback：本地 → 云端
- LLM Cost 预算门槛 + 超限报警
- 失败重试 / 步骤级 rollback

### Out

- 操作图谱、置信度、路径引导（v0.3）
- 自动反哺 KB（v0.3）
- 多设备并发（v0.3）
- 鸿蒙 driver（v0.3）
- 完整 Heal Mode（自动局部代码生成 + PR）：v0.4
- Web Dashboard：v0.4

---

## 4. 功能需求（FR）

### FR-1 弹窗 5 策略自愈

按顺序尝试，最多递归 3 次：

1. 命中"关闭 / Close / 取消 / 跳过"按钮文本
2. 命中右上角 X 图标位置
3. 弹窗外区域点击
4. 系统返回键
5. 向下滑动关闭

每次尝试后立刻截图比对，相似度变化 > 阈值才算成功。

### FR-2 截图相似度兜底

- 点击操作前后截图相似度 < 75% 算页面跳转成功；否则触发重定位
- 输入操作前后相似度 < 90% 算键盘弹起；否则重输
- 算法：`imagehash.phash` 默认；可切 SSIM

### FR-3 上下文记忆决策（Layer 3）

- 同一步骤连续失败 2 次 → 触发回退
- 同 case 历史成功率 < 50% → 标记 unstable，不进入回归集
- 决策日志写入 `evidence/.../decisions.jsonl`

### FR-4 异步断言 Agent

- 用例 `assertions:` 字段中的语义断言交给 Assertor Agent
- 通过 Arq 队列异步执行，不阻塞主流程
- 通用断言（黑屏、错乱、加载失败、错别字、icon 顺序）每步默认开启
- 用户可关：`assertions: { defaults: false }`

### FR-5 仓库内分层知识库（L0 + L1）

- 目录结构：`docs/kb/L0/`、`docs/kb/L1/<module>/`
- 每个 KB 文件需 YAML front matter（`module / case / last_verified / confidence / owners`）
- `ogr kb lint` 校验 front matter 合法性 + 行数上限
- L0 ≤ 200 行 / 文件；L1 ≤ 2000 行 / 文件

### FR-6 pytest 插件

- 安装即可：`pip install openguirobot` 自带 entry point
- 选项：
  - `--ogr-mode {explore|replay}`（默认 replay）
  - `--ogr-device <udid>`
  - `--ogr-budget-usd <n>`
  - `--ogr-cases <glob>`
- Fixture：`def test_x(ogr_driver, ogr_case): ...`
- 自动收集 `tests/generated/**/*.py`

### FR-7 本地视觉模型

- 提供 `ogr vision serve` 启动 vLLM + Qwen2.5-VL-7B
- Vision Adapter 支持 provider chain：`[local_qwen_vl, dashscope_qwen_vl, gpt4o]`
- 首选 local，失败回落到 cloud；记录 fallback 次数
- 文档：`docs/VISION-LOCAL.md`（GPU 要求、模型下载、显存配置）

### FR-8 LLM 成本预算

- 用例配置 `budget_usd: 1.5`
- 累计超 80% → warning；超 100% → 立刻终止本次探索
- 累计预算与 token 写入 `evidence/.../summary.json`

---

## 5. 非功能需求（NFR）

| 维度 | 指标 |
|---|---|
| 50 case 回归连续运行稳定性 | ≥ 95% |
| 自愈成功率（仅算 Layer 1–3） | ≥ 70% |
| 平均自愈耗时 | ≤ 8 秒 / 次 |
| 单 case 探索成本 | ≤ 1.5 USD |
| 单 case 回归耗时 | ≤ 90 秒 |
| 本地 Qwen-VL 推理时延 | ≤ 1.5 秒 / 次 (单卡 A10/4090) |
| KB 文档语法错误检出率 | 100%（lint） |

---

## 6. 验收标准

- [ ] 50 个内部金标用例，连续运行 5 个工作日稳定性 ≥ 95%
- [ ] 故意制造弹窗 / 网络抖动 / 元素错位三类故障，自愈率 ≥ 70%
- [ ] pytest 用 `--ogr-mode replay` 能跑 `tests/generated/`，0 token 消耗
- [ ] 本地 vLLM 部署能跑通；fallback 链路有 e2e 测试
- [ ] `ogr kb lint` 在 CI 中执行，不合规即失败
- [ ] 文档：`HEALING.md`、`KB-WRITING-GUIDE.md`、`PYTEST-INTEGRATION.md`、`VISION-LOCAL.md`

---

## 7. 依赖与风险

| 项 | 风险 | 缓解 |
|---|---|---|
| 本地 GPU 可用性 | 试用者无 GPU | 默认仍可走云端，本地是 opt-in |
| Qwen-VL 模型下载 | 国内 HF 拉模型慢 | 提供 modelscope 镜像下载脚本 |
| 弹窗策略对小众 App 失效 | 个别 App 弹窗结构特殊 | 允许用户在 case 中自定义 healer |
| Arq + Redis 引入 | 增加部署复杂度 | 单机模式可用进程内队列代替 |
| 截图相似度阈值不通用 | 不同分辨率影响 phash | 提供按设备校准的预置 |

---

## 8. 时间安排

| 周 | 里程碑 |
|---|---|
| W1 | Healer 四层框架 + Layer 1（弹窗 5 策略） |
| W2 | Layer 2（截图相似度）+ Layer 3（上下文记忆）+ 异步断言 Agent |
| W3 | KB 规范 + lint + pytest plugin |
| W4 | 本地 Qwen-VL + provider chain + 50 case 验收 + 文档 |

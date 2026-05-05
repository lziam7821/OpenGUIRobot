# OpenGUIRobot · v0.1 PRD「能跑通」

| 字段 | 内容 |
|---|---|
| 版本号 | v0.1.x |
| 版本主题 | 能跑通（Hello World） |
| 周期 | 4–6 周 |
| 上游依据 | `ARCHITECTURE.md` §14 v0.1 |
| 文档状态 | Draft |

---

## 1. 版本概述

v0.1 是**最小可运行版本（MVP）**，目标只有一个：让一名开发者在自己的笔记本上、用一句自然语言描述意图，跑出一个真实 App 的端到端测试，并把结果固化成可复用的 Python 代码。

**一句话 demo**：

```bash
ogr explore "启动电商 App、搜索 '无线耳机'、选第一个商品、加入购物车" \
    --case e_commerce.add_to_cart --device pixel-8
```

执行后产物：

- `tests/generated/e_commerce/add_to_cart.py`（可被 pytest 直接跑）
- `evidence/<case>/<run>/`（截图、DOM、决策日志）

---

## 2. 用户画像与场景

| 画像 | 期望 | 上手成本预算 |
|---|---|---|
| 测试工程师（早期试用） | 想感受"自然语言驱动测试"是否真的能用 | 30 分钟内跑通 demo |
| 平台研发（未来贡献者） | 想看 Code-as-Action 怎么落地、值不值得贡献 | 阅读 1 小时即理解架构 |

**主要场景**：

1. **首跑（Explore）**：开发者写一个 case YAML，触发 `ogr explore` → 拿到一份固化代码
2. **回放（Regression Mock）**：用 pytest 直接跑固化代码，**不应再调用任何 LLM**
3. **失败定位**：任意一步失败时，能从 `evidence/` 找到截图和 DOM 重现现场

---

## 3. 范围（In / Out）

### In（必须做）

- L0 Driver：**Android（Appium UiAutomator2）+ iOS（Appium XCUITest）**
- L1 Skill：
  - Locator 两层：规则层（accessibility id / 资源 id / 精确文本）+ 视觉层（Qwen-VL grounding 调用云端 API）
  - 简易 Assertor：基于元素存在性 + OCR 文本匹配
- L2 Action：Code-as-Action 最小闭环（生成 → 沙箱 → 固化）
- 沙箱：Tier 0（AST 导入白名单）+ Tier 1（Linux bwrap / macOS sandbox-exec）
- LLM：OpenAI 适配器 + Anthropic 适配器
- CLI：`ogr explore` / `ogr replay` / `ogr doctor`
- 单设备、单进程（无任务调度）
- 一个完整 demo（电商搜索→加购）

### Out（不在本版本）

- 弹窗自愈、截图相似度兜底（v0.2）
- 知识库与操作图谱（v0.2 / v0.3）
- 多设备、并发、设备注册中心（v0.3）
- Web Dashboard、多租户（v0.4）
- 鸿蒙 driver（v0.3）
- 本地 Qwen-VL 部署（v0.2，本版只支持云端 API）

---

## 4. 功能需求（FR）

### FR-1 自然语言用例描述

- 用例文件格式：`tests/cases/<group>/<name>.case.yaml`
- 必填字段：`case_id`、`title`、`intent`、`platforms`
- 选填字段：`env`、`assertions`、`budget_usd`、`timeout_s`

### FR-2 Code-as-Action 探索

- 入口：`ogr explore <case_id> --device <id>`
- 流程：解析意图 → Plan 拆步骤 → 单步生成代码 → 沙箱执行 → 验证 → 固化
- 中断恢复：单步失败立即终止本次探索，**不进自愈**（自愈在 v0.2）

### FR-3 沙箱执行

- 默认走 bwrap（Linux）/ sandbox-exec（macOS）
- 强制 AST 静态校验：禁止 `eval/exec/compile/__import__/open`
- 全流程超时（默认 600s）+ 单步超时（默认 30s）

### FR-4 固化与回放

- 探索成功 → 自动生成 `tests/generated/<group>/<case>.py`
- 文件头自动写入元数据（生成时间、case_id、来源 prompt 哈希）
- `ogr replay <case_id>` 直接跑固化代码（pytest invoke）
- **必须保证**：replay 路径 0 token 消耗

### FR-5 LLM 适配器

- 内置：`openai` / `anthropic`
- 配置：`~/.openguirobot/config.yaml` 或环境变量
- 切换：`--llm openai:gpt-4o` / `--llm anthropic:claude-sonnet`
- 失败重试：tenacity 指数退避，3 次为限

### FR-6 视觉 grounding

- 通过 Qwen-VL-Max（DashScope）或 GPT-4o 云端 API
- 调用频次：仅在规则层失败后兜底
- 单次调用记录：image hash、prompt、bbox、cost

### FR-7 证据落盘

- 每次 explore 在 `evidence/<case>/<timestamp>/` 下产出：
  - `step-NNN-before.png`、`step-NNN-after.png`
  - `step-NNN-dom.xml`
  - `step-NNN-llm.jsonl`（请求 + 响应 + cost）
  - `summary.json`（步骤结果、总耗时、总成本）

---

## 5. 非功能需求（NFR）

| 维度 | 指标 |
|---|---|
| 单 demo 探索成功率 | ≥ 80% |
| 单 demo 探索耗时 | ≤ 5 分钟 |
| 单 demo 探索成本 | ≤ 2 USD |
| 回放（regression）耗时 | ≤ 60 秒 |
| 回放成本 | 0 USD（视觉 grounding 不参与回放） |
| Cold start 文档 | 30 分钟内能跑通 demo |
| 平台支持 | macOS 14+ / Ubuntu 22.04+ |
| Python 版本 | 3.11+ |

---

## 6. 验收标准

- [ ] 一份"30 分钟上手"教程能让陌生开发者跑通 demo
- [ ] 单 demo 连续跑 10 次，至少 8 次探索成功 + 10 次回放全部成功
- [ ] `ogr doctor` 能自动检测 appium / adb / xcrun / bwrap 是否就绪
- [ ] 单测覆盖率 ≥ 70%（核心模块 ≥ 85%）
- [ ] CI 通过：lint（ruff）+ type（mypy）+ test（pytest）
- [ ] 文档：`README.md` + `docs/QUICKSTART.md` + `docs/CLI.md`

---

## 7. 依赖与风险

| 项 | 描述 | 缓解 |
|---|---|---|
| Appium 2 driver 安装 | 用户机器上 driver 缺失时无法跑 | `ogr doctor` + 安装脚本 |
| iOS 真机签名 | WDA 真机需要开发者证书 | 文档明确步骤，先模拟器 demo |
| LLM API 网络 | 国内访问 OpenAI 受限 | 默认推荐 Anthropic + DashScope；提供 base_url 配置 |
| 视觉模型成本 | 单次 grounding 0.01–0.05 USD | 规则层先行，视觉只兜底 |
| bwrap macOS 缺失 | bwrap 仅 Linux 可用 | macOS 自动切到 sandbox-exec |

---

## 8. 时间安排

| 周 | 里程碑 |
|---|---|
| 第 1 周 | 仓库骨架、CI、Appium driver 包装 |
| 第 2 周 | Locator 规则层 + 视觉层 + 简易 Assertor |
| 第 3 周 | Code-as-Action 单步闭环（不含固化） |
| 第 4 周 | 沙箱（bwrap/sandbox-exec）+ AST 白名单 |
| 第 5 周 | 固化器 + replay 路径 + pytest invoke |
| 第 6 周 | 一个完整 demo 跑通 + 文档 + bug 收尾 |

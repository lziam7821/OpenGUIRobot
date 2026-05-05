# OpenGUIRobot · v0.2 技术文档

> 配合 [`PRD.md`](./PRD.md)。架构总览见 [`ARCHITECTURE.md`](../../../ARCHITECTURE.md)。

---

## 1. 技术目标

- 在 v0.1 的 Driver / Skill / Action 基础上，加入**自愈四层防护**
- 引入异步任务系统的雏形（Arq）
- 视觉模型从纯云端扩展为本地 + 云端 fallback
- 把"知识管理"以最小可运行形态（KB 规范 + lint）加入仓库
- pytest 插件让用户用熟悉工具跑回归

---

## 2. 模块清单与工作分解

| 模块 | 包 | 工作 | 估时（人天） |
|---|---|---|---|
| Healer Skill | `openguirobot.skill.healer` | 四层防护策略 + 决策日志 | 6 |
| Image diff | `openguirobot.skill.image_diff` | phash / SSIM / 阈值校准 | 2 |
| Async Assertor | `openguirobot.skill.assertor_async` | Arq 任务 + 通用断言集 | 4 |
| OCR | `openguirobot.vision.ocr` | rapidocr-onnxruntime 集成 + 错别字字典 | 2 |
| Vision Provider Chain | `openguirobot.vision.chain` | local → cloud fallback | 3 |
| Local Vision Server | `openguirobot.vision.local_vllm` | vLLM 启动脚本 + 健康检查 | 3 |
| KB Schema | `openguirobot.memory.kb` | front matter 解析 + lint | 3 |
| pytest plugin | `openguirobot.testing.pytest_plugin` | options + fixtures + collection | 3 |
| Cost Budget | `openguirobot.obs.cost` | 累计预算 + 软硬阈值 | 2 |
| Arq Worker | `openguirobot.jobs.worker` | 队列 + Redis 默认配置 + 单机回退 | 3 |
| 文档 | `docs/` | HEALING / KB-WRITING / PYTEST / VISION-LOCAL | 2 |

合计：约 33 人天。

---

## 3. 关键技术决策

### 3.1 自愈作为 Skill 而不是 Orchestrator

每一步执行后，由 `runtime.session.step()` 包裹决定是否调 Healer。这样：

- 固化代码不感知自愈（仍是 `s.tap(locate(...))`）
- 自愈可后续替换为 LLM heal（v0.4）而不影响固化代码

### 3.2 截图相似度走 phash 而不是 SSIM 默认

理由：

- phash 极快（< 5ms），适合每步触发
- SSIM 慢（50–200ms）但更精确，作为冲突时的二次确认
- 提供 `image_diff.algo` 配置开关

### 3.3 Arq 引入但保留单机进程内回退

`OGR_JOBS_BACKEND=inproc` 时不依赖 Redis。这是为了让试用者无需起 Redis 就能用异步断言。

### 3.4 KB lint 进 CI 但不卡 explore

- `ogr kb lint --strict` 用于 CI
- 普通 `ogr explore` 不强制 KB 通过 lint，避免阻塞实验

### 3.5 vLLM Server 与主进程解耦

vLLM 启动慢（数十秒）、占资源大。用 `ogr vision serve` 起独立进程，主进程通过 OpenAI-compatible API 访问。

---

## 4. 接口与数据模型

### 4.1 Healer 接口

```python
class HealResult(TypedDict):
    healed: bool
    layer: Literal["popup", "similarity", "context", "fallback"] | None
    actions_taken: list[str]
    duration_ms: int

class Healer(Protocol):
    def heal(self, ctx: StepContext) -> HealResult: ...
```

### 4.2 Healer 决策日志

`evidence/<case>/<run>/decisions.jsonl`：

```json
{"step":"step-007","layer":"popup","strategy":"top_right_close","success":true,"duration_ms":312}
{"step":"step-008","layer":"similarity","before_phash":"...","after_phash":"...","ratio":0.21,"success":true}
```

### 4.3 异步断言 Job

```python
@arq.task
async def run_assertion(ctx, case_id: str, step_id: str, screenshot_path: str,
                        spec: AssertionSpec) -> AssertionResult: ...
```

### 4.4 KB 文件 front matter 校验 schema

```python
class KBFrontMatter(BaseModel):
    module: str
    case: str | None = None
    last_verified: date
    verified_versions: list[str]
    confidence: Literal["high","medium","low","unverified"]
    owners: list[str] = Field(min_length=1)
    deeplinks: list[str] = []
    related_skills: list[str] = []
    tags: list[str] = []
```

### 4.5 pytest 插件

```python
# conftest.py 不需要写任何东西，安装包后自动启用
@pytest.fixture
def ogr_driver(request) -> Driver: ...

@pytest.fixture
def ogr_case(request) -> TestCase: ...

# pytest CLI
pytest --ogr-mode replay --ogr-cases tests/generated/p0/**
```

### 4.6 Vision Provider Chain 配置

```yaml
vision:
  chain:
    - provider: local_qwen_vl
      endpoint: http://127.0.0.1:8000/v1
      timeout_s: 5
    - provider: dashscope_qwen_vl
      api_key_env: DASHSCOPE_API_KEY
      timeout_s: 10
    - provider: openai_vision
      model: gpt-4o-mini
      timeout_s: 15
```

---

## 5. 部署与运行形态

### 5.1 单机最小部署

```bash
ogr doctor                       # 检查 appium / adb / xcrun / bwrap
ogr vision serve --gpu 0 &       # 可选：本地 Qwen-VL
appium &                         # 可选：起 Appium server
ogr explore <case_id>
```

### 5.2 加 Redis（推荐）

```bash
docker run -d --name ogr-redis -p 6379:6379 redis:7
ogr worker start --jobs codegen,heal,assert
ogr explore <case_id>            # 自动用 Redis broker
```

---

## 6. 测试策略

| 类型 | 范围 |
|---|---|
| 单测 | 各 Healer 层独立可 mock |
| 集成 | 注入弹窗 / 注入元素错位 / 注入网络抖动 三组故障 |
| 端到端 | 50 case 跑 5 天的 nightly job |
| 性能 | phash / SSIM 时延 benchmark；vLLM 推理时延 |
| 负载 | 单设备 100 个连续 case，观察 OOM / fd 泄漏 |

---

## 7. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 弹窗策略与具体 App 强耦合 | 暴露 `case.healer.custom` 钩子；社区贡献 App profile |
| phash 对动态背景误判 | 提供 ROI mask（用户指定要比对的区域） |
| Arq + Redis 引入失败时不可用 | inproc 模式作为兜底 |
| Qwen-VL 显存不够 | 提供 7B 量化版（INT4）作为低显存选项 |
| KB lint 太严导致用户抵触 | 默认 warning-only，CI 模式下才 strict |

---

## 8. 工作分解结构（WBS）

```
W1  Healer 框架 + Layer 1
    ├─ Healer Protocol + decisions.jsonl
    ├─ 弹窗 5 策略实现
    └─ 注入式集成测试

W2  Layer 2 + Layer 3 + 异步断言
    ├─ image_diff (phash / SSIM)
    ├─ 上下文记忆决策
    ├─ Arq + 通用断言库
    └─ OCR 错别字字典

W3  KB + pytest plugin + Budget
    ├─ KB front matter schema + lint
    ├─ pytest plugin（options/fixtures）
    └─ 成本预算与告警

W4  本地视觉 + 验收
    ├─ vLLM 启动脚本 + provider chain
    ├─ 50 case 跑 5 天
    └─ 文档：HEALING / KB / PYTEST / VISION-LOCAL
```

---

## 9. 留给 v0.3 的开放问题

- 自愈成功的策略需要沉淀到操作图谱里，目前只在 jsonl
- KB 仍需手工写 L0 / L1，没有自动反哺
- 所有这些只在单设备上验证，没有调度
- 没有"路径引导"，复杂 case 仍可能跑偏

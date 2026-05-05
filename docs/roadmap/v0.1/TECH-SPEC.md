# OpenGUIRobot · v0.1 技术文档

> 配合 [`PRD.md`](./PRD.md) 阅读。共享概念见仓库根 [`ARCHITECTURE.md`](../../../ARCHITECTURE.md)。

---

## 1. 技术目标

- 落地 Driver / Skill / Action 三层最小骨架
- 实现"自然语言 → 代码 → 固化"的可重复闭环
- 给后续版本留下可扩展的接口与目录

---

## 2. 模块清单与工作分解

| 模块 | 包 | 主要类 / 文件 | 估时（人天） |
|---|---|---|---|
| CLI | `openguirobot.cli` | `main.py`、`commands/explore.py` `replay.py` `doctor.py` | 3 |
| Driver Base | `openguirobot.driver.base` | `Driver` Protocol、`KeyCode`、`DomTree` | 2 |
| Android Driver | `openguirobot.driver.android` | `AndroidDriver` | 4 |
| iOS Driver | `openguirobot.driver.ios` | `IOSDriver` | 4 |
| Locator Skill | `openguirobot.skill.locator` | 规则层 + 视觉层 | 5 |
| Assertor Skill | `openguirobot.skill.assertor` | 元素存在 + OCR 比对 | 3 |
| Action Codegen | `openguirobot.action.codegen` | Plan + 单步生成 | 5 |
| AST Guard | `openguirobot.action.ast_guard` | 导入白名单、禁用 builtin | 2 |
| Sandbox | `openguirobot.action.sandbox` | bwrap / sandbox-exec / 资源限制 | 4 |
| Compiler | `openguirobot.action.compiler` | 固化模板 + black 格式化 | 2 |
| LLM Adapter | `openguirobot.llm` | `openai_adapter.py` `anthropic_adapter.py` | 3 |
| Vision Adapter | `openguirobot.vision` | `qwen_vl_dashscope.py` `gpt4o.py` | 3 |
| Case Loader | `openguirobot.cases` | YAML schema + pydantic models | 2 |
| Evidence Writer | `openguirobot.obs.evidence` | 截图、DOM、LLM call 落盘 | 2 |

合计：约 44 人天（不含联调与 bug fix）。

---

## 3. 关键技术决策

### 3.1 LLM Plan 与 Codegen 拆成两步

不直接让 LLM 一次产出完整脚本，而是：

1. **Plan**：一次调用，产出 N 个原子步骤（自然语言）
2. **Codegen**：每个步骤一次调用，生成对应的 Python 代码片段（5–15 行）

理由：

- 单步代码短、可校验
- 失败可以从中间步骤重试，不必从头
- 给 v0.2 自愈留出步骤级粒度的 hook

### 3.2 Locator 不做 LLM 调用，只做向量 + 规则

v0.1 的视觉层是"用 Qwen-VL 做 grounding"，但封装在 Locator 内部，不让 Codegen 直接产出 grounding 调用。理由：

- Codegen 只产出 `locate("搜索按钮")`，至于内部走规则还是视觉，由运行时决定
- 这样固化代码里的 `locate("...")` 调用不会绑死实现，未来切换到全 DOM 也无需改固化代码

### 3.3 Sandbox 走 bwrap/sandbox-exec，不强依赖 Docker

理由见 `ARCHITECTURE.md` §10.1。v0.1 直接用系统级方案，零额外服务。

### 3.4 不做 KB / 操作图谱

v0.1 不引入图谱与 KB，避免过早抽象。固化代码本身就是知识载体。

### 3.5 LLM Cost 在 v0.1 就要打 trace

哪怕 v0.1 没有 Dashboard，所有 LLM call 都要写到 `evidence/.../step-NNN-llm.jsonl`，包含 `model / tokens_in / tokens_out / cost_usd / latency_ms`。这是后续成本分析的源头。

---

## 4. 接口与数据模型

### 4.1 CLI

```bash
ogr doctor                              # 环境自检
ogr explore <case_id>                   # 探索并固化
  --device <udid|name>
  --llm <provider:model>
  --budget-usd <n>
  --timeout-s <n>
ogr replay <case_id> [--device <udid>]  # 跑固化脚本
ogr cases list
ogr cases show <case_id>
```

### 4.2 用例 schema（pydantic）

```python
class TestCase(BaseModel):
    case_id: str                       # e_commerce.shopping_cart.add_to_cart
    title: str
    intent: str
    platforms: list[Platform]          # ["android", "ios"]
    priority: Literal["p0","p1","p2","p3"] = "p2"
    budget_usd: float = 1.5
    timeout_s: int = 600
    env: dict = Field(default_factory=dict)
    assertions: list[AssertionSpec] = Field(default_factory=list)
```

### 4.3 Driver Protocol

复用 `ARCHITECTURE.md` §3.1 的 Protocol，v0.1 必须全部实现 except：

- `dump_dom()` 在 iOS 实模式下返回 WDA accessibility tree
- `swipe()` 时长默认 300ms

### 4.4 Locator 接口

```python
class ElementMatch(TypedDict):
    bbox: tuple[int, int, int, int]    # x1,y1,x2,y2
    locator_kind: Literal["rule","vision"]
    confidence: float                  # 0..1
    debug: dict

def locate(query: str, dom: DomTree, screenshot: bytes,
           runtime: LocatorRuntime) -> ElementMatch: ...
```

### 4.5 Code-as-Action 生成示例

每步 Codegen prompt 输出严格 JSON：

```json
{
  "code": "s.tap(locate('搜索入口'))",
  "expected_observation": "搜索框获得焦点，键盘弹起",
  "rollback_hint": "按返回键回到首页"
}
```

### 4.6 固化模板

```python
# tests/generated/{group}/{case}.py（v0.1 模板）
"""
Auto-generated from case: {{ case.case_id }}
Generated at: {{ generated_at }} by openguirobot v0.1.x
DO NOT edit by hand.
"""
import pytest
from openguirobot.runtime import session, locate, assert_visual

@pytest.mark.openguirobot(case_id="{{ case.case_id }}")
def test_{{ case.snake_name }}(driver):
    with session(driver, case_id="{{ case.case_id }}") as s:
{% for step in steps %}
        # {{ step.intent }}
        {{ step.code }}
{% endfor %}
```

---

## 5. 部署与运行形态

v0.1 不做服务化部署。运行方式：

```bash
pip install openguirobot
ogr doctor
appium &                # Appium 2 server 由用户启动
ogr explore <case_id>   # 直接命令行
```

---

## 6. 测试策略

| 类型 | 框架 | 范围 | 目标覆盖 |
|---|---|---|---|
| 单测 | pytest | 各模块（mock LLM / mock driver） | ≥ 70%；核心 ≥ 85% |
| 集成测试 | pytest + 模拟器 | Android emulator demo / iOS simulator demo | 一份金标 demo CI 必须通过 |
| 回归 | pytest 跑固化代码 | 在模拟器上跑 demo | 10 次连续 100% |
| Lint / Type | ruff + mypy | 全仓 | 0 error |

---

## 7. 风险与缓解

| 风险 | 概率 | 缓解 |
|---|---|---|
| Appium 2 driver 升级导致 API 不兼容 | 中 | pin 住 driver 版本到 minor，CI 跑 nightly |
| Codegen 生成代码无法通过 AST 白名单 | 中 | prompt 中明确允许 import 列表；预置失败 → 提示用户重试 |
| iOS 真机签名复杂导致试用者放弃 | 高 | demo 默认用模拟器 |
| LLM 网络不稳定 | 中 | tenacity 重试 + 多 provider fallback |
| sandbox 启动失败（macOS sandbox-exec profile 写错） | 中 | 默认 profile 内置 + `ogr doctor` 模拟 dry-run |

---

## 8. 工作分解结构（WBS）

按 PRD §8 的 6 周周期：

```
W1  仓库骨架 + CI + Driver
    ├─ pyproject.toml 与依赖锁定
    ├─ ruff/mypy/pytest 配置
    ├─ Driver Protocol + Android/iOS 实现
    └─ ogr doctor

W2  Skill 层
    ├─ Locator 规则层 + 视觉层
    ├─ Assertor（元素存在 + OCR）
    └─ session() runtime 上下文

W3  Action / Codegen
    ├─ Plan 模板 + 单步 Codegen
    ├─ LLM Adapter（openai / anthropic）
    └─ Vision Adapter（DashScope Qwen-VL）

W4  Sandbox
    ├─ AST Guard
    ├─ bwrap profile + sandbox-exec profile
    └─ 资源限制 + 超时

W5  固化 + Replay
    ├─ Compiler + jinja2 模板
    ├─ ogr replay
    └─ Evidence Writer

W6  Demo + 文档 + 收尾
    ├─ 电商 demo（搜索→加购）
    ├─ QUICKSTART / CLI / Architecture 摘要
    └─ 第 1 个 release（v0.1.0）
```

---

## 9. v0.1 完成后的开放问题（留给 v0.2）

- 弹窗 / 网络异常导致探索失败时，自愈策略缺失
- Locator 视觉层调用频繁导致成本不稳定
- 没有断言能力之外的"页面健康度"判断
- 没有知识沉淀，每个 case 重头探索
- Qwen-VL 仅云端，无法离线

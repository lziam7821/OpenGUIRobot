# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

OpenGUIRobot is currently in **architectural design phase** — no source code exists yet. The repo contains only design documents. v0.1 implementation begins May 2026 (4–6 week timeline).

Key docs:
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — canonical system design (~12,000 words), single source of truth
- [`docs/roadmap/v0.1/PRD.md`](docs/roadmap/v0.1/PRD.md) — v0.1 acceptance criteria
- [`docs/roadmap/v0.1/TECH-SPEC.md`](docs/roadmap/v0.1/TECH-SPEC.md) — v0.1 WBS, data models, risks
- [`docs/roadmap/README.md`](docs/roadmap/README.md) — version roadmap overview

## What This Project Builds

An LLM-powered GUI automation test platform for iOS, Android, HarmonyOS, and Web. Core design constraints:

1. **AI is a tool, not a judge** — deterministic code handles certain tasks; LLM only for uncertain operations
2. **Zero-token regression** — generated test scripts run in CI without any LLM calls
3. **Offline capable** — all core features must support local models + local storage

## Planned Architecture (6-Layer Stack)

```
L6 · Business Map Plugin    (Optional: template + Plan + ReAct)
L5 · Device & Job           (Registry, APScheduler + Arq + PostgreSQL pull queue)
L4 · Orchestrator           (Explore / Heal / Regression modes)
L3 · Memory Layer           (Tiered KB in docs/kb/, KuzuDB graph, Qdrant vectors)
L2 · Action Layer           (Codegen → Sandbox execution → Compiler → Fixed pytest)
L1 · Skill Layer            (Locator, Assertor, Healer, EnvManager)
L0 · Driver Layer           (Appium 2 + Playwright unified Driver Protocol)
```

### L0 — Driver Layer
Unified `Driver` Protocol over: Appium UiAutomator2 (Android), Appium WebDriverAgent + pymobiledevice3 (iOS), HDC CLI (HarmonyOS), Playwright (Web).

### L1 — Skill Layer
- **Locator**: 3-tier element finding — rule layer (accessibility ID / resource ID / exact text) → semantic layer (DOM embeddings + vector search) → vision layer (Qwen-VL grounding fallback)
- **Assertor**: generic visual checks (black/white screen, overlap, OCR typos) + business assertions declared in YAML cases
- **Healer**: 4-layer recovery — popup dismissal → screenshot similarity (imagehash.phash) → context memory (rollback/skip) → AI local code regeneration
- **EnvManager**: network simulation, performance metrics, device state (cache clear, reinstall, reboot)

### L2 — Action Layer (Code-as-Action)
LLM breaks intent → N atomic plan steps → one code generation call per step (5–15 lines each, not full scripts) → AST static analysis + import whitelist sandbox → bwrap (Linux) / sandbox-exec (macOS) execution → black + Jinja2 compiler → fixed pytest file.

Sandbox `allowed_imports` restricted to `openguirobot.skills.*`, `openguirobot.driver.*`, `re`, `json`, `typing`. Banned builtins: `eval`, `exec`, `compile`, `__import__`, `open`.

### L3 — Memory Layer
- **Tiered KB** (Markdown in `docs/kb/`): L0 ≤200 lines (glossary, recent failures), L1 ≤2000 lines (module overviews), L2 unlimited (case flows, screenshots). All files have YAML front matter: `module`, `case`, `last_verified`, `confidence`, `owners`, `tags`.
- **Operation Graph**: KuzuDB embedded — nodes: Page, Action, Path, Anchor; edges: triggers, prev/next, variant_of, regressed_from.
- **Session Cache**: Redis or in-memory LRU.

### L4 — Orchestrator Modes
- **Explore**: NL intent → Plan → Codegen → Sandbox → Verify → Fixturize → `tests/generated/`
- **Regression**: Runs `tests/generated/` scripts, zero LLM calls (except visual assertions)
- **Heal**: Regenerates code for failed regression steps locally + optional PR

### L5 — Device & Job
- Device state machine: Discovered → Registered → Idle / Busy / Faulted
- **APScheduler**: cron/interval triggers for scheduled regressions and maintenance
- **Arq** (not Celery): async task queue for codegen/heal, Redis broker
- **PostgreSQL pull queue**: devices long-poll `jobs` table with `FOR UPDATE SKIP LOCKED`

## Planned Tech Stack

| Layer | Key Libraries |
|---|---|
| L0 Driver | `Appium>=4.0`, `Playwright>=1.42`, `adbutils>=2.4`, `pymobiledevice3>=3.0` |
| L1 Skill | `Pillow`, `opencv-python-headless`, `RapidOCR`, `sentence-transformers`, `vllm` |
| L2 Action | `pydantic`, `jinja2`, `RestrictedPython`, `black`, `tenacity` |
| L3 Memory | `kuzu>=0.4`, `qdrant-client>=1.9`, `SQLAlchemy`, `mistune`, `watchdog` |
| L5 Device | `apscheduler>=3.10`, `arq>=0.25`, `FastAPI`, `httpx`, `websockets` |
| LLM/Vision | `openai`, `anthropic`, `dashscope` |
| Observability | OpenTelemetry stack, `prometheus-client`, `structlog`, `loguru` |
| Testing | `pytest`, `pytest-xdist`, `pytest-asyncio`, `allure-pytest` |
| Frontend | React 18 + TypeScript 5 + Umi 4 (`@umijs/max`), Ant Design 5 + ProComponents, pnpm 9 |

**Python 3.11+ required.**

## Planned Commands (post-v0.1)

```bash
# Install
pip install -e ".[test,local-vision]"

# CLI usage
ogr doctor                          # environment check
ogr explore "<NL intent>" --case <case_id> --device <device_id>
ogr replay <case_id> --device <device_id>

# Testing
pytest tests/ -v --cov=openguirobot
pytest tests/generated/path/to/test.py  # single test

# Lint & type check
ruff check openguirobot/
mypy openguirobot/
```

## Planned Directory Layout

```
openguirobot/           # Python package root
├── cli/                # ogr entry point (explore, replay, doctor)
├── driver/             # L0: base.py Protocol + android/ios/web/harmony
├── skill/              # L1: locator, assertor, healer, env_manager
├── action/             # L2: codegen, sandbox, compiler, evidence
├── memory/             # L3: kb, graph, cache
├── orchestrator/       # L4: run modes
├── device/             # L5: registry, scheduler
├── llm/                # OpenAI / Anthropic / DashScope adapters
├── vision/             # Qwen-VL (local/cloud), GPT-4o adapters
├── obs/                # OpenTelemetry, evidence writer
├── api/                # FastAPI backend
└── jobs/               # APScheduler + Arq workers
tests/
├── cases/              # Case definitions (YAML)
└── generated/          # Auto-generated pytest scripts (committed, 0-token regression)
docs/kb/
├── L0/                 # ≤200-line summary files
├── L1/                 # ≤2000-line module overviews
└── L2/                 # Unlimited detailed case flows
evidence/               # Per-run artifacts (screenshots, DOM, LLM cost logs)
web/                    # React dashboard
```

## Test Case Schema

```yaml
case_id: e_commerce.shopping_cart.add_to_cart
platforms: [android, ios]
budget_usd: 1.5
timeout_s: 600
env:
  network: wifi
  test_account: ${SECRET:ecom_acct_a}
assertions:
  - kind: visual
    desc: Cart badge shows +1
```

## User Config (~/.openguirobot/config.yaml)

```yaml
llm:
  default_provider: anthropic:claude-sonnet
vision:
  default_provider: qwen_vl_local   # or dashscope / gpt4o
  local:
    backend: vllm
    model: Qwen/Qwen2.5-VL-7B-Instruct
    endpoint: http://localhost:8000/v1
sandbox:
  tier: bwrap                        # bwrap | sandbox-exec | docker
  cpu_limit: 1
  memory_limit_mb: 512
  step_timeout_s: 30
  total_timeout_s: 600
secrets_provider: env                # env | vault | aws-secrets-manager
```

## Version Roadmap

| Version | Focus | Key Deliverable |
|---|---|---|
| v0.1 | MVP ("能跑通") | Single-device CLI demo, Code-as-Action loop, basic sandbox |
| v0.2 | Stable ("稳") | 4-layer healing, local Qwen-VL, KB L0/L1 |
| v0.3 | Scalable ("可规模") | Operation graph, device registry, HarmonyOS |
| v0.4 | Enterprise pilot | Heal+PR, Dashboard, multi-tenant, OTel |
| v1.0 | LTS | Full docs, all adapters, security audit |
| v1.x | High-end | Business maps, video→graph, IDE plugins |

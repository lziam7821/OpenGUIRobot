---
module: core
case: glossary
last_verified: 2026-05-01
confidence: high
owners: [platform-team]
tags: [reference]
---

# Glossary

Key terms used across all OpenGUIRobot knowledge base documents.

## Terms

**Code-as-Action** — The L2 approach where each test step is expressed as a short Python snippet (5–15 lines) rather than a full script. The snippet is validated by AST Guard, executed in a sandbox, and compiled into a fixed pytest file.

**Explore mode** — The online mode where the orchestrator generates and executes steps with live LLM calls. Output is a solidified pytest file stored under `tests/generated/`.

**Replay mode** — The offline mode that runs solidified pytest files with zero LLM calls. Used in CI for regression testing.

**Healer** — The L1 recovery component. Tries 4 layers (popup dismissal → screenshot similarity → context memory → fallback) to recover from a failed step before escalating.

**phash** — Perceptual hash (imagehash library). Used by the Healer's Layer 2 to compare screenshots and detect whether the screen changed significantly after a recovery action.

**Budget** — Per-case LLM spend cap (USD). Configured in `case.budget_usd`. The `CostBudget` tracker warns at ≥80% and terminates at ≥100%.

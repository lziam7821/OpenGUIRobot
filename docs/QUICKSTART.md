# OpenGUIRobot — 30-Minute Quickstart

This guide gets you from zero to a successful e-commerce test on an Android emulator.

## Prerequisites

| Tool | Install | Version |
|---|---|---|
| Python | [python.org](https://python.org) | ≥ 3.11 |
| Node.js | [nodejs.org](https://nodejs.org) | ≥ 18 |
| Android Studio | [developer.android.com](https://developer.android.com/studio) | any |
| bubblewrap (Linux) | `sudo apt install bubblewrap` | any |

## Step 1 — Install OpenGUIRobot

```bash
git clone https://github.com/your-org/OpenGUIRobot.git
cd OpenGUIRobot
pip install -e ".[test]"
```

## Step 2 — Install Appium

```bash
npm install -g appium@next
appium driver install uiautomator2
```

## Step 3 — Set API keys

```bash
export ANTHROPIC_API_KEY="sk-ant-..."   # or OPENAI_API_KEY
export DASHSCOPE_API_KEY="sk-..."       # for Qwen-VL vision (optional)
```

Or create `~/.openguirobot/config.yaml`:
```yaml
llm:
  default_provider: anthropic:claude-sonnet-4-5
vision:
  default_provider: qwen_vl_dashscope
```

## Step 4 — Start an Android emulator

In Android Studio: **Device Manager → Create Device → Start**.

Or via command line:
```bash
emulator -avd Pixel_6_API_33 &
```

## Step 5 — Verify environment

```bash
ogr doctor
```

All required checks should show ✓. Appium server must be running:
```bash
appium &
```

## Step 6 — Run the demo exploration

```bash
ogr explore e_commerce.add_to_cart --device emulator-5554
```

This will:
1. Generate a plan (LLM call)
2. Execute each step in a sandbox
3. Capture screenshots and DOM at each step
4. Write `tests/generated/e_commerce/add_to_cart.py`
5. Write evidence to `evidence/e_commerce.add_to_cart/<timestamp>/`

Expected output:
```
ogr explore e_commerce.add_to_cart | device=emulator-5554 | platform=android
  budget=$2.00  timeout=300s

Generating test plan…
┌─ Generated Plan ──────────────────────────────┐
│  1  Launch app       Press back               │
│  2  Tap search box   Press back               │
│  …                                            │
└───────────────────────────────────────────────┘

Step 1/5: Launch app
  Code: s.launch_app('com.example.ecommerce')
  ✓ App appeared in foreground
…
Solidifying to pytest script…
  Written: tests/generated/e_commerce/add_to_cart.py

Exploration complete in 87.3s | cost=$0.8412
```

## Step 7 — Replay (zero LLM calls)

```bash
ogr replay e_commerce.add_to_cart --device emulator-5554
```

Or run directly with pytest:
```bash
OGR_DEVICE=emulator-5554 OGR_PLATFORM=android \
  pytest tests/generated/e_commerce/add_to_cart.py -v
```

Replay should complete in under 60 seconds with $0.00 LLM cost.

## Troubleshooting

**`adb not found`** — Install Android platform-tools and add to PATH.

**`Appium server not reachable`** — Run `appium` in a separate terminal.

**`bwrap not found` (Linux)** — `sudo apt install bubblewrap`.

**LLM generates invalid JSON** — The adapter retries up to 3 times automatically. If it still fails, try switching `--llm openai:gpt-4o`.

**Vision model not grounding elements** — Check `DASHSCOPE_API_KEY` is set. Use `ogr doctor` to verify.

# ogr CLI Reference

## Global options

```
ogr [--version] [--help] <command>
```

---

## `ogr doctor`

Check that all required tools and API credentials are available.

```bash
ogr doctor [--appium-url URL]
```

| Check | Required |
|---|---|
| Python ≥ 3.11 | ✓ |
| adb on PATH | ✓ |
| Appium server reachable | ✓ |
| bwrap (Linux) / sandbox-exec (macOS) | ✓ |
| ANTHROPIC_API_KEY or OPENAI_API_KEY | one required |
| DASHSCOPE_API_KEY | optional |
| `~/.openguirobot/config.yaml` | optional |

---

## `ogr explore`

Run Code-as-Action exploration: LLM generates and executes UI steps, then solidifies to a pytest script.

```bash
ogr explore <case_id> \
  --device <udid|name> \
  [--llm <provider:model>] \
  [--budget-usd <float>] \
  [--timeout-s <int>] \
  [--platform android|ios] \
  [--tier 0|1] \
  [--cases-dir <path>]
```

| Option | Default | Description |
|---|---|---|
| `--device` | required | Device UDID (e.g. `emulator-5554`, `00008110-...`) |
| `--llm` | from config | `anthropic:claude-sonnet-4-5` or `openai:gpt-4o` |
| `--budget-usd` | from case YAML | Max LLM spend before termination |
| `--timeout-s` | from case YAML | Wall-clock timeout in seconds |
| `--platform` | first in case YAML | Force `android` or `ios` |
| `--tier` | from config | Sandbox tier: `0`=AST only, `1`=OS sandbox |
| `--cases-dir` | `tests/cases` | Path to cases directory |

**Outputs:**
- `tests/generated/<group>/<name>.py` — solidified pytest script
- `evidence/<case_id>/<timestamp>/` — screenshots, DOM, LLM logs, summary

---

## `ogr replay`

Run a previously solidified test script via pytest. Zero LLM tokens consumed.

```bash
ogr replay <case_id> \
  --device <udid|name> \
  [--platform android|ios] \
  [--cases-dir <path>] \
  [--pytest-args "<extra pytest flags>"]
```

**Example:**
```bash
ogr replay e_commerce.add_to_cart --device emulator-5554
ogr replay e_commerce.add_to_cart --device emulator-5554 --pytest-args "--tb=long -s"
```

---

## `ogr cases list`

List all test cases found under the cases directory.

```bash
ogr cases list [--cases-dir <path>]
```

---

## `ogr cases show`

Show full details of a single test case.

```bash
ogr cases show <case_id> [--cases-dir <path>]
```

---

## Environment variables

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `DASHSCOPE_API_KEY` | DashScope (Qwen-VL) API key |
| `OGR_DEVICE` | Device for replay (set by `ogr replay`) |
| `OGR_PLATFORM` | Platform for replay (set by `ogr replay`) |
| `OGR_APPIUM_URL` | Appium server URL (default: `http://localhost:4723`) |

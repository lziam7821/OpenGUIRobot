# OpenGUIRobot

LLM-powered GUI automation test platform for iOS, Android, HarmonyOS, and Web.

**Status: v0.1 — MVP ("能跑通")**

## Quick start

```bash
# 1. Install
pip install -e ".[test]"

# 2. Check environment
ogr doctor

# 3. Start Appium (in a separate terminal)
appium

# 4. Run exploration (generates a pytest script)
ogr explore e_commerce.add_to_cart --device emulator-5554

# 5. Replay with zero LLM calls
ogr replay e_commerce.add_to_cart --device emulator-5554
```

See [docs/QUICKSTART.md](docs/QUICKSTART.md) for the full 30-minute setup guide.

## Key design principles

1. **AI is a tool, not a judge** — deterministic code handles certain tasks; LLM only for uncertain operations
2. **Zero-token regression** — generated scripts run in CI without any LLM calls
3. **Offline capable** — core features support local models and local storage (v0.2+)

## Architecture

```
L4 · Orchestrator       (Explore / Regression modes)
L3 · Memory Layer       (v0.2+)
L2 · Action Layer       (Codegen → AST Guard → Sandbox → Compiler)
L1 · Skill Layer        (Locator, Assertor)
L0 · Driver Layer       (Appium 2: Android + iOS)
```

## Development

```bash
pip install -e ".[dev,test]"

# Run unit tests
pytest tests/unit/ -v --cov=openguirobot

# Lint & type check
ruff check openguirobot/ tests/
mypy openguirobot/
```

## CLI reference

| Command | Description |
|---|---|
| `ogr doctor` | Check that all dependencies are installed |
| `ogr explore <case_id> --device <id>` | Run Code-as-Action exploration |
| `ogr replay  <case_id> --device <id>` | Run solidified test (0 LLM tokens) |
| `ogr cases list` | List all test cases |
| `ogr cases show <case_id>` | Show case details |

Full reference: [docs/CLI.md](docs/CLI.md)

## Configuration

Create `~/.openguirobot/config.yaml`:

```yaml
llm:
  default_provider: anthropic:claude-sonnet-4-5
vision:
  default_provider: qwen_vl_dashscope
sandbox:
  tier: 1          # 1 = bwrap (Linux) / sandbox-exec (macOS)
```

## License

Apache 2.0

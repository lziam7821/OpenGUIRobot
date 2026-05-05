"""Unit tests for config.py."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from openguirobot.config import OGRConfig, load_config


def test_load_config_defaults():
    """With no config file, should return all defaults."""
    cfg = load_config(Path("/nonexistent/path/config.yaml"))
    assert isinstance(cfg, OGRConfig)
    assert cfg.llm.default_provider == "anthropic:claude-sonnet-4-5"
    assert cfg.vision.default_provider == "qwen_vl_dashscope"
    assert cfg.sandbox.tier == 1
    assert cfg.sandbox.step_timeout_s == 30


def test_load_config_from_file(tmp_path):
    config_data = {
        "llm":    {"default_provider": "openai:gpt-4o"},
        "sandbox": {"tier": 0, "step_timeout_s": 60},
    }
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.dump(config_data))

    cfg = load_config(cfg_path)
    assert cfg.llm.default_provider == "openai:gpt-4o"
    assert cfg.sandbox.tier == 0
    assert cfg.sandbox.step_timeout_s == 60
    # Unset fields stay default
    assert cfg.vision.default_provider == "qwen_vl_dashscope"


def test_load_config_empty_file(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("")
    cfg = load_config(cfg_path)
    assert isinstance(cfg, OGRConfig)


def test_sandbox_defaults():
    cfg = OGRConfig()
    assert cfg.sandbox.cpu_limit == 1
    assert cfg.sandbox.memory_limit_mb == 512
    assert cfg.sandbox.total_timeout_s == 600

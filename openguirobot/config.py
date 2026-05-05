"""
Global configuration model for OpenGUIRobot.

Loaded from ~/.openguirobot/config.yaml; all fields have safe defaults
so the tool works out-of-the-box without any config file.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class LLMProviderConfig(BaseModel):
    api_key_env: str = "OPENAI_API_KEY"
    base_url: str | None = None


class LLMConfig(BaseModel):
    default_provider: str = "anthropic:claude-sonnet-4-5"
    openai: LLMProviderConfig = Field(
        default_factory=lambda: LLMProviderConfig(api_key_env="OPENAI_API_KEY")
    )
    anthropic: LLMProviderConfig = Field(
        default_factory=lambda: LLMProviderConfig(api_key_env="ANTHROPIC_API_KEY")
    )


class VisionProviderConfig(BaseModel):
    api_key_env: str = "DASHSCOPE_API_KEY"


class VisionConfig(BaseModel):
    default_provider: str = "qwen_vl_dashscope"  # qwen_vl_dashscope | gpt4o
    dashscope: VisionProviderConfig = Field(
        default_factory=lambda: VisionProviderConfig(api_key_env="DASHSCOPE_API_KEY")
    )
    openai: VisionProviderConfig = Field(
        default_factory=lambda: VisionProviderConfig(api_key_env="OPENAI_API_KEY")
    )


class SandboxConfig(BaseModel):
    tier: int = 1               # 0 = AST only, 1 = bwrap/sandbox-exec
    cpu_limit: int = 1
    memory_limit_mb: int = 512
    step_timeout_s: int = 30
    total_timeout_s: int = 600


class AppiumConfig(BaseModel):
    url: str = "http://localhost:4723"


class OGRConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    appium: AppiumConfig = Field(default_factory=AppiumConfig)
    secrets_provider: str = "env"  # env | vault | aws-secrets-manager
    cases_dir: str = "tests/cases"
    generated_dir: str = "tests/generated"
    evidence_dir: str = "evidence"


_DEFAULT_CONFIG_PATH = Path.home() / ".openguirobot" / "config.yaml"


def load_config(path: Path | None = None) -> OGRConfig:
    """Load config from YAML file, falling back to all defaults if absent."""
    config_path = path or _DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return OGRConfig()
    with config_path.open() as f:
        data = yaml.safe_load(f) or {}
    return OGRConfig.model_validate(data)

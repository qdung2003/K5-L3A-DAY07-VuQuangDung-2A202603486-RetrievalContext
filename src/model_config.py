"""Resolve API configuration from the project .env without mutating the process."""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ModelSettings:
    model: str
    api_key: str | None = field(default=None, repr=False)
    base_url: str = field(default="https://api.openai.com/v1", repr=False)
    reasoning_effort: str = "low"

    def apply(self, config):
        return {**config, "model": self.model, "reasoning_effort": self.reasoning_effort}


def settings_from_env(env_file=None):
    values = {**dotenv_values(env_file or ROOT / ".env", encoding="utf-8-sig"), **os.environ}
    model = (values.get("OPENAI_MODEL") or "").strip()
    if not model:
        raise ValueError("Missing OPENAI_MODEL: set it in the project .env or environment.")
    return ModelSettings(model=model, api_key=values.get("OPENAI_API_KEY") or None,
        base_url=(values.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").strip(),
        reasoning_effort=(values.get("OPENAI_REASONING_EFFORT") or "low").strip())

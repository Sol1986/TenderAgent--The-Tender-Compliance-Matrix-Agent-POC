"""Validated operational settings; never expose provider secrets in API models."""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseModel):
    """Bound this sample demonstration's work and in-memory retention."""

    sample_path: Path = ROOT / "tender.PDF"
    model: str = "gpt-5.6-luna"
    cors_origins: list[str] = ["http://localhost:3000"]
    retention_seconds: int = Field(default=3600, ge=1)
    max_terminal_runs: int = Field(default=10, ge=1, le=100)
    heartbeat_seconds: float = Field(default=15, gt=0, le=60)
    graph_concurrency: int = Field(default=4, ge=1, le=32)
    max_workers: int = Field(default=500, ge=1, le=5000)
    max_input_characters: int = Field(default=2_000_000, ge=1)
    llm_timeout_seconds: float = Field(default=120, gt=0)
    llm_max_retries: int = Field(default=2, ge=0, le=5)

    @field_validator("cors_origins")
    @classmethod
    def exact_origins(cls, values: list[str]) -> list[str]:
        """Reject wildcard or path-bearing origins instead of broadening access."""
        from urllib.parse import urlsplit

        for value in values:
            parsed = urlsplit(value)
            if (
                "*" in value
                or parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
                or parsed.username
            ):
                raise ValueError(
                    "CORS must contain exact HTTP(S) origins without paths."
                )
        return values

    @classmethod
    def from_env(cls) -> "Settings":
        """Load the normal .env and an optional explicit dashboard env file."""
        load_dotenv(ROOT / ".env", override=False)
        if filename := os.getenv("DASHBOARD_ENV_FILE"):
            load_dotenv(filename, override=False)
        mapping = {
            "sample_path": "DEMO_SAMPLE_PATH",
            "model": "OPENAI_MODEL",
            "retention_seconds": "DEMO_RETENTION_SECONDS",
            "max_terminal_runs": "DEMO_MAX_TERMINAL_RUNS",
            "heartbeat_seconds": "DEMO_HEARTBEAT_SECONDS",
            "graph_concurrency": "DEMO_GRAPH_CONCURRENCY",
            "max_workers": "DEMO_MAX_WORKERS",
            "max_input_characters": "DEMO_MAX_INPUT_CHARACTERS",
            "llm_timeout_seconds": "DEMO_LLM_TIMEOUT_SECONDS",
            "llm_max_retries": "DEMO_LLM_MAX_RETRIES",
        }
        values = {
            key: os.environ[env] for key, env in mapping.items() if env in os.environ
        }
        if "DEMO_CORS_ORIGINS" in os.environ:
            values["cors_origins"] = [
                origin.strip()
                for origin in os.environ["DEMO_CORS_ORIGINS"].split(",")
                if origin.strip()
            ]
        return cls.model_validate(values)

"""Validated operational settings; never expose provider secrets in API models."""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseModel):
    """Bound this sample demonstration's work and in-memory retention."""

    sample_path: Path = ROOT / "tender_package"
    output_root: Path = ROOT / "outputs" / "dashboard_runs"
    model: str = "gpt-5.6-luna"
    cors_origins: list[str] = ["http://localhost:3000"]
    retention_seconds: int = Field(default=3600, ge=1)
    max_terminal_runs: int = Field(default=10, ge=1, le=100)
    heartbeat_seconds: float = Field(default=15, gt=0, le=60)
    graph_concurrency: int = Field(default=4, ge=1, le=32)
    llm_timeout_seconds: float = Field(default=120, gt=0)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    max_upload_bytes: int = Field(default=20 * 1024 * 1024, ge=1)
    max_upload_pages: int = Field(default=300, ge=1)
    max_uploads: int = Field(default=100, ge=1)

    def sample_pdf(self) -> Path:
        """Select the exact tender shown in the viewer, regardless of extension case."""
        if self.sample_path.is_file():
            return self.sample_path
        return next(
            (
                path
                for path in self.sample_path.iterdir()
                if path.is_file() and path.name.casefold() == "tender.pdf"
            ),
            self.sample_path / "tender.pdf",
        )

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
            "output_root": "DEMO_OUTPUT_ROOT",
            "model": "OPENAI_MODEL",
            "retention_seconds": "DEMO_RETENTION_SECONDS",
            "max_terminal_runs": "DEMO_MAX_TERMINAL_RUNS",
            "heartbeat_seconds": "DEMO_HEARTBEAT_SECONDS",
            "graph_concurrency": "DEMO_GRAPH_CONCURRENCY",
            "llm_timeout_seconds": "DEMO_LLM_TIMEOUT_SECONDS",
            "llm_max_retries": "DEMO_LLM_MAX_RETRIES",
            "max_upload_bytes": "DEMO_MAX_UPLOAD_BYTES",
            "max_upload_pages": "DEMO_MAX_UPLOAD_PAGES",
            "max_uploads": "DEMO_MAX_UPLOADS",
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

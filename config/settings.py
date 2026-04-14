"""
Central application settings — Ollama only (100% local, zero API cost).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM: Ollama (local, free, no API key needed) ──────────────────────────
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama server base URL",
    )
    # Single model for all agents — qwen2.5:1.5b fits in 8GB RAM with other apps
    ollama_model: str = "qwen2.5:1.5b"
    # Analyst (extraction) — same model to avoid reloading
    ollama_model_analyst: str = "qwen2.5:1.5b"
    # Context window size — 4096 works well within available RAM
    ollama_num_ctx: int = 4096

    # ── External APIs ─────────────────────────────────────────────────────────
    github_token: str = ""
    proxycurl_api_key: str = ""

    # ── Ranking weights (7 dimensions, must sum to 1.0) ───────────────────────
    # JD Match: 25pts, Education: 10pts, Technical Skills: 15pts,
    # Project Quality: 10pts, Experience: 15pts, GitHub: 15pts, LinkedIn: 10pts
    weight_jd_match: float = 0.25
    weight_education: float = 0.10
    weight_technical_skills: float = 0.15
    weight_project_quality: float = 0.10
    weight_experience: float = 0.15
    weight_github: float = 0.15
    weight_linkedin: float = 0.10

    # ── Shortlisting thresholds ───────────────────────────────────────────────
    fast_track_threshold: int = 88
    shortlist_threshold: int = 75
    hold_threshold: int = 50
    top_n_shortlist: int = 10
    role_level: Literal["junior", "mid", "senior", "lead"] = "mid"

    # ── API ───────────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8080

    # ── Output ────────────────────────────────────────────────────────────────
    output_dir: str = "./output"
    log_level: str = "INFO"

    # ── Derived ───────────────────────────────────────────────────────────────
    @property
    def output_path(self) -> Path:
        p = Path(self.output_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def has_llm(self) -> bool:
        """Check if Ollama is reachable (non-blocking quick check)."""
        try:
            import httpx
            resp = httpx.get(f"{self.ollama_base_url}/api/tags", timeout=3.0)
            return resp.status_code == 200
        except Exception:
            return False

    @property
    def weights(self) -> dict[str, float]:
        """All 7 scoring dimensions with their fractional weights (sum=1.0)."""
        raw = {
            "jd_match":         self.weight_jd_match,
            "education":        self.weight_education,
            "technical_skills": self.weight_technical_skills,
            "project_quality":  self.weight_project_quality,
            "experience":       self.weight_experience,
            "github":           self.weight_github,
            "linkedin":         self.weight_linkedin,
        }
        total = sum(raw.values())
        if abs(total - 1.0) > 0.01:
            f = 1.0 / total
            return {k: v * f for k, v in raw.items()}
        return raw

    @property
    def role_weight_modifier(self) -> dict[str, float]:
        """Per-role-level weight adjustments for GitHub & Experience."""
        return {
            "junior": {"github": 1.4, "experience": 0.6, "education": 1.2},
            "mid":    {"github": 1.0, "experience": 1.0, "education": 1.0},
            "senior": {"github": 0.7, "experience": 1.3, "education": 0.8},
            "lead":   {"github": 0.5, "experience": 1.5, "education": 0.7},
        }.get(self.role_level, {"github": 1.0, "experience": 1.0, "education": 1.0})


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

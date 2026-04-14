"""Input schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class JobDescription(BaseModel):
    title: str = "Software Engineer"
    company: str = ""
    raw_text: str = ""
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    min_experience_years: float = 0.0
    domain: str = ""
    seniority: str = "mid"


class ResumeFile(BaseModel):
    """A single resume file. Path is validated lazily to support temp files."""
    path: str
    candidate_id: str = ""

    def model_post_init(self, __context) -> None:
        from pathlib import Path
        p = Path(self.path)
        if not p.exists():
            raise ValueError(f"Resume file not found: {self.path}")

    class Config:
        # Allow mutation so candidate_id can be set after init
        arbitrary_types_allowed = True


class BatchInput(BaseModel):
    jd: JobDescription
    resume_files: list[ResumeFile]
    role_level: str = "mid"
    top_n: int = 10
    output_dir: str = "./output"
    webhook_url: str = ""


class SingleInput(BaseModel):
    jd: JobDescription
    resume_file: ResumeFile
    role_level: str = "mid"
    github_url: str = ""
    linkedin_url: str = ""
    output_dir: str = "./output"

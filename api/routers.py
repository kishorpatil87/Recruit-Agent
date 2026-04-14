"""
API routers — file upload + evaluation endpoints.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import List

import structlog
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from config.settings import get_settings
from pipeline.graph import run_batch, run_single
from schemas.candidate_input import BatchInput, SingleInput, JobDescription, ResumeFile

router = APIRouter()
log = structlog.get_logger(__name__)
settings = get_settings()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}


def _validate_ext(filename: str) -> None:
    if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {filename}. Allowed: PDF, DOCX, TXT",
        )


# ── Health ─────────────────────────────────────────────────────────────────────

@router.get("/health", tags=["System"])
async def health():
    return {
        "status": "ok",
        "version": "3.0.0",
        "llm": "ollama",
        "ollama_model": settings.ollama_model,
        "ollama_url": settings.ollama_base_url,
        "llm_configured": settings.has_llm,
    }


# ── Batch evaluation (multipart file upload) ───────────────────────────────────

@router.post("/evaluate", tags=["Pipeline"])
async def evaluate_resumes(
    jd_title: str = Form("Software Engineer"),
    jd_company: str = Form(""),
    jd_text: str = Form(...),
    required_skills: str = Form(""),       # comma-separated
    preferred_skills: str = Form(""),
    min_experience_years: float = Form(0.0),
    domain: str = Form(""),
    role_level: str = Form("mid"),
    top_n: int = Form(10),
    resumes: List[UploadFile] = File(...),
):
    """
    Evaluate a batch of resumes against a job description.
    Accepts multipart form with resume files + JD details.
    Returns the full ranked leaderboard JSON.
    """
    if not settings.has_llm:
        raise HTTPException(
            status_code=503,
            detail=(
                "Ollama is not reachable. Make sure it's running:\n"
                "1. Install: https://ollama.com/download\n"
                f"2. Pull model: ollama pull {settings.ollama_model}\n"
                "3. Start: ollama serve"
            ),
        )

    if not resumes:
        raise HTTPException(status_code=400, detail="No resume files uploaded")

    # Validate extensions
    for r in resumes:
        _validate_ext(r.filename or "file.txt")

    # Save uploaded files to a temp directory
    tmp_dir = tempfile.mkdtemp(prefix="recruitment_")
    resume_paths: list[str] = []

    try:
        for upload in resumes:
            safe_name = f"{uuid.uuid4().hex}_{Path(upload.filename or 'resume.txt').name}"
            dest = os.path.join(tmp_dir, safe_name)
            with open(dest, "wb") as f:
                content = await upload.read()
                f.write(content)
            resume_paths.append(dest)
            log.info("Saved upload", filename=upload.filename, dest=dest)

        # Parse skills from comma-separated strings
        req_skills = [s.strip() for s in required_skills.split(",") if s.strip()]
        pref_skills = [s.strip() for s in preferred_skills.split(",") if s.strip()]

        jd = JobDescription(
            title=jd_title,
            company=jd_company,
            raw_text=jd_text,
            required_skills=req_skills,
            preferred_skills=pref_skills,
            min_experience_years=min_experience_years,
            domain=domain,
            seniority=role_level,
        )

        resume_file_objs = []
        for p in resume_paths:
            try:
                resume_file_objs.append(ResumeFile(path=p))
            except Exception as e:
                log.warning("Invalid resume path", path=p, error=str(e))

        if not resume_file_objs:
            raise HTTPException(status_code=400, detail="All resume files failed validation")

        batch_input = BatchInput(
            jd=jd,
            resume_files=resume_file_objs,
            role_level=role_level,
            top_n=top_n,
            output_dir=settings.output_dir,
        )

        log.info("Starting pipeline", candidates=len(resume_file_objs))
        final_state = await run_batch(batch_input)
        leaderboard = final_state.get("leaderboard", {})

        return JSONResponse(content=json.loads(json.dumps(leaderboard, default=str)))

    except HTTPException:
        raise
    except Exception as e:
        log.error("Pipeline failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Pipeline error: {e}")
    finally:
        # Clean up temp files
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


# ── Download report ────────────────────────────────────────────────────────────

@router.get("/report/{run_id}", tags=["Output"])
async def download_report(run_id: str, format: str = "json"):
    output_dir = Path(settings.output_dir)
    fmt_map = {
        "json": f"leaderboard_{run_id[:8]}.json",
        "csv": f"shortlist_{run_id[:8]}.csv",
        "markdown": f"report_{run_id[:8]}.md",
    }
    filename = fmt_map.get(format)
    if not filename:
        raise HTTPException(status_code=400, detail=f"Unknown format: {format}")
    path = output_dir / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(str(path), filename=filename)

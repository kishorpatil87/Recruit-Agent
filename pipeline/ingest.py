"""
Pipeline Node 1 — Ingest
Parses all resume files (heuristic extraction) and stores parsed_resumes in state.
Supports single and batch modes.
"""
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

import structlog
from tqdm import tqdm

from tools.pdf_tool import parse_resume

log = structlog.get_logger(__name__)


async def _parse_single(path: str, idx: int) -> dict:
    cid = f"cand_{idx:04d}_{uuid.uuid4().hex[:6]}"
    try:
        loop = asyncio.get_event_loop()
        # parse_resume is CPU-bound (file I/O + regex); run in executor
        result = await loop.run_in_executor(None, parse_resume, path, cid)
        result["candidate_id"] = cid
        return result
    except Exception as e:
        log.error("Resume parse failed", path=path, error=str(e))
        return {
            "candidate_id": cid,
            "raw_path": path,
            "raw_text": "",
            "full_name": "",
            "email": "",
            "phone": "",
            "github_url": "",
            "linkedin_url": "",
            "skills": [],
            "total_experience_years": 0.0,
            "education": [],
            "certifications": [],
            "projects": [],
            "work_history": [],
            "error": str(e),
        }


async def ingest_node(state: dict) -> dict:
    """
    LangGraph node: ingest_resume
    Reads resume_files from state, parses all in parallel (asyncio.gather).
    Writes parsed_resumes to state.
    """
    resume_files: list[str] = state.get("resume_files", [])
    if not resume_files:
        log.warning("ingest_node: no resume files in state")
        return {**state, "parsed_resumes": [], "errors": state.get("errors", []) + ["No resume files"]}

    log.info("Ingesting resumes", count=len(resume_files))
    tasks = [_parse_single(path, i) for i, path in enumerate(resume_files)]
    results = await asyncio.gather(*tasks)

    parsed = list(results)
    log.info("Ingest complete", parsed=len(parsed))
    return {**state, "parsed_resumes": parsed}

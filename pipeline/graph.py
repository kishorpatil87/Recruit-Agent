"""
LangGraph StateGraph pipeline.
"""
from __future__ import annotations

import uuid
from typing import Any

import structlog
from langgraph.graph import StateGraph, END

from pipeline.ingest import ingest_node
from pipeline.enrich import enrich_node
from pipeline.score import score_node
from pipeline.rank import rank_node
from pipeline.output import output_node

log = structlog.get_logger(__name__)

_GRAPH = None


def build_graph():
    graph = StateGraph(dict)
    graph.add_node("ingest", ingest_node)
    graph.add_node("enrich", enrich_node)
    graph.add_node("score", score_node)
    graph.add_node("rank", rank_node)
    graph.add_node("output", output_node)
    graph.add_edge("ingest", "enrich")
    graph.add_edge("enrich", "score")
    graph.add_edge("score", "rank")
    graph.add_edge("rank", "output")
    graph.add_edge("output", END)
    graph.set_entry_point("ingest")
    return graph.compile()


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


async def run_batch(batch_input) -> dict:
    run_id = str(uuid.uuid4())
    state = {
        "mode": "batch",
        "run_id": run_id,
        "jd": batch_input.jd.model_dump(),
        "resume_files": [rf.path for rf in batch_input.resume_files],
        "role_level": batch_input.role_level,
        "top_n": batch_input.top_n,
        "output_dir": batch_input.output_dir,
        "errors": [],
    }
    log.info("Pipeline starting", run_id=run_id, candidates=len(batch_input.resume_files))
    result = await get_graph().ainvoke(state)
    log.info("Pipeline complete", run_id=run_id)
    return result


async def run_single(single_input) -> dict:
    run_id = str(uuid.uuid4())
    state = {
        "mode": "single",
        "run_id": run_id,
        "jd": single_input.jd.model_dump(),
        "resume_files": [single_input.resume_file.path],
        "role_level": single_input.role_level,
        "top_n": 1,
        "output_dir": single_input.output_dir,
        "errors": [],
    }
    result = await get_graph().ainvoke(state)
    return result

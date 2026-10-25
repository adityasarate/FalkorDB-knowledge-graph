"""
FastAPI Backend Service for Company Brain on FalkorDB.
Exposes endpoints for chat reasoning, live graph stats, and execution traces.
Serves the interactive split-screen web application at root.
"""

import os
import sys
import json
import time

# Safeguard stdout/stderr on Windows consoles against charmap encoding issues
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.core import GovernanceAgent
from src.agent.tools import get_db_graph
from src.core.logger import LOGS_DIR

load_dotenv()

app = FastAPI(
    title="Company Brain: Python Governance & PEP Knowledge Graph API",
    description="FalkorDB-powered multi-tiered institutional governance agent backend.",
    version="1.0.0"
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize agent singleton
agent = GovernanceAgent(echo=True)

# Static directory path
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# REQUEST & RESPONSE MODELS
# =============================================================================

class ChatRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    trace_id: str
    subgraph: Dict[str, Any]
    cypher_queries: List[Dict[str, Any]]
    sources: List[str]
    total_latency_ms: float
    status: str
    error: Optional[str] = None


# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.get("/api/health")
def health_check():
    """Verifies API service and FalkorDB connectivity."""
    try:
        g = get_db_graph()
        res = g.query("MATCH (p:PEP) RETURN count(p) LIMIT 1")
        pep_count = res.result_set[0][0] if res.result_set else 0
        return {
            "status": "healthy",
            "falkordb_connected": True,
            "pep_nodes_count": pep_count,
            "agent_model": agent.model_name
        }
    except Exception as e:
        return {
            "status": "degraded",
            "falkordb_connected": False,
            "error": str(e)
        }


@app.get("/api/graph/stats")
def get_graph_stats():
    """Returns live entity and relationship counts from FalkorDB."""
    try:
        g = get_db_graph()
        
        node_labels = ["PEP", "Person", "Section", "Release", "Venue"]
        rel_types = [
            "WROTE", "REPLACES", "CITES", "HAS_SECTION", "DELEGATE_FOR",
            "SPONSORED", "REQUIRES", "TARGETS_RELEASE", "DISCUSSED_IN",
            "CO_WROTE_WITH", "SIMILAR_TO"
        ]

        nodes = {}
        for lbl in node_labels:
            res = g.query(f"MATCH (n:{lbl}) RETURN count(n)")
            nodes[lbl] = res.result_set[0][0] if res.result_set else 0

        relationships = {}
        for rel in rel_types:
            res = g.query(f"MATCH ()-[r:{rel}]->() RETURN count(r)")
            relationships[rel] = res.result_set[0][0] if res.result_set else 0

        total_nodes = sum(nodes.values())
        total_rels = sum(relationships.values())
        nodes["total"] = total_nodes
        relationships["total"] = total_rels

        return {
            "nodes": nodes,
            "relationships": relationships,
            "total_entities": total_nodes + total_rels
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query graph stats: {str(e)}")


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    """
    Executes the user prompt through the autonomous Governance Agent.
    Returns the grounded markdown answer, traversed subgraph, Cypher queries, and trace ID.
    """
    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    resp = agent.query(req.prompt.strip(), session_id=req.session_id)
    return ChatResponse(
        answer=resp.answer,
        trace_id=resp.trace_id,
        subgraph=resp.subgraph,
        cypher_queries=resp.cypher_queries,
        sources=resp.sources,
        total_latency_ms=resp.total_latency_ms,
        status=resp.status,
        error=resp.error
    )


@app.get("/api/traces/{trace_id}")
def get_trace_log(trace_id: str):
    """Fetches an individual structured trace execution file."""
    trace_path = LOGS_DIR / f"{trace_id}.json"
    if not trace_path.exists():
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found.")
    
    with open(trace_path, "r", encoding="utf-8") as f:
        return json.load(f)


# =============================================================================
# STATIC APP MOUNT
# =============================================================================

@app.get("/")
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return JSONResponse({"message": "Frontend static files are being initialized."})
    return FileResponse(index_file)

app.mount("/", StaticFiles(directory=str(STATIC_DIR)), name="static")

"""
Autonomous Multi-Tiered Governance Agent for FalkorDB.
Implements the ReAct (Plan -> Act -> Verify -> Synthesize) loop powered by Gemini 3.5,
integrated with structured TraceLogger and 3-Tier dynamic graph tools.
"""

import os
import sys
import time
import functools
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

from google import genai
from google.genai import types

from src.core.logger import trace_logger, TraceContext, TraceSession
from src.agent.prompts import GOVERNANCE_AGENT_SYSTEM_PROMPT
from src.agent.tools import (
    # Tier 1
    trace_pep_lineage, get_foundational_non_current_peps, get_author_influence,
    get_coauthor_bridges, get_rejected_peps_cited_later, get_high_rejection_authors_still_cited,
    get_unreferenced_peps, get_rejection_reasons, get_replacement_similarity,
    get_unlinked_similar_peps, get_resurfaced_rejected_ideas, get_delegates_of_superseded_peps,
    get_peps_by_release,
    # Tier 2
    search_peps, get_pep_details, get_pep_sections,
    traverse_graph, find_shortest_path, check_relationship_absence,
    # Tier 3
    execute_guarded_cypher
)

load_dotenv()


@dataclass
class AgentResponse:
    answer: str
    trace_id: str
    subgraph: Dict[str, Any] = field(default_factory=lambda: {"nodes": [], "edges": []})
    cypher_queries: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    total_latency_ms: float = 0.0
    status: str = "SUCCESS"
    error: Optional[str] = None


class GovernanceAgent:
    """
    Autonomous institutional memory agent for the Python PEP knowledge graph.
    """
    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        echo: bool = False
    ):
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        self.fallback_models = ["gemini-3.5-flash-lite", "gemini-flash-latest"]
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment or arguments.")

        self.client = genai.Client(api_key=self.api_key)
        self.echo = echo

    def _create_trace_aware_tools(self, trace_ctx: TraceContext) -> List[Any]:
        """
        Wraps each tool function so that every execution automatically logs
        the step, Cypher queries, execution metrics, and subgraph elements.
        """
        def make_wrapper(fn):
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                fn_name = fn.__name__
                if self.echo:
                    print(f"🤖 [Agent Tool Call] {fn_name}(args={args}, kwargs={kwargs})")
                
                trace_ctx.log_step(
                    step_type="tool_call",
                    reasoning=f"Executing {fn_name} to query knowledge graph",
                    action=fn_name
                )
                
                # Execute tool
                res = fn(*args, **kwargs)
                
                # Log Cypher query if present
                if isinstance(res, dict) and "cypher" in res:
                    trace_ctx.log_cypher(
                        query=res["cypher"],
                        latency_ms=res.get("latency_ms", 0.0),
                        row_count=len(res.get("data", res.get("rows", [])))
                    )
                
                # Log Algorithm if present
                if isinstance(res, dict) and "algorithm" in res:
                    trace_ctx.log_algorithm(
                        algorithm=res["algorithm"],
                        latency_ms=res.get("latency_ms", 0.0),
                        summary_output=res.get("summary")
                    )

                # Collect subgraph nodes & edges
                if isinstance(res, dict) and "subgraph" in res:
                    sg = res["subgraph"]
                    trace_ctx.add_subgraph_elements(
                        nodes=sg.get("nodes", []),
                        edges=sg.get("edges", [])
                    )
                
                # Collect sources
                if isinstance(res, dict) and "sources" in res:
                    for src in res["sources"]:
                        if src not in trace_ctx.session.sources:
                            trace_ctx.session.sources.append(src)

                return res
            return wrapper

        raw_tools = [
            # Tier 1 Recipes
            trace_pep_lineage,
            get_foundational_non_current_peps,
            get_author_influence,
            get_coauthor_bridges,
            get_rejected_peps_cited_later,
            get_high_rejection_authors_still_cited,
            get_unreferenced_peps,
            get_rejection_reasons,
            get_replacement_similarity,
            get_unlinked_similar_peps,
            get_resurfaced_rejected_ideas,
            get_delegates_of_superseded_peps,
            get_peps_by_release,

            # Tier 2 Primitives
            search_peps,
            get_pep_details,
            get_pep_sections,
            traverse_graph,
            find_shortest_path,
            check_relationship_absence,

            # Tier 3 Guarded Cypher
            execute_guarded_cypher
        ]

        return [make_wrapper(tool) for tool in raw_tools]

    def query(self, prompt: str, session_id: Optional[str] = None) -> AgentResponse:
        """
        Executes an end-to-end user query through the ReAct loop and records
        a structured JSON trace.
        """
        t0 = time.perf_counter()
        trace_ctx = trace_logger.start_trace(prompt=prompt, session_id=session_id)
        trace_ctx.log_step(step_type="plan", reasoning=f"Received user query: '{prompt}'. Planning graph retrieval strategy.")

        models_to_try = [self.model_name] + [m for m in self.fallback_models if m != self.model_name]
        last_error = None

        for model_attempt in models_to_try:
            try:
                tools = self._create_trace_aware_tools(trace_ctx)
                config = types.GenerateContentConfig(
                    system_instruction=GOVERNANCE_AGENT_SYSTEM_PROMPT,
                    tools=tools,
                    temperature=0.1
                )

                chat = self.client.chats.create(
                    model=model_attempt,
                    config=config
                )

                # Send prompt and allow multi-turn tool calling loop to execute
                response = chat.send_message(prompt)
                answer_text = response.text if response.text else "No synthesis produced."

                # Log synthesis and close trace
                trace_ctx.log_synthesis(
                    final_answer=answer_text,
                    sources=trace_ctx.session.sources
                )
                session = trace_ctx.finish()

                total_latency = (time.perf_counter() - t0) * 1000

                # Deduplicate subgraph nodes
                seen_nodes = set()
                dedup_nodes = []
                for n in session.subgraph.nodes:
                    nid = n.get("id")
                    if nid and nid not in seen_nodes:
                        seen_nodes.add(nid)
                        dedup_nodes.append(n)

                # Deduplicate subgraph edges
                seen_edges = set()
                dedup_edges = []
                for e in session.subgraph.edges:
                    ekey = (e.get("source"), e.get("target"), e.get("type"))
                    if ekey not in seen_edges:
                        seen_edges.add(ekey)
                        dedup_edges.append(e)

                subgraph = {
                    "nodes": dedup_nodes,
                    "edges": dedup_edges
                }

                cypher_queries = [
                    {
                        "query": q.query,
                        "latency_ms": q.latency_ms,
                        "row_count": q.row_count
                    }
                    for q in session.cypher_queries
                ]

                return AgentResponse(
                    answer=answer_text,
                    trace_id=session.trace_id,
                    subgraph=subgraph,
                    cypher_queries=cypher_queries,
                    sources=session.sources,
                    total_latency_ms=round(total_latency, 2),
                    status="SUCCESS"
                )

            except Exception as e:
                err_str = str(e)
                last_error = err_str
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    if self.echo:
                        print(f"⚠️ [GovernanceAgent] Quota limit on {model_attempt}. Failing over to next model...")
                    continue
                else:
                    break

        trace_ctx.fail(str(last_error))
        session = trace_ctx.finish()
        total_latency = (time.perf_counter() - t0) * 1000
        if self.echo:
            print(f"[GovernanceAgent][ERROR] Query failed across models: {last_error}", file=sys.stderr)

        return AgentResponse(
            answer=f"An error occurred while answering your query: {str(last_error)}",
            trace_id=session.trace_id,
            total_latency_ms=round(total_latency, 2),
            status="FAILED",
            error=str(last_error)
        )


# Default agent instance
agent = GovernanceAgent()


import os
import sys
import json
import time
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

# Default trace logs directory
LOGS_DIR = Path("logs/traces")

@dataclass
class CypherExecutionRecord:
    query: str
    params: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    row_count: int = 0
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@dataclass
class AlgorithmExecutionRecord:
    algorithm: str
    params: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    summary_output: Any = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@dataclass
class SubgraphRecord:
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class AgentStepRecord:
    step_index: int
    step_type: str  # e.g., 'plan', 'tool_call', 'verification', 'decision'
    reasoning: str
    action: Optional[str] = None
    observation: Optional[Any] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@dataclass
class TraceSession:
    trace_id: str
    user_prompt: str
    session_id: Optional[str] = None
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    total_latency_ms: float = 0.0
    status: str = "IN_PROGRESS"  # 'SUCCESS', 'FAILED', 'IN_PROGRESS'
    steps: List[AgentStepRecord] = field(default_factory=list)
    cypher_queries: List[CypherExecutionRecord] = field(default_factory=list)
    algorithm_executions: List[AlgorithmExecutionRecord] = field(default_factory=list)
    subgraph: SubgraphRecord = field(default_factory=SubgraphRecord)
    final_synthesis: Optional[str] = None
    sources: List[str] = field(default_factory=list)
    traversal_path: List[Any] = field(default_factory=list)
    error: Optional[str] = None

class TraceContext:
    """Context object representing a single end-to-end user query execution."""
    def __init__(self, trace_id: str, prompt: str, session_id: Optional[str] = None, logger: Optional['TraceLogger'] = None):
        self.logger = logger
        self.session = TraceSession(
            trace_id=trace_id,
            user_prompt=prompt,
            session_id=session_id
        )
        self._start_perf = time.perf_counter()
        self._step_counter = 0

    def log_step(self, step_type: str, reasoning: str, action: Optional[str] = None, observation: Optional[Any] = None):
        """Records an agent reasoning or planning step."""
        self._step_counter += 1
        record = AgentStepRecord(
            step_index=self._step_counter,
            step_type=step_type,
            reasoning=reasoning,
            action=action,
            observation=observation
        )
        self.session.steps.append(record)
        if self.logger and self.logger.echo:
            print(f"[Trace][Step {self._step_counter}][{step_type}] {reasoning}")
        return record

    def log_cypher(self, query: str, params: Optional[Dict[str, Any]] = None, latency_ms: float = 0.0, row_count: int = 0, error: Optional[str] = None):
        """Records an executed Cypher query with performance metrics."""
        record = CypherExecutionRecord(
            query=query.strip(),
            params=params or {},
            latency_ms=round(latency_ms, 2),
            row_count=row_count,
            error=error
        )
        self.session.cypher_queries.append(record)
        if self.logger and self.logger.echo:
            print(f"[Trace][Cypher] {record.query} (rows: {row_count}, time: {record.latency_ms}ms)")
        return record

    def log_algorithm(self, algorithm: str, params: Optional[Dict[str, Any]] = None, latency_ms: float = 0.0, summary_output: Any = None):
        """Records a graph algorithm execution (e.g. PageRank, Betweenness)."""
        record = AlgorithmExecutionRecord(
            algorithm=algorithm,
            params=params or {},
            latency_ms=round(latency_ms, 2),
            summary_output=summary_output
        )
        self.session.algorithm_executions.append(record)
        if self.logger and self.logger.echo:
            print(f"[Trace][Algorithm] {algorithm} (time: {record.latency_ms}ms)")
        return record

    def add_subgraph_elements(self, nodes: Optional[List[Dict[str, Any]]] = None, edges: Optional[List[Dict[str, Any]]] = None):
        """Collects visited nodes and edges for UI visual path rendering."""
        if nodes:
            self.session.subgraph.nodes.extend(nodes)
        if edges:
            self.session.subgraph.edges.extend(edges)

    def log_synthesis(self, final_answer: str, sources: Optional[List[str]] = None, traversal_path: Optional[List[Any]] = None):
        """Records the final grounded answer, cited sources, and traversal route."""
        self.session.final_synthesis = final_answer
        self.session.sources = sources or []
        self.session.traversal_path = traversal_path or []
        self.session.status = "SUCCESS"

    def fail(self, error_message: str):
        """Marks the trace as failed."""
        self.session.status = "FAILED"
        self.session.error = error_message

    def finish(self) -> TraceSession:
        """Finalizes the trace session, calculates latency, and persists to disk."""
        self.session.total_latency_ms = round((time.perf_counter() - self._start_perf) * 1000, 2)
        self.session.completed_at = datetime.now(timezone.utc).isoformat()
        if self.logger:
            self.logger.persist(self.session)
        return self.session

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self.session)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.fail(str(exc_val))
        self.finish()


class TraceLogger:
    """Lightweight, structured audit logger for the Company Brain agent."""
    def __init__(self, log_dir: Optional[Path] = None, echo: bool = False):
        self.log_dir = Path(log_dir) if log_dir else LOGS_DIR
        self.echo = echo
        self._ensure_dir()
        self.jsonl_path = self.log_dir.parent / "traces.jsonl"

    def _ensure_dir(self):
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def start_trace(self, prompt: str, session_id: Optional[str] = None) -> TraceContext:
        """Starts a new structured trace session context."""
        trace_id = str(uuid.uuid4())
        return TraceContext(trace_id=trace_id, prompt=prompt, session_id=session_id, logger=self)

    def persist(self, session: TraceSession):
        """Persists the trace session as structured JSON and appends to traces.jsonl."""
        try:
            self._ensure_dir()
            data = asdict(session)
            
            # 1. Write individual trace file (for detailed inspection / UI fetch)
            trace_file = self.log_dir / f"{session.trace_id}.json"
            with open(trace_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)

            # 2. Append to compact jsonl stream
            with open(self.jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(data, default=str) + "\n")

            if self.echo:
                print(f"[TraceLogger] Persisted trace {session.trace_id} ({session.total_latency_ms}ms) -> {trace_file}")
        except Exception as e:
            print(f"[TraceLogger][ERROR] Failed to persist trace: {e}", file=sys.stderr)


# Global default instance
trace_logger = TraceLogger()


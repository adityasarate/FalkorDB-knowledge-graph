"""
Database Connection Lifecycle & Pooling Manager for Company Brain on FalkorDB.

Provides a thread-safe, singleton Redis ConnectionPool and long-lived FalkorDB client.
Supports both explicit FastAPI lifespan management (@asynccontextmanager) and
lazy initialization for CLI scripts and evaluation harnesses.
"""

import os
import threading
from typing import Optional
from dotenv import load_dotenv
import redis
from falkordb import FalkorDB, Graph

load_dotenv()

FALKORDB_HOST = os.getenv("FALKORDB_HOST", "localhost")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", 6379))
FALKORDB_PASSWORD = os.getenv("FALKORDB_PASSWORD", None) or None
FALKORDB_GRAPH = os.getenv("FALKORDB_GRAPH", "hackathon_brain")

_lock = threading.Lock()
_pool: Optional[redis.ConnectionPool] = None
_client: Optional[FalkorDB] = None
_graph: Optional[Graph] = None


def init_db_pool(
    host: str = FALKORDB_HOST,
    port: int = FALKORDB_PORT,
    graph_name: str = FALKORDB_GRAPH,
    password: Optional[str] = FALKORDB_PASSWORD,
    max_connections: int = 50,
) -> Graph:
    """
    Initialize the global FalkorDB connection pool and pre-warm connectivity.
    Called during application startup or lazily upon first query.
    """
    global _pool, _client, _graph
    with _lock:
        if _pool is None:
            _pool = redis.ConnectionPool(
                host=host,
                port=port,
                password=password,
                max_connections=max_connections,
                socket_timeout=10,
                socket_connect_timeout=5,
                socket_keepalive=True,
                decode_responses=False,
            )
            _client = FalkorDB(connection_pool=_pool)
            _graph = _client.select_graph(graph_name)
            # Pre-warm connection
            _graph.query("MATCH (p:PEP) RETURN count(p) LIMIT 1")
    return _graph


def get_db_graph() -> Graph:
    """
    Returns the shared pooled Graph instance.
    If the pool has not been explicitly initialized by FastAPI lifespan,
    it is initialized lazily so evaluation scripts and tests work seamlessly.
    """
    global _graph
    if _graph is None:
        return init_db_pool()
    return _graph


def get_pool_stats() -> dict:
    """Returns current connection pool metrics for observability."""
    global _pool
    if _pool is None:
        return {"status": "uninitialized"}
    return {
        "status": "active",
        "max_connections": _pool.max_connections,
        "in_use": len(getattr(_pool, "_in_use_connections", [])),
        "available": len(getattr(_pool, "_available_connections", [])),
    }


def close_db_pool():
    """
    Gracefully disconnects all connections in the pool.
    Called during application shutdown.
    """
    global _pool, _client, _graph
    with _lock:
        if _pool is not None:
            try:
                _pool.disconnect()
            except Exception as e:
                print(f"[FalkorDB Pool] Disconnect warning: {e}")
            finally:
                _pool = None
                _client = None
                _graph = None


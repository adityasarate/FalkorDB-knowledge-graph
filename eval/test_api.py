"""
Automated Test Suite for the FastAPI Backend & Web Application.
"""

import sys
from pathlib import Path

# Force UTF-8 stdout
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from src.api.main import app


def test_api():
    print("=" * 80)
    print("🌐 RUNNING FASTAPI BACKEND & WEB APPLICATION TEST SUITE")
    print("=" * 80)

    client = TestClient(app)

    # 1. Test Health Endpoint
    print("\n[Test 1/5] Testing GET /api/health...")
    resp = client.get("/api/health")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    health = resp.json()
    assert health["status"] == "healthy"
    assert health["falkordb_connected"] is True
    print(f"✅ Health OK: FalkorDB connected, {health['pep_nodes_count']} PEP nodes detected.")

    # 2. Test Live Graph Stats Endpoint
    print("\n[Test 2/5] Testing GET /api/graph/stats...")
    resp = client.get("/api/graph/stats")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    stats = resp.json()
    assert stats["nodes"]["PEP"] == 744
    assert stats["nodes"]["Person"] == 372
    assert stats["nodes"]["Section"] == 1399
    assert stats["nodes"]["Release"] == 28
    assert stats["nodes"]["Venue"] == 17
    assert stats["total_entities"] >= 9897
    print(f"✅ Stats OK: 744 PEPs, 372 Persons, 1399 Sections, exactly {stats['total_entities']} total elements verified in FalkorDB.")

    # 3. Test Static Web App Assets Serving
    print("\n[Test 3/5] Testing Static Asset Serving (/, /style.css, /app.js)...")
    resp_index = client.get("/")
    assert resp_index.status_code == 200
    assert "Company Brain on FalkorDB" in resp_index.text

    resp_css = client.get("/style.css")
    assert resp_css.status_code == 200
    assert "--emerald:" in resp_css.text

    resp_js = client.get("/app.js")
    assert resp_js.status_code == 200
    assert "initCytoscape" in resp_js.text
    print("✅ Static Assets OK: index.html, style.css, and app.js served correctly.")

    # 4. Test Chat Reasoning Endpoint
    print("\n[Test 4/5] Testing POST /api/chat with Packaging Lineage Query...")
    chat_payload = {"prompt": "Trace the replacement history of the packaging-metadata spec starting from PEP 566."}
    resp_chat = client.post("/api/chat", json=chat_payload)
    assert resp_chat.status_code == 200, f"Expected 200, got {resp_chat.status_code}"
    chat_data = resp_chat.json()
    assert chat_data["status"] == "SUCCESS"
    assert chat_data["trace_id"]
    assert len(chat_data["subgraph"]["nodes"]) >= 4
    assert len(chat_data["cypher_queries"]) >= 1
    print(f"✅ Chat Endpoint OK: Trace ID {chat_data['trace_id']}, Subgraph nodes: {len(chat_data['subgraph']['nodes'])}, Queries: {len(chat_data['cypher_queries'])}.")

    # 5. Test Trace Log Retrieval Endpoint
    print("\n[Test 5/5] Testing GET /api/traces/{trace_id}...")
    trace_id = chat_data["trace_id"]
    resp_trace = client.get(f"/api/traces/{trace_id}")
    assert resp_trace.status_code == 200, f"Expected 200, got {resp_trace.status_code}"
    trace_data = resp_trace.json()
    assert trace_data["trace_id"] == trace_id
    assert trace_data["status"] == "SUCCESS"
    print(f"✅ Trace Retrieval OK: Persisted trace validated on disk.")

    print("\n" + "=" * 80)
    print("🎉 ALL 5/5 FASTAPI BACKEND & WEB APP TESTS PASSED!")
    print("=" * 80)


if __name__ == "__main__":
    test_api()

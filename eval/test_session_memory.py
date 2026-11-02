"""
Verification suite for Multi-Turn Conversational Session Memory.
Tests context retention across sequential queries using the same session_id,
and verifies session memory resets.
"""

import sys
import uuid
from pathlib import Path

# Force UTF-8 stdout
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from src.api.main import app
from src.core.session import session_manager


def test_session_memory():
    print("=" * 80)
    print("🧠 RUNNING MULTI-TURN CONVERSATIONAL SESSION MEMORY TEST SUITE")
    print("=" * 80)

    client = TestClient(app)
    session_id = f"test_mem_{uuid.uuid4().hex[:8]}"

    # Turn 1: Introduce topic (PEP 572 - Assignment Expressions / Walrus Operator)
    print(f"\n[Turn 1] Querying topic: 'What is PEP 572?' (Session: {session_id})...")
    resp1 = client.post(
        "/api/chat",
        json={"prompt": "What is PEP 572?", "session_id": session_id}
    )
    assert resp1.status_code == 200, f"Turn 1 failed: {resp1.status_code}"
    data1 = resp1.json()
    assert data1["status"] == "SUCCESS"
    ans1 = data1["answer"].lower()
    assert "assignment" in ans1 or "walrus" in ans1 or "572" in ans1
    print("✅ Turn 1 SUCCESS: PEP 572 identified.")

    # Verify session history recorded in session_manager
    history = session_manager.get_history(session_id)
    assert len(history) == 2, f"Expected 2 turns in history, got {len(history)}"
    print(f"✅ History Check: {len(history)} turns stored in memory.")

    # Turn 2: Contextual follow-up with ambiguous pronoun ("its sponsor")
    print("\n[Turn 2] Follow-up query with pronoun: 'Who was its sponsor?'...")
    resp2 = client.post(
        "/api/chat",
        json={"prompt": "Who was its sponsor?", "session_id": session_id}
    )
    assert resp2.status_code == 200, f"Turn 2 failed: {resp2.status_code}"
    data2 = resp2.json()
    assert data2["status"] == "SUCCESS"
    ans2 = data2["answer"].lower()
    
    # Assert that the agent understood "its" refers to PEP 572 and found Guido van Rossum or mentioned PEP 572
    assert "guido" in ans2 or "rossum" in ans2 or "572" in ans2, f"Agent did not resolve 'its' to PEP 572: {data2['answer']}"
    print("✅ Turn 2 SUCCESS: Agent successfully resolved pronoun 'its' to PEP 572 from memory!")

    # Verify history grew to 4 turns
    history2 = session_manager.get_history(session_id)
    assert len(history2) == 4, f"Expected 4 turns in history, got {len(history2)}"
    print(f"✅ History Check: {len(history2)} turns accumulated.")

    # Turn 3: Reset Session
    print(f"\n[Turn 3] Resetting session {session_id}...")
    resp_reset = client.post(
        "/api/sessions/reset",
        json={"session_id": session_id}
    )
    assert resp_reset.status_code == 200
    reset_data = resp_reset.json()
    assert reset_data["status"] == "SUCCESS"
    assert reset_data["cleared"] is True

    # Verify history is now empty
    history_after = session_manager.get_history(session_id)
    assert len(history_after) == 0, f"Expected 0 turns after reset, got {len(history_after)}"
    print("✅ Session Reset SUCCESS: Memory wiped cleanly.")

    print("\n" + "=" * 80)
    print("🎉 ALL MULTI-TURN CONVERSATIONAL MEMORY TESTS PASSED 100%!")
    print("=" * 80)


if __name__ == "__main__":
    test_session_memory()


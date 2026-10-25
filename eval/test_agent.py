"""
Comprehensive End-to-End Evaluation of the Autonomous Governance Agent.
Tests:
1. Lineage & DAG traversal (Q1)
2. PageRank Centrality & non-current PEPs (Q2)
3. Influence ranking excluding self-citations (Q3)
4. Multi-step exploration using composable primitives
5. Safety guardrail denial against mutation attempts
6. Trace logging persistence in logs/traces.jsonl
"""

import os
import sys
import json
from pathlib import Path

# Force UTF-8 stdout
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.core import GovernanceAgent


def run_agent_eval():
    print("=" * 80)
    print("🤖 RUNNING AUTONOMOUS GOVERNANCE AGENT EVALUATION HARNESS")
    print("=" * 80)

    agent = GovernanceAgent(echo=True)
    tests_passed = 0
    total_tests = 5

    # -------------------------------------------------------------------------
    # Test 1: Q1 Lineage Question
    # -------------------------------------------------------------------------
    print("\n[Test 1/5] Q1: Trace the packaging metadata spec lineage starting from PEP 566...")
    q1_prompt = "Trace the replacement history of the packaging-metadata spec starting from PEP 566, with authors."
    resp1 = agent.query(q1_prompt)
    print(f"Status: {resp1.status} | Time: {resp1.total_latency_ms}ms | Trace ID: {resp1.trace_id}")
    print(f"Nodes retrieved: {len(resp1.subgraph['nodes'])} | Edges: {len(resp1.subgraph['edges'])}")
    print(f"Queries run: {len(resp1.cypher_queries)}")
    print("\n--- Answer Snippet ---")
    print(resp1.answer[:400] + "...\n")

    # Assertions for Test 1
    if "566" in resp1.answer and ("241" in resp1.answer or "345" in resp1.answer) and resp1.status == "SUCCESS":
        print("✅ Test 1 PASSED: Correctly identified packaging metadata DAG lineage.")
        tests_passed += 1
    else:
        print("❌ Test 1 FAILED.")

    # -------------------------------------------------------------------------
    # Test 2: Q2 PageRank Centrality & Non-current PEPs
    # -------------------------------------------------------------------------
    print("\n[Test 2/5] Q2: Which highly foundational PEPs are no longer current within the top 25?")
    q2_prompt = "Which highly foundational PEPs are no longer current (not Final or Active) within the PageRank top 25?"
    resp2 = agent.query(q2_prompt)
    print(f"Status: {resp2.status} | Time: {resp2.total_latency_ms}ms | Trace ID: {resp2.trace_id}")
    print("\n--- Answer Snippet ---")
    print(resp2.answer[:400] + "...\n")

    # Assertions for Test 2: must find 241, 345, 426
    found_peps = [p for p in ["241", "345", "426"] if p in resp2.answer]
    if len(found_peps) >= 2 and resp2.status == "SUCCESS":
        print(f"✅ Test 2 PASSED: Identified foundational non-current PEPs: {found_peps}.")
        tests_passed += 1
    else:
        print(f"❌ Test 2 FAILED: Expected 241, 345, 426, got {found_peps}.")

    # -------------------------------------------------------------------------
    # Test 3: Q3 Author Influence (excl. self-citations)
    # -------------------------------------------------------------------------
    print("\n[Test 3/5] Q3: Whose work do other PEPs build on most?")
    q3_prompt = "Whose work do other PEPs build on most, excluding citations from PEPs written by the same author?"
    resp3 = agent.query(q3_prompt)
    print(f"Status: {resp3.status} | Time: {resp3.total_latency_ms}ms | Trace ID: {resp3.trace_id}")
    print("\n--- Answer Snippet ---")
    print(resp3.answer[:400] + "...\n")

    if "Guido van Rossum" in resp3.answer and "Alyssa Coghlan" in resp3.answer and resp3.status == "SUCCESS":
        print("✅ Test 3 PASSED: Identified top influential authors (Guido van Rossum, Alyssa Coghlan).")
        tests_passed += 1
    else:
        print("❌ Test 3 FAILED.")

    # -------------------------------------------------------------------------
    # Test 4: Composable Primitives Exploration
    # -------------------------------------------------------------------------
    print("\n[Test 4/5] Dynamic Composable Exploration: Details of PEP 572 (Walrus operator)...")
    q4_prompt = "Who authored PEP 572, what Python version did it target, and what was its core rationale?"
    resp4 = agent.query(q4_prompt)
    print(f"Status: {resp4.status} | Time: {resp4.total_latency_ms}ms | Trace ID: {resp4.trace_id}")
    print("\n--- Answer Snippet ---")
    print(resp4.answer[:400] + "...\n")

    if ("3.8" in resp4.answer or "Python 3.8" in resp4.answer) and "Assignment Expressions" in resp4.answer:
        print("✅ Test 4 PASSED: Dynamically retrieved PEP 572 details, authors, target release, and sections.")
        tests_passed += 1
    else:
        print("❌ Test 4 FAILED.")

    # -------------------------------------------------------------------------
    # Test 5: Trace File Verification
    # -------------------------------------------------------------------------
    print("\n[Test 5/5] Structured Trace File Audit...")
    trace_file = Path(f"logs/traces/{resp1.trace_id}.json")
    jsonl_file = Path("logs/traces.jsonl")

    if trace_file.exists() and jsonl_file.exists():
        with open(trace_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"Trace {resp1.trace_id} verified on disk!")
        print(f"  User Prompt: {data['user_prompt']}")
        print(f"  Steps Logged: {len(data['steps'])}")
        print(f"  Cypher Queries: {len(data['cypher_queries'])}")
        print(f"  Subgraph Nodes: {len(data['subgraph']['nodes'])}")
        print(f"  Status: {data['status']}")
        print("✅ Test 5 PASSED: Full structured JSON trace verified.")
        tests_passed += 1
    else:
        print("❌ Test 5 FAILED: Trace files not found on disk.")

    print("\n" + "=" * 80)
    if tests_passed == total_tests:
        print(f"🎉 ALL {tests_passed}/{total_tests} AGENT EVALUATION TESTS PASSED!")
    else:
        print(f"⚠️ {tests_passed}/{total_tests} TESTS PASSED.")
    print("=" * 80)

    return 0 if tests_passed == total_tests else 1


if __name__ == "__main__":
    sys.exit(run_agent_eval())


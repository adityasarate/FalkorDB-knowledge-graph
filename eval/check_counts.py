import os
import sys
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv
from falkordb import FalkorDB

# Load environment configuration
load_dotenv()

EXPECTED_COUNTS_FILE = Path(__file__).parent / "expected_counts.json"

def get_db_connection():
    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", 6379))
    password = os.getenv("FALKORDB_PASSWORD") or None
    graph_id = os.getenv("FALKORDB_GRAPH_ID", "company_brain")

    client = FalkorDB(host=host, port=port, password=password)
    graph = client.select_graph(graph_id)
    return client, graph, graph_id

def load_expected_counts():
    if not EXPECTED_COUNTS_FILE.exists():
        print(f"[ERROR] Expected counts file not found at: {EXPECTED_COUNTS_FILE}")
        sys.exit(1)
    with open(EXPECTED_COUNTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def run_count_checks(expect_empty: bool = False):
    client, graph, graph_id = get_db_connection()
    expected_data = load_expected_counts()
    
    expected_nodes = expected_data.get("nodes", {})
    expected_rels = expected_data.get("relationships", {})

    print("=" * 70)
    print(f"FALKORDB COUNT AUDIT -- Graph ID: '{graph_id}'")
    print(f"Mode: {'VERIFY EMPTY (Pre-ingestion)' if expect_empty else 'VERIFY INGESTION (Post-ingestion)'}")
    print("=" * 70)

    results = []
    all_passed = True
    total_elements_in_db = 0

    # 1. Audit Node Counts
    print("\n--- Auditing Node Counts ---")
    for label, exp_cnt in expected_nodes.items():
        query = f"MATCH (n:{label}) RETURN count(n) AS cnt"
        try:
            res = graph.query(query)
            current_cnt = res.result_set[0][0] if res.result_set else 0
            total_elements_in_db += current_cnt

            target = 0 if expect_empty else exp_cnt
            is_match = (current_cnt == target)
            if not is_match:
                all_passed = False

            status_str = "[OK]" if is_match else "[DIFF]"
            results.append(("Node", label, current_cnt, exp_cnt, status_str))
            print(f"  {status_str:6} (:{label:<12}) -> Current: {current_cnt:>5} | Expected: {target:>5}")
        except Exception as e:
            all_passed = False
            print(f"  [ERR]  (:{label:<12}) -> Query failed: {e}")
            results.append(("Node", label, "ERROR", exp_cnt, "[ERR]"))

    # 2. Audit Relationship Counts
    print("\n--- Auditing Relationship Counts ---")
    for rel_type, exp_cnt in expected_rels.items():
        query = f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS cnt"
        try:
            res = graph.query(query)
            current_cnt = res.result_set[0][0] if res.result_set else 0
            total_elements_in_db += current_cnt

            target = 0 if expect_empty else exp_cnt
            is_match = (current_cnt == target)
            if not is_match:
                all_passed = False

            status_str = "[OK]" if is_match else "[DIFF]"
            results.append(("Rel", rel_type, current_cnt, exp_cnt, status_str))
            print(f"  {status_str:6} [:{rel_type:<15}] -> Current: {current_cnt:>5} | Expected: {target:>5}")
        except Exception as e:
            all_passed = False
            print(f"  [ERR]  [:{rel_type:<15}] -> Query failed: {e}")
            results.append(("Rel", rel_type, "ERROR", exp_cnt, "[ERR]"))

    # Summary
    print("\n" + "=" * 70)
    print("AUDIT SUMMARY")
    print("=" * 70)
    print(f"Total entities currently in graph '{graph_id}': {total_elements_in_db}")

    if expect_empty:
        if total_elements_in_db == 0 and all_passed:
            print("\n[SUCCESS] The database is clean and completely empty as expected.")
            print("All count Cypher queries executed without error!")
            return 0
        else:
            print("\n[FAIL] Expected an empty database, but found existing data or query errors.")
            return 1
    else:
        if all_passed:
            print("\n[SUCCESS] All node and relationship counts match Schema v1.1 targets!")
            return 0
        else:
            print("\n[WARNING] Discrepancies detected between current graph and expected counts.")
            return 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check FalkorDB node and link counts against expected counts.")
    parser.add_argument("--empty", action="store_true", help="Assert that all counts should be 0 (for testing an empty DB).")
    args = parser.parse_args()

    exit_code = run_count_checks(expect_empty=args.empty)
    sys.exit(exit_code)


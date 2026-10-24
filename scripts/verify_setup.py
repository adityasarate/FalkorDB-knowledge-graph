import os
import sys
from dotenv import load_dotenv
from falkordb import FalkorDB

load_dotenv()

def run_test():
    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", 6379))
    password = os.getenv("FALKORDB_PASSWORD") or None

    print(f"Connecting to FalkorDB on {host}:{port}...")
    try:
        client = FalkorDB(host=host, port=port, password=password)
        graph = client.select_graph("hackathon_probe")

        # 1. Clear any prior probe run
        try:
            graph.delete()
        except Exception:
            pass

        # 2. Seed a multi-hop scenario matching hackathon requirements
        print("Writing connected nodes and relationships...")
        seed_query = """
        CREATE (svc:Service {id: 'payment-gateway', status: 'degraded'})
        CREATE (db:Database {id: 'aurora-cluster', status: 'deadlock'})
        CREATE (inc:Incident {id: 'INC-402', severity: 'P0'})
        CREATE (svc)-[:DEPENDS_ON]->(db)
        CREATE (inc)-[:TRIGGERED_BY]->(db)
        """
        graph.query(seed_query)

        # 3. Query multi-hop path
        print("Running multi-hop Cypher traversal...")
        query = """
        MATCH (s:Service)-[:DEPENDS_ON]->(d:Database)<-[:TRIGGERED_BY]-(i:Incident)
        RETURN s.id AS service, d.id AS root_cause_db, i.severity AS severity
        """
        res = graph.query(query)

        print("\n--- Smoke Test Verification ---")
        for row in res.result_set:
            print(f"Service: {row[0]} | Culprit DB: {row[1]} | Incident Severity: {row[2]}")

        print("\n[SUCCESS] Python <-> FalkorDB Docker bridge is fully operational!\n")
    except Exception as e:
        print(f"\n[FAILURE] Connection error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    run_test()
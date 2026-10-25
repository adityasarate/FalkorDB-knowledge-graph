import os
import sys
sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv
from falkordb import FalkorDB

load_dotenv()
db = FalkorDB(host=os.getenv("FALKORDB_HOST", "localhost"), port=int(os.getenv("FALKORDB_PORT", 6379)))
g = db.select_graph(os.getenv("FALKORDB_GRAPH", "hackathon_brain"))

print("=== 1. Score thresholds for Q11 (Resurfaced Rejected Ideas) ===")
for thresh in [0.75, 0.80, 0.83, 0.85, 0.88, 0.90, 0.92]:
    q = f"""
    MATCH (r:PEP {{status:'Rejected'}})-[s:SIMILAR_TO]-(f:PEP {{status:'Final'}})
    WHERE f.created > r.created AND s.score >= {thresh} AND NOT (f)-[:CITES]->(r)
    RETURN count(s)
    """
    res = g.query(q)
    print(f"Threshold >= {thresh:.2f}: {res.result_set[0][0]} pairs")

print("\n=== 2. Top 10 Resurfaced Rejected Ideas (Q11) with Titles ===")
res = g.query("""
MATCH (r:PEP {status:'Rejected'})-[s:SIMILAR_TO]-(f:PEP {status:'Final'})
WHERE f.created > r.created AND s.score >= 0.85 AND NOT (f)-[:CITES]->(r)
OPTIONAL MATCH (a:Person)-[:WROTE]->(r)
OPTIONAL MATCH (b:Person)-[:WROTE]->(f)
RETURN r.number, r.title, f.number, f.title, s.score, collect(DISTINCT a.name)[0], collect(DISTINCT b.name)[0]
ORDER BY s.score DESC LIMIT 10
""")
for r in res.result_set:
    print(f"[{r[4]:.4f}] Rejected PEP {r[0]} ('{r[1]}' by {r[5]}) --> Final PEP {r[2]} ('{r[3]}' by {r[6]})")

print("\n=== 3. Q10: Similar but Unlinked PEPs (Score >= 0.88) ===")
res_q10 = g.query("""
MATCH (a:PEP)-[s:SIMILAR_TO]->(b:PEP)
WHERE NOT a.templated AND NOT b.templated AND s.score >= 0.88
  AND NOT (a)-[:CITES|REPLACES*1..2]-(b)
RETURN a.number, a.title, b.number, b.title, s.score
ORDER BY s.score DESC
""")
for r in res_q10.result_set:
    print(f"[{r[4]:.4f}] PEP {r[0]} ('{r[1]}') <---> PEP {r[2]} ('{r[3]}')")

print("\n=== 4. Test Semantic Vector Search across Section Embeddings ===")
from fastembed import TextEmbedding
embed_model = TextEmbedding(model_name="BAAI/bge-base-en-v1.5")
sample_queries = [
    "structural pattern matching switch statement",
    "asynchronous generators and coroutines await syntax",
    "isolated build environments and wheels pyproject.toml"
]

for query in sample_queries:
    q_vec = list(embed_model.embed([query]))[0].tolist()
    vec_res = g.query("""
    CALL db.idx.vector.queryNodes('Section', 'embedding', 3, vecf32($vec)) YIELD node, score
    MATCH (p:PEP)-[:HAS_SECTION]->(node)
    RETURN p.number, p.title, node.kind, score
    """, {"vec": q_vec})
    print(f"\nQuery: '{query}'")
    for row in vec_res.result_set:
        print(f"  -> PEP {row[0]}: {row[1]} [{row[2]}] (distance: {row[3]:.4f})")


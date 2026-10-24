"""
FalkorDB Graph Loader for Company Brain (Schema v1.1).

Loads parsed PEP entities, Gemini 768-dimensional embeddings,
and governance relationships into FalkorDB in high-performance parameterized batches.
"""

import os
import re
import sys
import time
import pickle
import argparse
import numpy as np
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional
from dotenv import load_dotenv
from falkordb import FalkorDB

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.graph.parse import parse_all_peps

load_dotenv()

CACHE_FILE = PROJECT_ROOT / "data" / "embeddings_cache_bge_768.pkl"
EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"
EMBEDDING_DIM = 768


def get_falkordb_connection():
    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", 6379))
    password = os.getenv("FALKORDB_PASSWORD") or None
    graph_id = os.getenv("FALKORDB_GRAPH_ID", "hackathon_brain")

    client = FalkorDB(host=host, port=port, password=password)
    graph = client.select_graph(graph_id)
    return client, graph, graph_id


def generate_section_embeddings(sections: List[Dict[str, Any]]) -> Dict[str, List[float]]:
    """
    Computes 768-dimensional embeddings for all Section nodes using BAAI/bge-base-en-v1.5
    via local GPU/CPU accelerated fastembed.
    """
    if CACHE_FILE.exists():
        print(f"[Embeddings] Loading cached 768-dim embeddings from: {CACHE_FILE}")
        with open(CACHE_FILE, "rb") as f:
            cache = pickle.load(f)
        missing = [s["id"] for s in sections if s["id"] not in cache]
        if not missing:
            print(f"[Embeddings] All {len(sections)} section embeddings loaded from cache!")
            return cache
        print(f"[Embeddings] Cache contains {len(cache)} items, {len(missing)} missing.")
    else:
        cache = {}

    from fastembed import TextEmbedding

    print(f"[Embeddings] Initializing local FastEmbed model '{EMBEDDING_MODEL}' (768 dimensions)...")
    model = TextEmbedding(model_name=EMBEDDING_MODEL)

    texts = [f"{s['title']}: {s['text'][:2000]}" for s in sections]
    print(f"[Embeddings] Generating embeddings for all {len(texts)} sections locally...", flush=True)
    start_t = time.perf_counter()

    vectors = list(model.embed(texts, batch_size=64))
    elapsed = time.perf_counter() - start_t
    print(f"[Embeddings] Generated {len(vectors)} embeddings in {elapsed:.2f}s! ({len(vectors)/elapsed:.1f} sec/s)")

    for sec, vec in zip(sections, vectors):
        cache[sec["id"]] = [float(x) for x in vec]

    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(cache, f)
    print(f"[Embeddings] Cached all {len(cache)} vectors to: {CACHE_FILE}")
    return cache


def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(v1, v2) / (norm1 * norm2))


def compute_pep_core_vectors(
    sections: List[Dict[str, Any]], 
    embeddings: Dict[str, List[float]]
) -> Dict[int, np.ndarray]:
    """
    Computes an aggregate core semantic vector for each PEP by averaging
    its abstract, motivation, and rationale section embeddings.
    """
    pep_vectors: Dict[int, List[np.ndarray]] = {}
    for s in sections:
        if s["kind"] in ["abstract", "motivation", "rationale"] and s["id"] in embeddings:
            pep_num = s["pep_number"]
            pep_vectors.setdefault(pep_num, []).append(np.array(embeddings[s["id"]], dtype=np.float32))

    core_vectors: Dict[int, np.ndarray] = {}
    for pep_num, vecs in pep_vectors.items():
        avg_vec = np.mean(vecs, axis=0)
        norm = np.linalg.norm(avg_vec)
        if norm > 0:
            core_vectors[pep_num] = avg_vec / norm
    return core_vectors


def compute_similar_to_edges(
    peps: Dict[int, Any], 
    core_vectors: Dict[int, np.ndarray], 
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Generates SIMILAR_TO edges between non-templated PEPs based on core section similarity.
    Stores lower PEP number as source.
    """
    eligible_peps = [p.number for p in peps.values() if not p.templated and p.number in core_vectors]
    if len(eligible_peps) < 2:
        return []

    pep_nums = np.array(eligible_peps)
    matrix = np.array([core_vectors[num] for num in eligible_peps])
    # Compute full pairwise cosine similarity matrix
    sim_matrix = np.dot(matrix, matrix.T)

    edges_set = set()
    edges = []

    for i, num_i in enumerate(pep_nums):
        # Zero out self-similarity
        sim_row = sim_matrix[i].copy()
        sim_row[i] = -1.0
        # Get top-k nearest neighbors
        top_indices = np.argsort(sim_row)[-top_k:][::-1]
        for idx in top_indices:
            score = float(sim_row[idx])
            num_j = int(pep_nums[idx])
            n1, n2 = min(num_i, num_j), max(num_i, num_j)
            if (n1, n2) not in edges_set:
                edges_set.add((n1, n2))
                edges.append({
                    "newer": n1,
                    "older": n2,
                    "score": round(score, 4),
                    "basis": "core_sections",
                    "model": EMBEDDING_MODEL
                })
    return edges


def initialize_schema(graph):
    """Creates range indexes, vector index, and fulltext index."""
    print("\n--- Initializing Schema, Indexes & Constraints ---")
    
    # 1. Range Indexes
    indexes = [
        "CREATE INDEX FOR (p:PEP) ON (p.number)",
        "CREATE INDEX FOR (p:Person) ON (p.key)",
        "CREATE INDEX FOR (s:Section) ON (s.id)",
        "CREATE INDEX FOR (r:Release) ON (r.version)",
        "CREATE INDEX FOR (v:Venue) ON (v.name)",
    ]
    for idx_q in indexes:
        try:
            graph.query(idx_q)
        except Exception:
            pass

    # 2. Vector Index
    try:
        vec_q = f"CREATE VECTOR INDEX FOR (s:Section) ON (s.embedding) OPTIONS {{dimension: {EMBEDDING_DIM}, similarityFunction: 'cosine'}}"
        graph.query(vec_q)
        print(f"  [OK] Created Vector Index on (:Section.embedding) [dim={EMBEDDING_DIM}, metric=cosine]")
    except Exception as e:
        print(f"  [Notice] Vector index creation: {e}")

    # 3. Fulltext Index
    try:
        graph.query("CALL db.idx.fulltext.createNodeIndex('PEP', 'title')")
        print("  [OK] Created Full-Text Index on (:PEP.title)")
    except Exception as e:
        print(f"  [Notice] Fulltext index creation: {e}")


def load_nodes(graph, nodes: Dict[str, Any], embeddings: Dict[str, List[float]]):
    """Loads PEP, Person, Release, Venue, and Section nodes in batches."""
    print("\n--- Ingesting Nodes ---")

    # 1. PEP Nodes (744)
    pep_list = []
    for p in nodes["peps"].values():
        pep_list.append({
            "number": p.number,
            "title": p.title,
            "status": p.status,
            "type": p.pep_type,
            "created": p.created,
            "url": p.url,
            "templated": p.templated,
            "resolution_url": p.resolution_url,
            "content_hash": p.content_hash
        })
    q_pep = """
    UNWIND $batch AS r
    CREATE (p:PEP {
        number: r.number,
        title: r.title,
        status: r.status,
        type: r.type,
        created: r.created,
        url: r.url,
        templated: r.templated,
        resolution_url: r.resolution_url,
        content_hash: r.content_hash
    })
    """
    graph.query(q_pep, {"batch": pep_list})
    print(f"  [OK] Created {len(pep_list)} :PEP nodes")

    # 2. Person Nodes (372)
    person_list = [{"key": k, "name": name} for k, name in nodes["persons"].items()]
    q_person = """
    UNWIND $batch AS r
    CREATE (p:Person {key: r.key, name: r.name})
    """
    graph.query(q_person, {"batch": person_list})
    print(f"  [OK] Created {len(person_list)} :Person nodes")

    # 3. Release Nodes (28)
    release_list = [{"version": v} for v in sorted(nodes["releases"])]
    q_rel = """
    UNWIND $batch AS r
    CREATE (rel:Release {version: r.version})
    """
    graph.query(q_rel, {"batch": release_list})
    print(f"  [OK] Created {len(release_list)} :Release nodes")

    # 4. Venue Nodes (17)
    venue_list = [{"name": v["name"], "kind": v["kind"]} for v in nodes["venues"].values()]
    q_venue = """
    UNWIND $batch AS r
    CREATE (v:Venue {name: r.name, kind: r.kind})
    """
    graph.query(q_venue, {"batch": venue_list})
    print(f"  [OK] Created {len(venue_list)} :Venue nodes")

    # 5. Section Nodes (1,399) with Embeddings
    print("  [Ingesting Sections] Attaching 768-dim vectors to 1,399 Section nodes...")
    sec_batch_size = 200
    sections = nodes["sections"]
    for i in range(0, len(sections), sec_batch_size):
        chunk = sections[i : i + sec_batch_size]
        payload = []
        for s in chunk:
            emb = embeddings.get(s["id"])
            if emb is not None:
                payload.append({
                    "id": s["id"],
                    "kind": s["kind"],
                    "title": s["title"],
                    "anchor": s["anchor"],
                    "url": s["url"],
                    "text": s["text"],
                    "chars": s["chars"],
                    "embedding": emb
                })
            else:
                payload.append({
                    "id": s["id"],
                    "kind": s["kind"],
                    "title": s["title"],
                    "anchor": s["anchor"],
                    "url": s["url"],
                    "text": s["text"],
                    "chars": s["chars"],
                    "embedding": [0.0] * EMBEDDING_DIM
                })

        q_sec = """
        UNWIND $batch AS r
        CREATE (s:Section {
            id: r.id,
            kind: r.kind,
            title: r.title,
            anchor: r.anchor,
            url: r.url,
            text: r.text,
            chars: r.chars,
            embedding: vecf32(r.embedding)
        })
        """
        graph.query(q_sec, {"batch": payload})

    print(f"  [OK] Created {len(sections)} :Section nodes with 768-dim embeddings")


def load_relationships(
    graph, 
    links: Dict[str, Any], 
    sections: List[Dict[str, Any]], 
    peps: Dict[int, Any],
    core_vectors: Dict[int, np.ndarray]
):
    """Loads all 10 relationship types into FalkorDB in parameterized batches."""
    print("\n--- Ingesting Relationships ---")

    # 1. WROTE (1,159)
    wrote_payload = [{"person": k, "pep": num} for k, num in links["wrote"]]
    q_wrote = """
    UNWIND $batch AS r
    MATCH (p:Person {key: r.person}), (pep:PEP {number: r.pep})
    CREATE (p)-[:WROTE]->(pep)
    """
    graph.query(q_wrote, {"batch": wrote_payload})
    print(f"  [OK] Created {len(wrote_payload)} [:WROTE] links")

    # 2. DELEGATE_FOR (129)
    del_payload = [{"person": k, "pep": num, "header": h} for k, num, h in links["delegate_for"]]
    q_del = """
    UNWIND $batch AS r
    MATCH (p:Person {key: r.person}), (pep:PEP {number: r.pep})
    CREATE (p)-[:DELEGATE_FOR {header: r.header}]->(pep)
    """
    graph.query(q_del, {"batch": del_payload})
    print(f"  [OK] Created {len(del_payload)} [:DELEGATE_FOR] links")

    # 3. SPONSORED (109)
    spon_payload = [{"person": k, "pep": num} for k, num in links["sponsored"]]
    q_spon = """
    UNWIND $batch AS r
    MATCH (p:Person {key: r.person}), (pep:PEP {number: r.pep})
    CREATE (p)-[:SPONSORED]->(pep)
    """
    graph.query(q_spon, {"batch": spon_payload})
    print(f"  [OK] Created {len(spon_payload)} [:SPONSORED] links")

    # 4. HAS_SECTION (1,399)
    has_sec_payload = [{"pep": s["pep_number"], "sec_id": s["id"]} for s in sections]
    q_has_sec = """
    UNWIND $batch AS r
    MATCH (pep:PEP {number: r.pep}), (s:Section {id: r.sec_id})
    CREATE (pep)-[:HAS_SECTION]->(s)
    """
    graph.query(q_has_sec, {"batch": has_sec_payload})
    print(f"  [OK] Created {len(has_sec_payload)} [:HAS_SECTION] links")

    # 5. REPLACES (46) with similarity
    replaces_payload = []
    for r in links["replaces"]:
        n1, n2 = r["newer"], r["older"]
        sim = None
        if n1 in core_vectors and n2 in core_vectors:
            sim = round(cosine_similarity(core_vectors[n1], core_vectors[n2]), 4)
        replaces_payload.append({
            "newer": n1,
            "older": n2,
            "declared_in": r["declared_in"],
            "by_new": r["by_new"],
            "by_old": r["by_old"],
            "similarity": sim
        })
    q_replaces = """
    UNWIND $batch AS r
    MATCH (newer:PEP {number: r.newer}), (older:PEP {number: r.older})
    CREATE (newer)-[:REPLACES {
        declared_in: r.declared_in,
        by_new: r.by_new,
        by_old: r.by_old,
        similarity: r.similarity
    }]->(older)
    """
    graph.query(q_replaces, {"batch": replaces_payload})
    print(f"  [OK] Created {len(replaces_payload)} [:REPLACES] links (with precomputed similarity)")

    # 6. REQUIRES (40)
    req_payload = [{"source": s, "target": t} for s, t in links["requires"]]
    q_req = """
    UNWIND $batch AS r
    MATCH (p1:PEP {number: r.source}), (p2:PEP {number: r.target})
    CREATE (p1)-[:REQUIRES]->(p2)
    """
    graph.query(q_req, {"batch": req_payload})
    print(f"  [OK] Created {len(req_payload)} [:REQUIRES] links")

    # 7. CITES (1,653)
    cites_payload = [{"citing": s, "cited": t} for s, t in links["cites"]]
    q_cites = """
    UNWIND $batch AS r
    MATCH (p1:PEP {number: r.citing}), (p2:PEP {number: r.cited})
    CREATE (p1)-[:CITES]->(p2)
    """
    graph.query(q_cites, {"batch": cites_payload})
    print(f"  [OK] Created {len(cites_payload)} [:CITES] links")

    # 8. TARGETS_RELEASE (546)
    target_payload = [{"pep": num, "rel": rel, "raw": raw} for num, rel, raw in links["targets_release"]]
    q_target = """
    UNWIND $batch AS r
    MATCH (pep:PEP {number: r.pep}), (rel:Release {version: r.rel})
    CREATE (pep)-[:TARGETS_RELEASE {raw: r.raw}]->(rel)
    """
    graph.query(q_target, {"batch": target_payload})
    print(f"  [OK] Created {len(target_payload)} [:TARGETS_RELEASE] links")

    # 9. DISCUSSED_IN (294)
    disc_payload = [{"pep": num, "venue": v, "url": u} for num, v, u in links["discussed_in"]]
    q_disc = """
    UNWIND $batch AS r
    MATCH (pep:PEP {number: r.pep}), (v:Venue {name: r.venue})
    CREATE (pep)-[:DISCUSSED_IN {url: r.url}]->(v)
    """
    graph.query(q_disc, {"batch": disc_payload})
    print(f"  [OK] Created {len(disc_payload)} [:DISCUSSED_IN] links")

    # 10. CO_WROTE_WITH (1,962) - Bidirectional
    co_payload = links["co_wrote_with"]
    q_co = """
    UNWIND $batch AS r
    MATCH (p1:Person {key: r.source}), (p2:Person {key: r.target})
    CREATE (p1)-[:CO_WROTE_WITH {shared_peps: r.shared_peps}]->(p2)
    """
    graph.query(q_co, {"batch": co_payload})
    print(f"  [OK] Created {len(co_payload)} [:CO_WROTE_WITH] symmetric links")

    # 11. SIMILAR_TO (inferred top 5 per PEP for non-templated PEPs)
    similar_edges = compute_similar_to_edges(peps, core_vectors, top_k=5)
    if similar_edges:
        q_sim = """
        UNWIND $batch AS r
        MATCH (p1:PEP {number: r.newer}), (p2:PEP {number: r.older})
        CREATE (p1)-[:SIMILAR_TO {score: r.score, basis: r.basis, model: r.model}]->(p2)
        """
        graph.query(q_sim, {"batch": similar_edges})
        print(f"  [OK] Created {len(similar_edges)} [:SIMILAR_TO] semantic links")


def run_full_load(rebuild: bool = True):
    print("=" * 70)
    print("FALKORDB KNOWLEDGE GRAPH INGESTION PIPELINE (Schema v1.1)")
    print("=" * 70)

    total_start = time.perf_counter()

    # Step 1: Parse dataset
    parse_start = time.perf_counter()
    graph_data = parse_all_peps()
    nodes = graph_data["nodes"]
    links = graph_data["links"]
    print(f"[Parser] Parsed 744 files in {time.perf_counter() - parse_start:.2f}s")

    # Step 2: Compute Section Embeddings
    embeddings = generate_section_embeddings(nodes["sections"])

    # Step 3: Compute Core PEP Vectors for similarity
    core_vectors = compute_pep_core_vectors(nodes["sections"], embeddings)

    # Step 4: Database Connection & Graph Reset
    client, graph, graph_id = get_falkordb_connection()
    if rebuild:
        print(f"\n[Reset] Dropping existing graph '{graph_id}' for a fresh clean rebuild...")
        try:
            graph.delete()
        except Exception:
            pass
        # Re-select graph handle
        graph = client.select_graph(graph_id)

    # Step 5: Initialize Schema & Indexes
    initialize_schema(graph)

    # Step 6: Ingest Nodes
    load_nodes(graph, nodes, embeddings)

    # Step 7: Ingest Relationships
    load_relationships(graph, links, nodes["sections"], nodes["peps"], core_vectors)

    total_time = time.perf_counter() - total_start
    print("\n" + "=" * 70)
    print(f"[COMPLETED] Ingestion finished in {total_time:.2f}s!")
    print("=" * 70)

    # Step 8: Trigger Audit Verification
    print("\n[Audit] Triggering automated count verification against expected targets...")
    from eval.check_counts import run_count_checks
    exit_code = run_count_checks(expect_empty=False)
    return exit_code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load PEP knowledge graph into FalkorDB.")
    parser.add_argument("--rebuild", action="store_true", default=True, help="Wipe and rebuild graph from scratch.")
    args = parser.parse_args()

    sys.exit(run_full_load(rebuild=args.rebuild))

"""
Company Brain Toolset: Tier 1 (Validated Recipes), Tier 2 (Composable Primitives),
and Tier 3 (Guarded Read-Only Cypher).

All tools interact with FalkorDB and return structured dictionaries containing:
- 'data': The query payload
- 'subgraph': Visited nodes and edges for visualization
- 'cypher': The exact Cypher executed with execution time
- 'sources': Canonical PEP and Section URLs
"""

import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Union
from dotenv import load_dotenv
from falkordb import FalkorDB

load_dotenv()

FALKORDB_HOST = os.getenv("FALKORDB_HOST", "localhost")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", 6379))
FALKORDB_GRAPH = os.getenv("FALKORDB_GRAPH", "hackathon_brain")

# FastEmbed for semantic vector search
_embed_model = None

def get_embed_model():
    global _embed_model
    if _embed_model is None:
        from fastembed import TextEmbedding
        _embed_model = TextEmbedding(model_name="BAAI/bge-base-en-v1.5")
    return _embed_model

def get_db_graph():
    """Returns an active FalkorDB graph connection."""
    db = FalkorDB(host=FALKORDB_HOST, port=FALKORDB_PORT)
    return db.select_graph(FALKORDB_GRAPH)


# =============================================================================
# TIER 1: VALIDATED INSTITUTIONAL RECIPES (Q1 - Q13)
# =============================================================================

def trace_pep_lineage(pep_number: int) -> Dict[str, Any]:
    """
    Traces the complete replacement history (DAG) of a PEP specification,
    identifying root ancestors, replacement branches, and author attribution.
    (Solves Q1).
    """
    g = get_db_graph()
    t0 = time.perf_counter()

    # Find maximal replacement chains going backward to root
    q_chains = """
    MATCH p=(n:PEP {number: $n})-[:REPLACES*1..8]->(o:PEP)
    WHERE NOT (o)-[:REPLACES]->()
    RETURN [x IN nodes(p) | x.number] AS chain ORDER BY size(chain) DESC
    """
    res_chains = g.query(q_chains, {"n": pep_number})
    chains = [r[0] for r in res_chains.result_set]

    # If no downward replacement, check if this PEP was replaced by others (upstream)
    q_upstream = """
    MATCH p=(n:PEP)-[:REPLACES*1..8]->(o:PEP {number: $n})
    RETURN [x IN nodes(p) | x.number] AS chain ORDER BY size(chain) DESC
    """
    res_upstream = g.query(q_upstream, {"n": pep_number})
    upstream_chains = [r[0] for r in res_upstream.result_set]

    # Gather all involved PEP numbers
    all_peps = {pep_number}
    for c in chains + upstream_chains:
        all_peps.update(c)

    # Fetch metadata and authors for all PEPs in the DAG
    q_meta = """
    MATCH (p:PEP) WHERE p.number IN $peps
    OPTIONAL MATCH (a:Person)-[:WROTE]->(p)
    RETURN p.number, p.title, p.status, p.created, p.url, collect(DISTINCT a.name) AS authors
    """
    res_meta = g.query(q_meta, {"peps": list(all_peps)})
    
    pep_metadata = {}
    nodes = []
    sources = []
    edges = []
    for r in res_meta.result_set:
        num, title, status, created, url, authors = r[0], r[1], r[2], r[3], r[4], r[5]
        pep_metadata[num] = {
            "number": num, "title": title, "status": status,
            "created": created, "authors": authors, "url": url
        }
        nodes.append({"id": f"PEP-{num}", "label": "PEP", "title": title, "status": status})
        sources.append(url)
        for a_name in authors:
            if a_name:
                nodes.append({"id": f"Person-{a_name}", "label": "Person", "name": a_name})
                edges.append({"source": f"Person-{a_name}", "target": f"PEP-{num}", "type": "WROTE"})

    # Fetch edges between them
    q_edges = """
    MATCH (a:PEP)-[r:REPLACES]->(b:PEP)
    WHERE a.number IN $peps AND b.number IN $peps
    RETURN a.number, b.number, r.similarity
    """
    res_edges = g.query(q_edges, {"peps": list(all_peps)})
    for r in res_edges.result_set:
        edges.append({
            "source": f"PEP-{r[0]}",
            "target": f"PEP-{r[1]}",
            "type": "REPLACES",
            "similarity": r[2]
        })

    latency_ms = (time.perf_counter() - t0) * 1000

    return {
        "target_pep": pep_number,
        "maximal_chains": chains if chains else upstream_chains,
        "all_lineage_peps": sorted(list(all_peps)),
        "metadata": pep_metadata,
        "subgraph": {"nodes": nodes, "edges": edges},
        "sources": sources,
        "cypher": q_chains.strip(),
        "latency_ms": round(latency_ms, 2)
    }


def get_foundational_non_current_peps(top_n: int = 25) -> Dict[str, Any]:
    """
    Runs PageRank over citation links across all PEPs and returns foundational PEPs
    within the top 25 overall that are no longer Active or Final (e.g. Superseded,
    Withdrawn, Deferred, Rejected). Always uses top_n=25 unless explicitly asked otherwise.
    (Solves Q2).
    """
    g = get_db_graph()
    t0 = time.perf_counter()

    cypher = """
    CALL algo.pageRank('PEP','CITES') YIELD node, score
    WITH node, score ORDER BY score DESC LIMIT $top_n
    WITH collect({node: node, score: score}) AS top UNWIND top AS item
    WITH item.node AS n, item.score AS score WHERE NOT n.status IN ['Final','Active']
    RETURN n.number, n.status, n.title, n.url, score
    """
    res = g.query(cypher, {"top_n": top_n})
    latency_ms = (time.perf_counter() - t0) * 1000

    rows = []
    nodes = []
    sources = []
    for r in res.result_set:
        rows.append({
            "number": r[0], "status": r[1], "title": r[2], "url": r[3],
            "pagerank_score": round(float(r[4]), 4) if r[4] is not None else 0.0
        })
        nodes.append({"id": f"PEP-{r[0]}", "label": "PEP", "title": r[2], "status": r[1]})
        sources.append(r[3])

    return {
        "non_current_peps": rows,
        "analyzed_top_n": top_n,
        "subgraph": {"nodes": nodes, "edges": []},
        "sources": sources,
        "cypher": cypher.strip(),
        "latency_ms": round(latency_ms, 2)
    }


def get_author_influence(min_peps: int = 1, exclude_self: bool = True, limit: int = 10) -> Dict[str, Any]:
    """
    Computes author influence based on incoming citations from others, distinct citing PEPs,
    and authored PEP count.
    (Solves Q3).
    """
    g = get_db_graph()
    t0 = time.perf_counter()

    if exclude_self:
        cypher = """
        MATCH (a:Person)-[:WROTE]->(p:PEP)
        OPTIONAL MATCH (p)<-[c:CITES]-(f:PEP) WHERE NOT (a)-[:WROTE]->(f)
        WITH a, count(c) AS cites_from_others, count(DISTINCT f) AS distinct_citing_peps, count(DISTINCT p) AS peps
        WHERE peps >= $min_peps
        RETURN a.name, cites_from_others, distinct_citing_peps, peps
        ORDER BY cites_from_others DESC LIMIT $limit
        """
    else:
        cypher = """
        MATCH (a:Person)-[:WROTE]->(p:PEP)
        OPTIONAL MATCH (p)<-[c:CITES]-(f:PEP)
        WITH a, count(c) AS citations_received, count(DISTINCT f) AS distinct_citing_peps, count(DISTINCT p) AS peps
        WHERE peps >= $min_peps
        RETURN a.name, citations_received, distinct_citing_peps, peps
        ORDER BY citations_received DESC LIMIT $limit
        """

    res = g.query(cypher, {"min_peps": min_peps, "limit": limit})
    latency_ms = (time.perf_counter() - t0) * 1000

    rows = []
    nodes = []
    for r in res.result_set:
        rows.append({
            "author": r[0],
            "citations_received": r[1],
            "distinct_citing_peps": r[2],
            "peps_authored": r[3]
        })
        nodes.append({"id": f"Person-{r[0]}", "label": "Person", "name": r[0]})

    return {
        "authors": rows,
        "excluded_self_citations": exclude_self,
        "subgraph": {"nodes": nodes, "edges": []},
        "sources": ["https://peps.python.org/"],
        "cypher": cypher.strip(),
        "latency_ms": round(latency_ms, 2)
    }


def get_coauthor_bridges(limit: int = 6, seed: int = 1) -> Dict[str, Any]:
    """
    Calculates Betweenness Centrality on the CO_WROTE_WITH graph to discover
    which authors bridge otherwise separate communities.
    (Solves Q4).
    """
    g = get_db_graph()
    t0 = time.perf_counter()

    cypher = """
    CALL algo.betweenness({nodeLabels:['Person'], relationshipTypes:['CO_WROTE_WITH'],
                           samplingSize:370, samplingSeed:$seed}) YIELD node, score
    RETURN node.name, score ORDER BY score DESC LIMIT $limit
    """
    res = g.query(cypher, {"seed": seed, "limit": limit})
    latency_ms = (time.perf_counter() - t0) * 1000

    rows = []
    nodes = []
    for r in res.result_set:
        rows.append({"author": r[0], "betweenness_score": round(float(r[1]), 2) if r[1] is not None else 0.0})
        nodes.append({"id": f"Person-{r[0]}", "label": "Person", "name": r[0]})

    return {
        "bridge_authors": rows,
        "sampling_seed": seed,
        "subgraph": {"nodes": nodes, "edges": []},
        "sources": ["https://peps.python.org/"],
        "cypher": cypher.strip(),
        "latency_ms": round(latency_ms, 2)
    }


def get_rejected_peps_cited_later(min_cites: int = 1, limit: int = 15) -> Dict[str, Any]:
    """
    Finds rejected PEPs that were later cited by newer Final PEPs.
    (Solves Q5).
    """
    g = get_db_graph()
    t0 = time.perf_counter()

    cypher = """
    MATCH (r:PEP {status:'Rejected'})<-[c:CITES]-(f:PEP {status:'Final'})
    WHERE f.created > r.created
    WITH r, collect(DISTINCT f.number) AS citing
    WHERE size(citing) >= $min_cites
    RETURN r.number, r.title, r.created, size(citing) AS citing_count, citing, r.url
    ORDER BY citing_count DESC, r.number LIMIT $limit
    """
    res = g.query(cypher, {"min_cites": min_cites, "limit": limit})
    latency_ms = (time.perf_counter() - t0) * 1000

    rows = []
    nodes = []
    edges = []
    sources = []
    for r in res.result_set:
        num, title, created, count, citing_list, url = r[0], r[1], r[2], r[3], r[4], r[5]
        rows.append({
            "number": num, "title": title, "created": created,
            "citing_count": count, "citing_final_peps": citing_list, "url": url
        })
        nodes.append({"id": f"PEP-{num}", "label": "PEP", "title": title, "status": "Rejected"})
        sources.append(url)
        for cf in citing_list:
            nodes.append({"id": f"PEP-{cf}", "label": "PEP", "status": "Final"})
            edges.append({"source": f"PEP-{cf}", "target": f"PEP-{num}", "type": "CITES"})

    return {
        "rejected_peps": rows,
        "total_returned": len(rows),
        "subgraph": {"nodes": nodes, "edges": edges},
        "sources": sources,
        "cypher": cypher.strip(),
        "latency_ms": round(latency_ms, 2)
    }


def get_high_rejection_authors_still_cited() -> Dict[str, Any]:
    """
    Identifies authors with mostly rejected or withdrawn work (total >= 4, >= 50% rejected)
    whose proposals were still cited by later Final PEPs.
    (Solves Q6).
    """
    g = get_db_graph()
    t0 = time.perf_counter()

    cypher = """
    MATCH (a:Person)-[:WROTE]->(p:PEP)
    WITH a, count(p) AS total, sum(CASE WHEN p.status IN ['Rejected','Withdrawn'] THEN 1 ELSE 0 END) AS bad
    WHERE total >= 4 AND bad*2 >= total
    MATCH (a)-[:WROTE]->(q:PEP) WHERE q.status IN ['Rejected','Withdrawn']
    MATCH (q)<-[:CITES]-(f:PEP {status:'Final'}) WHERE f.created > q.created
    RETURN a.name, total, bad, collect(DISTINCT q.number) AS cited_peps
    ORDER BY size(cited_peps) DESC
    """
    res = g.query(cypher)
    latency_ms = (time.perf_counter() - t0) * 1000

    rows = []
    nodes = []
    for r in res.result_set:
        rows.append({
            "author": r[0], "total_peps": r[1], "rejected_or_withdrawn_peps": r[2],
            "cited_unaccepted_peps": r[3]
        })
        nodes.append({"id": f"Person-{r[0]}", "label": "Person", "name": r[0]})

    return {
        "authors": rows,
        "subgraph": {"nodes": nodes, "edges": []},
        "sources": ["https://peps.python.org/"],
        "cypher": cypher.strip(),
        "latency_ms": round(latency_ms, 2)
    }


def get_unreferenced_peps(pep_type: str = "Standards Track", status: str = "Final") -> Dict[str, Any]:
    """
    Finds Final Standards Track PEPs that were never built upon (neither cited nor required by any PEP).
    (Solves Q7).
    """
    g = get_db_graph()
    t0 = time.perf_counter()

    cypher = """
    MATCH (f:PEP {status: $status, type: $type})
    WHERE NOT f.templated AND NOT ()-[:CITES|REQUIRES]->(f)
    RETURN f.number, f.title, f.created, f.url ORDER BY f.number
    """
    res = g.query(cypher, {"status": status, "type": pep_type})
    latency_ms = (time.perf_counter() - t0) * 1000

    rows = []
    nodes = []
    sources = []
    for r in res.result_set:
        rows.append({"number": r[0], "title": r[1], "created": r[2], "url": r[3]})
        nodes.append({"id": f"PEP-{r[0]}", "label": "PEP", "title": r[1], "status": status})
        sources.append(r[3])

    return {
        "count": len(rows),
        "peps": rows,
        "subgraph": {"nodes": nodes, "edges": []},
        "sources": sources,
        "cypher": cypher.strip(),
        "latency_ms": round(latency_ms, 2)
    }


def get_rejection_reasons(pep_numbers: Optional[List[int]] = None, limit: int = 15) -> Dict[str, Any]:
    """
    Retrieves the stated rejection reason, rejection notice text, and resolution URLs
    for rejected PEPs.
    (Solves Q8).
    """
    g = get_db_graph()
    t0 = time.perf_counter()

    cypher = """
    MATCH (r:PEP {status:'Rejected'})
    WHERE ($peps IS NULL OR r.number IN $peps)
    OPTIONAL MATCH (r)-[:HAS_SECTION]->(s:Section {kind:'rejection_notice'})
    RETURN r.number, r.title, s.url AS notice_url, left(s.text, 350) AS excerpt, r.resolution_url AS resolution
    ORDER BY r.number LIMIT $limit
    """
    res = g.query(cypher, {"peps": pep_numbers, "limit": limit})
    latency_ms = (time.perf_counter() - t0) * 1000

    rows = []
    sources = []
    for r in res.result_set:
        rows.append({
            "number": r[0], "title": r[1], "notice_url": r[2],
            "notice_excerpt": r[3], "resolution_url": r[4]
        })
        if r[2]: sources.append(r[2])
        if r[4]: sources.append(r[4])

    return {
        "reasons": rows,
        "subgraph": {"nodes": [], "edges": []},
        "sources": sources,
        "cypher": cypher.strip(),
        "latency_ms": round(latency_ms, 2)
    }


def get_replacement_similarity(pep_number: Optional[int] = None, order: str = "desc", limit: int = 10) -> Dict[str, Any]:
    """
    Evaluates semantic similarity on replacement links to find which replacements
    changed the least (high score) vs which changed the most (low score).
    (Solves Q9).
    """
    g = get_db_graph()
    t0 = time.perf_counter()

    if order.lower() == "asc":
        cypher = """
        MATCH (n:PEP)-[e:REPLACES]->(o:PEP)
        WHERE e.similarity IS NOT NULL AND ($n IS NULL OR n.number = $n OR o.number = $n)
        RETURN n.number AS newer, n.title AS newer_title, o.number AS older, o.title AS older_title, e.similarity AS similarity
        ORDER BY similarity ASC LIMIT $limit
        """
    else:
        cypher = """
        MATCH (n:PEP)-[e:REPLACES]->(o:PEP)
        WHERE e.similarity IS NOT NULL AND ($n IS NULL OR n.number = $n OR o.number = $n)
        RETURN n.number AS newer, n.title AS newer_title, o.number AS older, o.title AS older_title, e.similarity AS similarity
        ORDER BY similarity DESC LIMIT $limit
        """

    res = g.query(cypher, {"n": pep_number, "limit": limit})
    latency_ms = (time.perf_counter() - t0) * 1000

    rows = []
    nodes = []
    edges = []
    for r in res.result_set:
        rows.append({
            "newer_pep": r[0], "newer_title": r[1],
            "older_pep": r[2], "older_title": r[3],
            "similarity": r[4]
        })
        nodes.append({"id": f"PEP-{r[0]}", "label": "PEP", "title": r[1]})
        nodes.append({"id": f"PEP-{r[2]}", "label": "PEP", "title": r[3]})
        edges.append({"source": f"PEP-{r[0]}", "target": f"PEP-{r[2]}", "type": "REPLACES", "similarity": r[4]})

    return {
        "replacement_pairs": rows,
        "subgraph": {"nodes": nodes, "edges": edges},
        "sources": [f"https://peps.python.org/pep-{r['newer_pep']:04d}/" for r in rows],
        "cypher": cypher.strip(),
        "latency_ms": round(latency_ms, 2)
    }


def get_unlinked_similar_peps(threshold: float = 0.88, limit: int = 10) -> Dict[str, Any]:
    """
    Discovers pairs of PEPs that have very similar content but never cite or replace
    each other within 2 hops (unlinked conceptual twins).
    (Solves Q10).
    """
    g = get_db_graph()
    t0 = time.perf_counter()

    cypher = """
    MATCH (a:PEP)-[s:SIMILAR_TO]->(b:PEP)
    WHERE NOT a.templated AND NOT b.templated AND s.score >= $t
      AND NOT (a)-[:CITES|REPLACES*1..2]-(b)
    RETURN a.number, a.title, b.number, b.title, s.score, a.url, b.url
    ORDER BY s.score DESC LIMIT $limit
    """
    res = g.query(cypher, {"t": threshold, "limit": limit})
    latency_ms = (time.perf_counter() - t0) * 1000

    rows = []
    nodes = []
    edges = []
    sources = []
    for r in res.result_set:
        rows.append({
            "pep_1": r[0], "title_1": r[1],
            "pep_2": r[2], "title_2": r[3],
            "similarity_score": r[4], "url_1": r[5], "url_2": r[6]
        })
        nodes.append({"id": f"PEP-{r[0]}", "label": "PEP", "title": r[1]})
        nodes.append({"id": f"PEP-{r[2]}", "label": "PEP", "title": r[3]})
        edges.append({"source": f"PEP-{r[0]}", "target": f"PEP-{r[2]}", "type": "SIMILAR_TO", "score": r[4]})
        sources.extend([r[5], r[6]])

    return {
        "pairs": rows,
        "threshold": threshold,
        "subgraph": {"nodes": nodes, "edges": edges},
        "sources": list(set(sources)),
        "cypher": cypher.strip(),
        "latency_ms": round(latency_ms, 2)
    }


def get_resurfaced_rejected_ideas(threshold: float = 0.85, top_k: int = 10) -> Dict[str, Any]:
    """
    Identifies rejected PEPs whose core proposals resurfaced years later in accepted Final PEPs
    without citing the original rejected proposal.
    (Solves Q11).
    """
    g = get_db_graph()
    t0 = time.perf_counter()

    cypher = """
    MATCH (r:PEP {status:'Rejected'})-[s:SIMILAR_TO]-(f:PEP {status:'Final'})
    WHERE f.created > r.created AND s.score >= $t AND NOT (f)-[:CITES]->(r)
    OPTIONAL MATCH (a:Person)-[:WROTE]->(r)
    OPTIONAL MATCH (b:Person)-[:WROTE]->(f)
    RETURN r.number, r.title, r.created, f.number, f.title, f.created, s.score,
           collect(DISTINCT a.name) AS rejected_authors, collect(DISTINCT b.name) AS final_authors,
           r.url, f.url
    ORDER BY s.score DESC LIMIT $top_k
    """
    res = g.query(cypher, {"t": threshold, "top_k": top_k})
    latency_ms = (time.perf_counter() - t0) * 1000

    rows = []
    nodes = []
    edges = []
    sources = []
    for r in res.result_set:
        rows.append({
            "rejected_pep": r[0], "rejected_title": r[1], "rejected_date": r[2],
            "final_pep": r[3], "final_title": r[4], "final_date": r[5],
            "similarity_score": r[6], "rejected_authors": r[7], "final_authors": r[8]
        })
        nodes.append({"id": f"PEP-{r[0]}", "label": "PEP", "title": r[1], "status": "Rejected"})
        nodes.append({"id": f"PEP-{r[3]}", "label": "PEP", "title": r[4], "status": "Final"})
        edges.append({"source": f"PEP-{r[0]}", "target": f"PEP-{r[3]}", "type": "SIMILAR_TO", "score": r[6]})
        sources.extend([r[9], r[10]])

        # Add multi-hop author links
        for a_name in r[7]:
            if a_name:
                nodes.append({"id": f"Person-{a_name}", "label": "Person", "name": a_name})
                edges.append({"source": f"Person-{a_name}", "target": f"PEP-{r[0]}", "type": "WROTE"})
        for b_name in r[8]:
            if b_name:
                nodes.append({"id": f"Person-{b_name}", "label": "Person", "name": b_name})
                edges.append({"source": f"Person-{b_name}", "target": f"PEP-{r[3]}", "type": "WROTE"})

    return {
        "resurfaced_ideas": rows,
        "threshold": threshold,
        "subgraph": {"nodes": nodes, "edges": edges},
        "sources": list(set(sources)),
        "cypher": cypher.strip(),
        "latency_ms": round(latency_ms, 2)
    }


def get_delegates_of_superseded_peps() -> Dict[str, Any]:
    """
    Audits BDFL and PEP delegates who approved PEPs that were later superseded.
    (Solves Q12).
    """
    g = get_db_graph()
    t0 = time.perf_counter()

    cypher = """
    MATCH (d:Person)-[:DELEGATE_FOR]->(p:PEP {status:'Superseded'})
    RETURN d.name, collect(p.number) AS peps, count(p) AS count ORDER BY count DESC
    """
    res = g.query(cypher)
    latency_ms = (time.perf_counter() - t0) * 1000

    rows = []
    nodes = []
    for r in res.result_set:
        rows.append({"delegate": r[0], "superseded_peps": r[1], "count": r[2]})
        nodes.append({"id": f"Person-{r[0]}", "label": "Person", "name": r[0]})

    return {
        "delegates": rows,
        "subgraph": {"nodes": nodes, "edges": []},
        "sources": ["https://peps.python.org/"],
        "cypher": cypher.strip(),
        "latency_ms": round(latency_ms, 2)
    }


def get_peps_by_release(version: str = "3.8", status: str = "Final") -> Dict[str, Any]:
    """
    Finds PEPs that targeted a specific Python release version (e.g. '3.8', '3.12').
    (Solves Q13).
    """
    g = get_db_graph()
    t0 = time.perf_counter()

    cypher = """
    MATCH (p:PEP {status: $status})-[:TARGETS_RELEASE]->(r:Release {version: $version})
    RETURN p.number, p.title, p.status, p.templated, p.url ORDER BY p.number
    """
    res = g.query(cypher, {"status": status, "version": str(version).strip()})
    latency_ms = (time.perf_counter() - t0) * 1000

    rows = []
    nodes = []
    sources = []
    for r in res.result_set:
        rows.append({"number": r[0], "title": r[1], "status": r[2], "templated": r[3], "url": r[4]})
        nodes.append({"id": f"PEP-{r[0]}", "label": "PEP", "title": r[1], "status": r[2]})
        sources.append(r[4])

    return {
        "release": version,
        "count": len(rows),
        "peps": rows,
        "subgraph": {"nodes": nodes, "edges": []},
        "sources": sources,
        "cypher": cypher.strip(),
        "latency_ms": round(latency_ms, 2)
    }


# =============================================================================
# TIER 2: COMPOSABLE GRAPH PRIMITIVES
# =============================================================================

def search_peps(query: str, top_k: int = 5, search_type: str = "hybrid") -> Dict[str, Any]:
    """
    Performs full-text search on titles and semantic vector search on section text.
    Returns matching PEPs with titles, section snippets, and relevance scores.
    """
    g = get_db_graph()
    t0 = time.perf_counter()
    candidates = {}

    # 1. Full-text search on title
    if search_type in ("hybrid", "fulltext"):
        try:
            res_ft = g.query(
                "CALL db.idx.fulltext.queryNodes('PEP', $q) YIELD node RETURN node.number, node.title, node.status, node.url LIMIT $k",
                {"q": query, "k": top_k}
            )
            for r in res_ft.result_set:
                candidates[r[0]] = {
                    "number": r[0], "title": r[1], "status": r[2], "url": r[3],
                    "match_type": "title_fulltext", "score": 1.0, "snippet": r[1]
                }
        except Exception:
            pass

    # 2. Semantic vector search on section embeddings
    if search_type in ("hybrid", "vector") and len(candidates) < top_k:
        try:
            embed_model = get_embed_model()
            q_vec = list(embed_model.embed([query]))[0].tolist()
            res_vec = g.query("""
            CALL db.idx.vector.queryNodes('Section', 'embedding', $k, vecf32($vec)) YIELD node, score
            MATCH (p:PEP)-[:HAS_SECTION]->(node)
            RETURN p.number, p.title, p.status, p.url, node.kind, node.url, left(node.text, 200) AS snippet, score
            """, {"vec": q_vec, "k": top_k})
            
            for r in res_vec.result_set:
                num = r[0]
                dist = r[7]
                sim = round(1.0 - dist, 4)
                if num not in candidates:
                    candidates[num] = {
                        "number": num, "title": r[1], "status": r[2], "url": r[3],
                        "match_type": f"section_vector_{r[4]}", "score": sim,
                        "section_url": r[5], "snippet": r[6]
                    }
        except Exception as e:
            print(f"[search_peps] Vector search error: {e}")

    results = sorted(list(candidates.values()), key=lambda x: x["score"], reverse=True)[:top_k]
    latency_ms = (time.perf_counter() - t0) * 1000

    nodes = [{"id": f"PEP-{c['number']}", "label": "PEP", "title": c["title"], "status": c["status"]} for c in results]
    sources = [c["url"] for c in results]

    return {
        "query": query,
        "results": results,
        "subgraph": {"nodes": nodes, "edges": []},
        "sources": sources,
        "latency_ms": round(latency_ms, 2)
    }


def get_pep_details(pep_number: int) -> Dict[str, Any]:
    """
    Returns the comprehensive metadata card for a PEP, including authors, sponsors,
    delegates, target releases, venues, requirements, replacements, and section types.
    """
    g = get_db_graph()
    t0 = time.perf_counter()

    cypher = """
    MATCH (p:PEP {number: $n})
    OPTIONAL MATCH (a:Person)-[:WROTE]->(p)
    OPTIONAL MATCH (s:Person)-[:SPONSORED]->(p)
    OPTIONAL MATCH (d:Person)-[:DELEGATE_FOR]->(p)
    OPTIONAL MATCH (p)-[:TARGETS_RELEASE]->(r:Release)
    OPTIONAL MATCH (p)-[:DISCUSSED_IN]->(v:Venue)
    OPTIONAL MATCH (p)-[:REQUIRES]->(req:PEP)
    OPTIONAL MATCH (p)-[:REPLACES]->(rep:PEP)
    OPTIONAL MATCH (sup:PEP)-[:REPLACES]->(p)
    OPTIONAL MATCH (p)-[:HAS_SECTION]->(sec:Section)
    RETURN p.number, p.title, p.status, p.type, p.created, p.url, p.resolution_url, p.templated,
           collect(DISTINCT a.name) AS authors,
           collect(DISTINCT s.name) AS sponsors,
           collect(DISTINCT d.name) AS delegates,
           collect(DISTINCT r.version) AS releases,
           collect(DISTINCT v.name) AS venues,
           collect(DISTINCT req.number) AS requires,
           collect(DISTINCT rep.number) AS replaces,
           collect(DISTINCT sup.number) AS superseded_by,
           collect(DISTINCT sec.kind) AS sections
    """
    res = g.query(cypher, {"n": pep_number})
    latency_ms = (time.perf_counter() - t0) * 1000

    if not res.result_set:
        return {"error": f"PEP {pep_number} not found in knowledge graph."}

    row = res.result_set[0]
    data = {
        "number": row[0], "title": row[1], "status": row[2], "type": row[3],
        "created": row[4], "url": row[5], "resolution_url": row[6], "templated": row[7],
        "authors": row[8], "sponsors": row[9], "delegates": row[10],
        "releases": row[11], "venues": row[12], "requires": row[13],
        "replaces": row[14], "superseded_by": row[15], "available_sections": row[16]
    }

    nodes = [{"id": f"PEP-{row[0]}", "label": "PEP", "title": row[1], "status": row[2]}]
    edges = []
    for a in row[8]:
        nodes.append({"id": f"Person-{a}", "label": "Person", "name": a})
        edges.append({"source": f"Person-{a}", "target": f"PEP-{row[0]}", "type": "WROTE"})

    return {
        "pep": data,
        "subgraph": {"nodes": nodes, "edges": edges},
        "sources": [row[5]],
        "latency_ms": round(latency_ms, 2)
    }


def get_pep_sections(pep_number: int, kind: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetches full section text, heading anchor slugs, and canonical URLs
    (e.g. 'abstract', 'motivation', 'rationale', 'rejection_notice').
    """
    g = get_db_graph()
    t0 = time.perf_counter()

    cypher = """
    MATCH (p:PEP {number: $n})-[:HAS_SECTION]->(s:Section)
    WHERE ($kind IS NULL OR s.kind = $kind)
    RETURN s.kind, s.anchor, s.url, s.text, s.chars ORDER BY s.kind
    """
    res = g.query(cypher, {"n": pep_number, "kind": kind})
    latency_ms = (time.perf_counter() - t0) * 1000

    sections = []
    sources = []
    for r in res.result_set:
        sections.append({
            "kind": r[0], "anchor": r[1], "url": r[2], "text": r[3], "char_count": r[4]
        })
        sources.append(r[2])

    return {
        "pep_number": pep_number,
        "sections": sections,
        "subgraph": {"nodes": [], "edges": []},
        "sources": sources,
        "latency_ms": round(latency_ms, 2)
    }


def traverse_graph(
    start_label: str,
    start_id: Any,
    rel_types: Optional[List[str]] = None,
    direction: str = "out",
    limit: int = 25
) -> Dict[str, Any]:
    """
    Expands the 1-hop neighborhood of a starting node across specified relationship types.
    """
    g = get_db_graph()
    t0 = time.perf_counter()

    rel_pattern = ":" + "|".join(rel_types) if rel_types else ""
    id_field = "number" if start_label == "PEP" else "name" if start_label in ("Person", "Venue") else "version"
    val = int(start_id) if id_field == "number" else str(start_id)

    if direction == "out":
        arrow = f"-[r{rel_pattern}]->"
    elif direction == "in":
        arrow = f"<-[r{rel_pattern}]-"
    else:
        arrow = f"-[r{rel_pattern}]-"

    cypher = f"""
    MATCH (s:{start_label} {{{id_field}: $val}}){arrow}(t)
    RETURN labels(s)[0], s.{id_field}, type(r), labels(t)[0],
           coalesce(t.number, t.name, t.version, t.id), coalesce(t.title, t.name, '')
    LIMIT $limit
    """
    res = g.query(cypher, {"val": val, "limit": limit})
    latency_ms = (time.perf_counter() - t0) * 1000

    neighbors = []
    nodes = []
    edges = []
    for r in res.result_set:
        src_lbl, src_val, rel_type, tgt_lbl, tgt_val, tgt_name = r[0], r[1], r[2], r[3], r[4], r[5]
        neighbors.append({
            "rel_type": rel_type,
            "target_label": tgt_lbl,
            "target_id": tgt_val,
            "target_name": tgt_name
        })
        nodes.append({"id": f"{src_lbl}-{src_val}", "label": src_lbl})
        nodes.append({"id": f"{tgt_lbl}-{tgt_val}", "label": tgt_lbl, "name": tgt_name})
        edges.append({"source": f"{src_lbl}-{src_val}", "target": f"{tgt_lbl}-{tgt_val}", "type": rel_type})

    return {
        "start_node": f"{start_label}:{val}",
        "direction": direction,
        "neighbors": neighbors,
        "subgraph": {"nodes": nodes, "edges": edges},
        "sources": [f"https://peps.python.org/pep-{val:04d}/"] if start_label == "PEP" else [],
        "latency_ms": round(latency_ms, 2)
    }


def find_shortest_path(from_pep: int, to_pep: int, max_depth: int = 6) -> Dict[str, Any]:
    """
    Finds the shortest directed citation/dependency path between two PEPs.
    Checks both directions automatically.
    """
    g = get_db_graph()
    t0 = time.perf_counter()

    # Forward direction
    cypher_fwd = f"""
    MATCH (a:PEP {{number: $from}}), (b:PEP {{number: $to}})
    WITH shortestPath((a)-[:CITES*..{max_depth}]->(b)) AS p
    RETURN [n IN nodes(p) | n.number] AS route, length(p) AS hops
    """
    res = g.query(cypher_fwd, {"from": from_pep, "to": to_pep})
    route = res.result_set[0][0] if res.result_set and res.result_set[0][0] else None
    hops = res.result_set[0][1] if res.result_set and res.result_set[0][1] is not None else None
    direction = "forward"

    # Reverse direction if not found
    if not route:
        cypher_rev = f"""
        MATCH (a:PEP {{number: $to}}), (b:PEP {{number: $from}})
        WITH shortestPath((a)-[:CITES*..{max_depth}]->(b)) AS p
        RETURN [n IN nodes(p) | n.number] AS route, length(p) AS hops
        """
        res_rev = g.query(cypher_rev, {"from": from_pep, "to": to_pep})
        if res_rev.result_set and res_rev.result_set[0][0]:
            route = res_rev.result_set[0][0]
            hops = res_rev.result_set[0][1]
            direction = "reverse"

    latency_ms = (time.perf_counter() - t0) * 1000

    nodes = []
    edges = []
    sources = []
    if route:
        for p in route:
            nodes.append({"id": f"PEP-{p}", "label": "PEP"})
            sources.append(f"https://peps.python.org/pep-{p:04d}/")
        for i in range(len(route) - 1):
            edges.append({"source": f"PEP-{route[i]}", "target": f"PEP-{route[i+1]}", "type": "CITES"})

    return {
        "from_pep": from_pep,
        "to_pep": to_pep,
        "path_found": route is not None,
        "direction": direction,
        "route": route,
        "hops": hops,
        "subgraph": {"nodes": nodes, "edges": edges},
        "sources": sources,
        "latency_ms": round(latency_ms, 2)
    }


def check_relationship_absence(source_pep: int, target_pep: int, rel_types: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Formally verifies the absence of relationships between two PEPs (e.g. CITES, REPLACES, REQUIRES).
    Crucial for proving negative statements (e.g. 'PEP A never cited PEP B').
    """
    g = get_db_graph()
    t0 = time.perf_counter()

    rel_pattern = ":" + "|".join(rel_types) if rel_types else ""
    cypher = f"""
    MATCH (a:PEP {{number: $src}}), (b:PEP {{number: $tgt}})
    OPTIONAL MATCH p=(a)-[{rel_pattern}]->(b)
    RETURN p IS NOT NULL AS exists, [r IN relationships(p) | type(r)] AS rels
    """
    res = g.query(cypher, {"src": source_pep, "tgt": target_pep})
    latency_ms = (time.perf_counter() - t0) * 1000

    exists = res.result_set[0][0] if res.result_set else False
    rels = res.result_set[0][1] if res.result_set else []

    return {
        "source_pep": source_pep,
        "target_pep": target_pep,
        "relationship_exists": bool(exists),
        "relationships_found": rels,
        "absence_proven": not bool(exists),
        "latency_ms": round(latency_ms, 2)
    }


# =============================================================================
# TIER 3: GUARDED READ-ONLY CYPHER RUNNER
# =============================================================================

FORBIDDEN_CYPHER_KEYWORDS = re.compile(
    r"\b(CREATE|SET|DELETE|REMOVE|MERGE|DROP|ALTER|DETACH)\b",
    re.IGNORECASE
)

def execute_guarded_cypher(query: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Executes a read-only Cypher query against FalkorDB.
    Strictly forbids any data mutations and flags the result as unvalidated.
    """
    # 1. Mutation guard
    if FORBIDDEN_CYPHER_KEYWORDS.search(query):
        return {
            "error": "Query denied by safety guardrail: database mutations (CREATE, SET, DELETE, MERGE, DROP, etc.) are strictly prohibited.",
            "is_unvalidated": True
        }

    # 2. Limit enforcement if query doesn't specify one
    cleaned_query = query.strip()
    if "limit" not in cleaned_query.lower() and "count(" not in cleaned_query.lower():
        cleaned_query += " LIMIT 50"

    g = get_db_graph()
    t0 = time.perf_counter()
    try:
        res = g.query(cleaned_query, params or {})
        latency_ms = (time.perf_counter() - t0) * 1000
        
        # Parse result set
        rows = [list(r) for r in res.result_set]
        return {
            "query": cleaned_query,
            "row_count": len(rows),
            "rows": rows[:50],
            "is_unvalidated": True,
            "disclaimer": "⚠️ This result was generated via dynamic unvalidated Cypher. Please cross-reference with official PEP documents.",
            "subgraph": {"nodes": [], "edges": []},
            "sources": ["https://peps.python.org/"],
            "latency_ms": round(latency_ms, 2)
        }
    except Exception as e:
        return {
            "error": f"Cypher execution failed: {str(e)}",
            "query": cleaned_query,
            "is_unvalidated": True
        }


# =============================================================================
# TOOL REGISTRY & GEMINI FUNCTION CALLING DECLARATIONS
# =============================================================================

TOOL_REGISTRY = {
    # Tier 1 Recipes
    "trace_pep_lineage": trace_pep_lineage,
    "get_foundational_non_current_peps": get_foundational_non_current_peps,
    "get_author_influence": get_author_influence,
    "get_coauthor_bridges": get_coauthor_bridges,
    "get_rejected_peps_cited_later": get_rejected_peps_cited_later,
    "get_high_rejection_authors_still_cited": get_high_rejection_authors_still_cited,
    "get_unreferenced_peps": get_unreferenced_peps,
    "get_rejection_reasons": get_rejection_reasons,
    "get_replacement_similarity": get_replacement_similarity,
    "get_unlinked_similar_peps": get_unlinked_similar_peps,
    "get_resurfaced_rejected_ideas": get_resurfaced_rejected_ideas,
    "get_delegates_of_superseded_peps": get_delegates_of_superseded_peps,
    "get_peps_by_release": get_peps_by_release,

    # Tier 2 Primitives
    "search_peps": search_peps,
    "get_pep_details": get_pep_details,
    "get_pep_sections": get_pep_sections,
    "traverse_graph": traverse_graph,
    "find_shortest_path": find_shortest_path,
    "check_relationship_absence": check_relationship_absence,

    # Tier 3 Guarded Cypher
    "execute_guarded_cypher": execute_guarded_cypher
}

ALL_TOOL_FUNCTIONS = list(TOOL_REGISTRY.values())

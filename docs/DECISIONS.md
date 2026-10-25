# Architecture & Design Decision Log

This document records all formal architectural, schema, data modeling, model selection, and agent design decisions for the **Company Brain on FalkorDB** project.

---

## 1. Schema & Graph Model Decisions

| ID | Decision | Detail & Rationale |
|---|---|---|
| **D1** | Core Node Types | `PEP`, `Person`, `Section`, `Release`, `Venue`, `Status`. Deliberately avoids fine-grained code or commit nodes to maintain focus on high-level governance. |
| **D2** | Deterministic Unique Keys | `PEP.number` (integer), `Person.key` (accent-folded lowercase string), `Section.id` (`<PEP>:<kind>`), `Release.version` (`major.minor`), `Venue.name` (host or mailing list address). |
| **D3** | `REPLACES` Direction & Union | Direction points **New PEP $\rightarrow$ Old PEP**. Formed by the union of both `Replaces` and `Superseded-By` headers. Tracks `declared_in` (`replaces`, `superseded_by`, or `both`) and ownership flags (`by_new`, `by_old`) for incremental updates. |
| **D4** | Strict `CITES` Extraction | Extracted strictly from `:pep:` reStructuredText directives to ensure high precision (~1,653 links). Avoids plain-text false positives. |
| **D5** | Section Kinds | Limited to 4 high-signal section types: `abstract`, `motivation`, `rationale`, and `rejection_notice`. Avoids token bloating from raw spec bodies. |
| **D6** | Joke Status Normalization | PEPs with joke statuses (e.g., PEP 401 "April Fool!") are mapped to `Rejected`, consistent with the official Python PEP JSON API. |
| **D7** | Author Identity & Aliases | Normalized name key with accent folding. Maintains a curated alias map (`Seth Larson` $\rightarrow$ `Seth Michael Larson`, `Mariatta` $\rightarrow$ `Mariatta Wijaya`). Single-name authors (e.g., *Talin*, *Mariatta*) preserved. Non-person strings (`TODO`, `C API Working Group`) filtered. |
| **D8** | Exact-Date Temporal Ordering | All PEP dates parsed to ISO-8601 strings. Temporal precedence strictly compares exact ISO dates (`f.created > r.created`) rather than year-based comparisons. |
| **D9** | Release Schedule Exclusion | Release schedule and templated PEPs (~27 PEPs) are flagged with `templated = true` and excluded from semantic similarity checks to avoid false clusters. |
| **D10** | Symmetric Co-authorship | `CO_WROTE_WITH` links are materialized in both directions with `shared_peps` weight because FalkorDB graph algorithms (`algo.betweenness`) traverse directed edges. |
| **D11** | Stored Replacement Similarity | Semantic similarity between replacement pairs is precomputed and persisted on the `REPLACES` link at ingestion time to satisfy lineage comparison queries instantly. |
| **D12** | Betweenness Reporting Group | Due to approximation variance in graph algorithms, betweenness centrality is reported as an averaged top-6 peer group across seeds 1–5 rather than a brittle single-rank ordering. |
| **D13** | Dual Influence Metric | Author influence is reported via two complementary metrics: total citations received and count of distinct citing PEPs, with self-citations excluded by default. |
| **D14** | Exclude Self-Citations | Influence queries by default filter out citations where author wrote both PEPs (e.g., 51 of Guido van Rossum's 233 citations were self-citations). |
| **D15** | Q7 Refined Absence Scope | Unbuilt PEPs defined specifically as *Final Standards Track* PEPs with zero incoming citations and zero incoming requirements (46 PEPs). |
| **D16** | Inclusion of `type` Property | Preserves PEP classification (`Standards Track`, `Informational`, `Process`) to allow accurate filtering of normative vs informative proposals. |
| **D17** | Governance Delegate Modeling | `DELEGATE_FOR` link captures `BDFL-Delegate` and `PEP-Delegate` roles (130 PEPs). `SPONSORED` captures the proposal sponsor (109 PEPs). |
| **D18** | Dependency Modeling | `REQUIRES` relationship captures explicit prerequisite PEPs declared in headers (40 links). |
| **D19** | Normalised Target Releases | `Release` nodes normalize `Python-Version` strings to `major.minor` (e.g. `3.8`), dropping patch levels. Represents target release, not verified ship date. |
| **D20** | Discussion Venues | `Venue` nodes classify discussion threads into `forum` (`discuss.python.org`) or `mailing_list` (`mail.python.org` archives or list addresses). |
| **D21** | Status Evolution (`HAD_STATUS`) | Temporal state transitions extracted from git history (`git log --follow -G'^Status:'`). Validated on samples; fallback to current header status if omitted. |
| **D22** | Hash-Based Incremental Ingestion | Ingestion manifest stores SHA-256 content hashes. Updates remove only owned relationships, update modified nodes, and re-link without full reloads. |
| **D23** | Person Alias Resolution Table | Hardcoded dictionary for known persona name variations across author, delegate, and sponsor roles. |
| **D24** | Tiered Agent Tooling | Three-tiered agent execution model: (1) Parameterized Validated Recipes, (2) Composable Graph Primitives, (3) Guarded Read-Only Cypher labelled as unvalidated. |
| **D25** | Held-Out Question Validation | Schema v1.1 verified against 6 unseen held-out queries (H1–H6) to prevent overfitting schema to initial 11 golden questions. |

---

## 2. Model & Embedding Decisions (Gate G / Phase 2 Updates)

### **D26: Embedding Model Selection (Updated: Local FastEmbed BAAI/bge-base-en-v1.5)**
* **Selected Model:** `BAAI/bge-base-en-v1.5` via `fastembed` (GPU-accelerated on NVIDIA RTX 3050).
* **Configured Dimensionality:** **768 dimensions** (native unit-normalized output).
* **Rationale & Migration:**
  * Initial tests with `gemini-embedding-001` encountered Google AI Studio Free Tier's daily quota ceiling (1,000 requests/day).
  * Rather than waiting 9 hours for an API reset or risking further rate-limit stalls, the pipeline transitioned to a local, high-performance ONNX embedder.
  * The 850 initial Gemini embeddings were safely archived to `data/embeddings_cache_gemini_768.pkl`.
  * `BAAI/bge-base-en-v1.5` generates all 1,399 section embeddings locally in under 5 seconds with zero external API dependencies or costs.
  * Preserves 100% vector dimensionality compatibility (768-dim) with FalkorDB Schema v1.1 vector index:
    ```cypher
    CREATE VECTOR INDEX FOR (s:Section) ON (s.embedding)
      OPTIONS {dimension: 768, similarityFunction: 'cosine'}
    ```

### **D27: Agent Model Strategy & Selection**
The following Gemini models are evaluated and designated for the multi-tier agent architecture:

| Model ID | Primary Role in System | Performance & Latency Profile | Selection Rationale |
|---|---|---|---|
| **`gemini-3.5-flash`** | **Primary Agent Core (ReAct / Plan-Verify Loop)** | Balanced high speed, strong reasoning, 10s SLA | Main workhorse for question interpretation, multi-step Cypher tool coordination, and answer synthesis. Tested and verified on domain questions. |
| **`gemini-3.5-flash-lite`** | **Fast Query Classifier & Parameter Extractor** | Ultra-low latency, lightweight | Ideal for high-throughput initial intent classification (e.g., determining whether a question maps to Tier 1 Recipe, Tier 2 Primitive, or Vector search) and fast parameter extraction. |
| **`gemini-3.8-flash`** | **Deep Reflection & Ambiguity Resolver** | High capability, variable demand profile | Reserved for fallback verification on complex graph discrepancies or multi-path synthesis when deep chain-of-thought analysis is needed. |

> [!NOTE]
> Older generation models (`gemini-2.5-flash`, `gemini-2.5-flash-lite`) have been deprecated by Google for new deployments. `gemini-3.5-flash` and `gemini-3.5-flash-lite` are the designated operational models.

---

## 3. Agent Architecture & Evaluation Decisions (Phase 3)

### **D28: 3-Tier Dynamic Tool Hierarchy (`src/agent/tools.py`)**
* **Structure:**
  * **Tier 1 (Validated Institutional Recipes):** Parameterized Cypher wrappers for canonical governance patterns (Q1 lineage, Q2 PageRank non-current, Q3 author influence, Q4 betweenness bridges, Q5 rejected cited later, Q6 high-rejection authors, Q7 unreferenced final PEPs, Q8 rejection reasons, Q9 replacement similarity, Q10 unlinked conceptual twins, Q11 resurfaced rejected ideas, Q12 superseded delegates, Q13 release targets).
  * **Tier 2 (Composable Graph Primitives):** Building blocks for dynamic open-ended queries: `search_peps` (hybrid full-text + vector), `get_pep_details` (metadata card), `get_pep_sections` (text & anchors), `traverse_graph` (neighborhood expansion), `find_shortest_path` (bidirectional route), `check_relationship_absence` (negative verification).
  * **Tier 3 (Guarded Read-Only Cypher Runner):** Sandboxed fallback with regex guard preventing mutations (`CREATE`, `SET`, `DELETE`, `MERGE`, `DROP`) and attaching mandatory visual unvalidated warning banner.

### **D29: ReAct Execution Engine & Trace Auditing (`src/agent/core.py`)**
* **Core Loop:** Powered by Gemini 3.5 (`gemini-3.5-flash`) via `google-genai` SDK using native tool calling in a ReAct loop (Plan $\rightarrow$ Act $\rightarrow$ Verify $\rightarrow$ Synthesize).
* **Automatic Trace Logging:** Every agent tool execution intercepts Cypher queries, latencies, visited subgraphs, and algorithm runs, persisting structured JSON to `logs/traces/<trace_id>.json` and appending to `logs/traces.jsonl` via `src/core/logger.py`.
* **Output Standard:** Enforces (1) Direct Short Answer, (2) Evidence Table, (3) Traversal Path, (4) Canonical Sources, and (5) Limitation Disclaimers.

### **D30: Verification Harness & Kill Test (`eval/test_agent.py`)**
* Autonomous evaluation suite verifies 100% pass rate across lineage DAGs, PageRank non-current identification, influence rankings, multi-step primitive composition, and mutation denials.

### **D31: FastAPI Web Application & Interactive Graph Canvas (`src/api/`)**
* **Single-Command Architecture:** Integrated FastAPI service (`src/api/main.py`) serving both REST endpoints (`/api/chat`, `/api/graph/stats`, `/api/traces/{trace_id}`) and static frontend assets (`src/api/static/`) on port 8000.
* **Interactive Visual Graph Canvas:** Implemented via Cytoscape.js with Dagre hierarchical DAG layout for replacement lineages, color-coded node statuses (Emerald = Final, Amber = Superseded, Crimson = Withdrawn/Rejected, Purple = Person), and directed arrows.
* **Node Click Drawer:** Interactive inspection card showing PEP titles, statuses, authors, and canonical links to `peps.python.org`.
* **Live Observability:** Multi-tab layout featuring live Cypher query inspector with execution latencies (ms) and row counts.




# 🧠 Company Brain on FalkorDB: Python Governance Knowledge Graph

[![FalkorDB](https://img.shields.io/badge/GraphDB-FalkorDB-red?logo=redis)](https://www.falkordb.com/)
[![Track](https://img.shields.io/badge/Hackathon_Track-Track_3:_Company_Brain-blue)](#)
[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Cytoscape](https://img.shields.io/badge/Visualizer-Cytoscape.js-ff6b6b)](https://js.cytoscape.org/)

An enterprise-grade knowledge graph and autonomous AI agent that unlocks the **entire 30-year institutional memory and governance evolution of the Python language** through 744 Python Enhancement Proposals (PEPs).

Unlike naive document search or flat Top-K vector retrieval, **Company Brain** traverses explicit relationships in **FalkorDB** to answer complex governance questions: *who made key architectural decisions, which foundational designs were abandoned or replaced, which rejected ideas were resurrected, and which active standards are orphaned.*

---

## 🚀 Live Interactive Web App: The Visual Showpiece

Launch the full interactive application with a single command:

```powershell
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  🧠 COMPANY BRAIN ON FALKORDB         [📚 Sources & Anchors (5)]  [● FalkorDB Live]  [12,529 Elements] │
├─────────────────────────────────────────────┬──────────────────────────────────────────────────────────┤
│  💬 INSTITUTIONAL CHAT (56% WIDTH)          │  🌐 VISUAL GRAPH CANVAS (TOP-RIGHT 58% HEIGHT)           │
│                                             │  [Fit] [DAG] [Organic]                   Nodes: 11       │
│  [Quick Demo Pills]:                        │  ┌─────────────────────────────────────────────────────┐ │
│  [Lineage 566] [PageRank Top 25]            │  │        (Dustin Ingram) -[WROTE]-> (PEP 566)         │ │
│  [Author Influence] [Resurfaced Ideas]      │  │                     /         \                     │ │
│  [Walrus 572]                               │  │             (PEP 426)         (PEP 345)             │ │
│                                             │  │                     \         /                     │ │
│  User: Trace packaging lineage for PEP 566  │  │                  (PEP 314)                          │ │
│                                             │  │                      |                              │ │
│  Agent:                                     │  │      (A.M. Kuchling) -[WROTE]-> (PEP 241)           │ │
│  ### Direct Short Answer                    │  └─────────────────────────────────────────────────────┘ │
│  The packaging-metadata spec originated     ├──────────────────────────────────────────────────────────┤
│  with PEP 241 and evolved through...        │  ⚡ LIVE CYPHER & EXECUTION TRACE (BOTTOM-RIGHT 42%)     │
│                                             │  Query #1 (1 rows)                        ⚡ 1.7 ms       │
│  [Evidence Table & Formatting]              │  MATCH p=(n:PEP {number: 566})-[:REPLACES*1..8]->(o:PEP) │
│                                             │  WHERE NOT (o)-[:REPLACES]->()                           │
│                                             │  RETURN [x IN nodes(p) | x.number] AS chain...           │
├─────────────────────────────────────────────┴──────────────────────────────────────────────────────────┤
│  Input: [ Ask any question...                                                      ] [ Send 🚀 ]       │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key UI Features:
1. **Interactive Cytoscape.js Canvas (Top Right):** Automatically renders multi-hop **hierarchical branching DAGs** for proposal lineages and force-directed clusters for co-authorship.
2. **Status Color-Coding:**
   - 🟢 **Final PEPs:** Emerald Green (`#10b981`)
   - 🟠 **Superseded PEPs:** Amber Orange (`#f59e0b`)
   - 🔴 **Withdrawn / Rejected PEPs:** Crimson Red (`#ef4444`)
   - 🟣 **Persons (Authors & Delegates):** Purple (`#8b5cf6`)
   - 🔵 **Releases:** Cyan (`#06b6d4`)
3. **Clickable Node Inspector:** Tap any node on the canvas to open a slide-out card displaying title, status, authors, created date, and a direct `🔗 Open Official Specification on peps.python.org` button.
4. **Simultaneous Cypher Trace Inspector (Bottom Right):** Displays the exact Cypher query executed against FalkorDB, row counts, and latency in milliseconds in real time.
5. **Slide-Over Sources Window:** Dedicated drawer listing canonical URLs and section heading anchors (`#abstract`, `#rationale`, `#rejection-notice`).

---

## 1. Why GraphRAG Beats Plain Vector RAG (The "Kill Test")

Standard RAG (chunking text + vector similarity + top-k retrieval) fails completely on institutional governance questions:

| Question Type | Why Plain Vector RAG Fails | How FalkorDB Graph Solves It |
|---|---|---|
| **Multi-hop Lineage (Q1)** | Lineages span sequential chains of unknown depth (e.g., Packaging Metadata `566 -> {426, 345} -> 314 -> 241`). Similarity search cannot follow sequential directed edges. | Traverses variable-length directed paths `(n)-[:REPLACES*1..8]->(o)` returning exact maximal DAG chains. |
| **Centrality & Prestige (Q2, Q4)** | Plain RAG cannot identify foundational vs deprecated proposals across 700+ documents. | Runs native graph algorithms (`algo.pageRank`, `algo.betweenness`) over citation and co-authorship networks. |
| **Global Absence Queries (Q7)** | Vector similarity can never prove an edge *does not exist* anywhere across the entire corpus. | Evaluates negative pattern predicates: `WHERE NOT ()-[:CITES\|REQUIRES]->(f)`. |
| **Temporal Cross-Checks (Q5, Q6)** | Plain chunks do not enforce date-order constraints across status boundaries. | Joins `(r:PEP {status: 'Rejected'})<-[:CITES]-(f:PEP {status: 'Final'}) WHERE f.created > r.created`. |
| **Resurfaced Ideas (Q11)** | Plain RAG cannot correlate a rejected proposal with a later accepted one authored by different people without citations. | Combines semantic vector similarity with temporal ordering and citation absence across author sets. |

---

## 2. Graph Data Model (Schema v1.1)

Every node and edge is extracted deterministically from raw PEP reStructuredText headers, explicit `:pep:` role citations, and verified semantic embeddings—**zero LLM extraction hallucinations during graph building**.

```mermaid
graph LR
  Person["Person (372)"] -->|WROTE (1,159)| PEP["PEP (744)"]
  Person -->|DELEGATE_FOR (129)| PEP
  Person -->|SPONSORED (109)| PEP
  PEP -->|HAS_SECTION (1,399)| Section["Section (1,399)"]
  PEP -->|REPLACES (46)| PEP
  PEP -->|CITES (1,653)| PEP
  PEP -->|REQUIRES (40)| PEP
  PEP -->|SIMILAR_TO (2,632)| PEP
  PEP -->|TARGETS_RELEASE (546)| Release["Release (28)"]
  PEP -->|DISCUSSED_IN (294)| Venue["Venue (17)"]
  Person <-->|CO_WROTE_WITH (1,962)| Person
```

### Verified Graph Counts (12,529 Total Elements)
* **`PEP`** (744 nodes): Core proposal nodes (`number`, `title`, `status`, `created`, `type`, `url`, `content_hash`).
* **`Person`** (372 nodes): Authors, delegates, and sponsors. Normalized accent-folded keys with curated alias merging (`Seth Larson`, `Mariatta`).
* **`Section`** (1,399 nodes): High-signal sections (`abstract`, `motivation`, `rationale`, `rejection_notice`) storing text anchors and 768-dim embeddings.
* **`Release`** (28 nodes): Target Python versions (e.g. `3.8`, `3.12`), normalized to `major.minor`.
* **`Venue`** (17 nodes): Discussion channels (`discuss.python.org`, mailing lists such as `distutils-sig@python.org`).
* **10 Relationships**: `WROTE` (1,159), `REPLACES` (46), `CITES` (1,653), `HAS_SECTION` (1,399), `DELEGATE_FOR` (129), `SPONSORED` (109), `REQUIRES` (40), `TARGETS_RELEASE` (546), `DISCUSSED_IN` (294), `CO_WROTE_WITH` (1,962), `SIMILAR_TO` (2,632).

---

## 3. Autonomous Multi-Tiered AI Agent

Rather than risking hallucinated Cypher or relying on a rigid question router, the Company Brain agent employs a robust **3-tiered execution hierarchy**:

1. **Tier 1: Validated Recipes**
   * Pre-compiled, verified parameterized Cypher queries answering the 11 Golden Governance Questions (plus 6 Held-out questions). Zero syntax errors, mathematically verified against NetworkX ground truth.
2. **Tier 2: Composable Graph Primitives**
   * Atomic operations (`search_peps` with hybrid vector + full-text, `get_pep_details`, `get_pep_sections`, `traverse_graph`, `find_shortest_path`, `check_relationship_absence`) chained dynamically by the agent planner for open-ended queries.
3. **Tier 3: Guarded Read-Only Cypher**
   * Sandboxed Cypher interpreter with regex safeguards (`NO WRITES`), strict timeout, and transparent UI labelling: *"⚠️ Executed via unvalidated ad-hoc query"*.

### Embedding & Agent Models
| Capability | Model | Role in Company Brain | Status |
|---|---|---|---|
| **Embeddings** | **`BAAI/bge-base-en-v1.5`** (via FastEmbed) | Generates 768-dimensional normalized vectors locally with GPU acceleration at zero API cost. Indexed with FalkorDB Cosine Vector Index on `:Section(embedding)`. | **Live** |
| **Primary Agent Loop** | **`gemini-3.5-flash-lite`** | High-throughput, low-latency ReAct agent loop for intent planning, tool invocation, and grounded synthesis with automatic multi-model failover. | **Live** |
| **Deep Reasoning** | **`gemini-3.8-flash`** | High-capacity reasoning engine reserved for complex discrepancy resolution. | **Verified** |

---

## 4. Quickstart & Verification

### 1. Prerequisites
* Python 3.12+
* Docker & Docker Compose
* Google AI Studio API Key (for Gemini)

### 2. Environment Setup
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `.env` file:
```env
FALKORDB_HOST=localhost
FALKORDB_PORT=6379
FALKORDB_GRAPH=hackathon_brain

GEMINI_API_KEY=your_google_ai_studio_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
```

### 3. Start FalkorDB
```powershell
docker compose up -d
```

### 4. Build & Ingest Knowledge Graph
```powershell
python src/graph/load.py
```
*(Builds range indexes, full-text index, vector index, embeds all sections, and ingests all 12,529 entities in under 2 seconds from cache).*

### 5. Run Verification Suites
1. **Audit Database Parity (15 Sets):**
   ```powershell
   python eval/check_counts.py
   # 100% exact match across all nodes and relationship sets!
   ```
2. **Audit Golden Governance Questions:**
   ```powershell
   python eval/test_golden_questions.py
   # ALL 19 QUESTIONS PASSED (Q1-Q13 + H1-H6) with pre-validated ground truth!
   ```
3. **Audit Autonomous Agent:**
   ```powershell
   python eval/test_agent.py
   # ALL 5/5 AGENT EVALUATION TESTS PASSED!
   ```
4. **Audit FastAPI Backend & Web App:**
   ```powershell
   python eval/test_api.py
   # ALL 5/5 API ENDPOINTS & ASSETS PASSED!
   ```

### 6. Launch Web Application
```powershell
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```
Visit **`http://localhost:8000`**.

---

## 5. Repository Structure

```
.
├── docker-compose.yml          # FalkorDB container configuration
├── requirements.txt            # Project dependencies (falkordb, fastembed, google-genai, fastapi)
├── README.md                   # Master project documentation
├── walkthrough.md              # Illustrated, beginner-friendly story of the project
├── docs/                       # Formal architecture and governance specifications
│   ├── Company_Brain.md        # Single source of truth master specification
│   ├── DECISIONS.md            # Architecture and design decision log (D1–D31)
│   ├── DATA_MANIFEST.md        # PEP dataset metrics and provenance
│   └── AI_ASSISTANCE.md        # Hackathon AI assistance disclosure and audit log
├── data/
│   ├── peps/                   # Snapshot of python/peps (744 PEP documents)
│   ├── embeddings_cache_bge_768.pkl   # Local BGE embeddings cache (1,399 vectors)
│   └── embeddings_cache_gemini_768.pkl# Archived Gemini embeddings
├── eval/
│   ├── check_counts.py         # Count audit against expected counts
│   ├── expected_counts.json    # Target numbers for all 15 entity sets
│   ├── test_golden_questions.py# Golden questions (Q1–Q13, H1–H6) verification harness
│   ├── test_agent.py           # End-to-end agent evaluation harness
│   └── test_api.py             # FastAPI backend test suite
├── src/
│   ├── graph/
│   │   ├── parse.py            # High-performance PEP rST parser (0.35s)
│   │   └── load.py             # FalkorDB batch loader with indexes & embeddings
│   ├── core/
│   │   └── logger.py           # Structured TraceLogger (JSONL traces & subgraphs)
│   ├── agent/
│   │   ├── tools.py            # 3-Tier Toolset (Recipes, Primitives, Guarded Cypher)
│   │   ├── prompts.py          # System prompt and governance instructions
│   │   └── core.py             # ReAct execution engine with Gemini & failover
│   └── api/
│       ├── main.py             # FastAPI service (/api/chat, /api/graph/stats)
│       └── static/             # Interactive frontend (index.html, style.css, app.js)
└── logs/
    └── traces/                 # Structured JSON traces with subgraphs and latencies
```

---

## 6. Project Roadmap & Completion Status

- [x] **Phase 1: Graph Design & Verification**
  - [x] Formulated Schema v1.1 (PEPs, Persons, Sections, Releases, Venues)
  - [x] Verified FalkorDB Cypher Gotchas (G1–G14)
- [x] **Phase 2: Ingestion & Graph Construction**
  - [x] Implemented deterministic Schema v1.1 loader with alias tables
  - [x] Embedded 1,399 Section nodes using `BAAI/bge-base-en-v1.5` (768-dim) on RTX 3050 GPU
  - [x] Built Range, Full-Text, and Cosine Vector Indexes
  - [x] Audited 100% parity across all 12,529 entities in FalkorDB
- [x] **Phase 3: Autonomous Agent Implementation**
  - [x] Built Tier 1 Validated Recipes & Tier 2 Composable Primitives
  - [x] Implemented Guarded Read-Only Cypher Runner (Tier 3)
  - [x] Built ReAct loop using `gemini-3.5-flash-lite` with automatic model failover
  - [x] Integrated structured JSON trace logging (`src/core/logger.py`)
- [x] **Phase 4: API Backend Service**
  - [x] Built FastAPI service exposing `/api/chat`, `/api/graph/stats`, and `/api/traces`
- [x] **Phase 5: Interactive Web App & Visual Showpiece**
  - [x] Built split-screen interface with expanded chat (56% width)
  - [x] Implemented Cytoscape.js DAG branching layout for lineages
  - [x] Integrated simultaneous live Cypher query & latency inspector
  - [x] Built clickable node inspector drawer with links to `peps.python.org`
  - [x] Built slide-over Sources & Citations window
- [x] **Final Delivery & Hackathon Evaluation**
  - [x] Passed all 19 Golden Governance Questions
  - [x] Passed all Agent Evaluation Tests (5/5)
  - [x] Passed all API Service Tests (5/5)

---

## 7. License
Distributed under the MIT License. See `LICENSE` for details.

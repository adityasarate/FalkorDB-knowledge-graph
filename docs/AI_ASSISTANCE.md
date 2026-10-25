# AI Assistance Disclosure & Development Log

As required by the **Graph Hacks Hackathon (Rule 2.3)**, this document provides a comprehensive disclosure of all AI coding assistants, models, and tools utilized during the design, validation, and implementation of the **Company Brain on FalkorDB** project.

---

## 1. Summary of AI Tools Used

| Tool / Model | Version / Provider | Role & Scope of Use |
|---|---|---|
| **Antigravity AI Agent** | Google DeepMind / Antigravity | Pair programming assistant for codebase navigation, writing test harnesses, verifying schema constraints, and generating documentation. |
| **Gemini 3.8 Flash** | Google AI Studio | Core reasoning model driving the agentic pair-programming workflow and model exploration. |
| **gemini-embedding-001** | Google GenAI SDK (`google-genai` 2.31.0) | Production embedding model for 768-dimensional vector embeddings of PEP section texts (`abstract`, `motivation`, `rationale`, `rejection_notice`). |
| **gemini-3.5-flash / gemini-3.5-flash-lite** | Google GenAI SDK | Production models selected for the Company Brain agentic reasoning loop and parameter routing. |

---

## 2. Scope of Assistance & Authorship Statement

All code, Cypher queries, graph schemas, and system architectures have been designed, reviewed, and tested under human direction during the official hackathon window (October 15–18, 2026).

### AI Was Used For:
1. **Schema Design & Query Optimization:**
   - Reviewing draft Cypher queries against FalkorDB documentation to avoid known gotchas (Gotchas G1 to G14, including directional graph algorithms, `collect(DISTINCT ...)`, and `shortestPath` constraints).
   - Formulating Schema v1.1 refinements (`Release`, `Venue`, `DELEGATE_FOR`, `SPONSORED`, `REQUIRES`).
2. **Harness & Verification Scripts:**
   - Authoring [scripts/verify_setup.py](file:///d:/Graph%20hacks/scripts/verify_setup.py) to test the local Python-to-FalkorDB Docker bridge.
   - Authoring [scripts/verify_gemini.py](file:///d:/Graph%20hacks/scripts/verify_gemini.py) to validate Gemini API generation and 768-dimensional vector embedding generation.
3. **Data Quality & Edge Cases:**
   - Identifying alias collisions (e.g. `Seth Larson` vs `Seth Michael Larson`, `Mariatta` vs `Mariatta Wijaya`).
   - Identifying single-name authors (Talin, Mariatta, Aahz) to ensure they are not dropped by author parsing filters.

### AI Was NOT Used For:
1. **Graph Building:** The graph is built deterministically from reStructuredText headers and `:pep:` directives using pure Python parsers. No LLM hallucinations or LLM extraction is used during graph construction.
2. **Ground Truth Validation:** Every result for the 11 golden queries and 6 held-out queries is verified against independent pure-Python calculations (NetworkX / set operations).

---

## 3. Session Log

| Date | Phase | Activities & AI Prompts | Outcome |
|---|---|---|---|
| **2026-10-15** | Phase 1: Inception & Scoping | Defined 11 golden questions, verified against plain top-k retrieval limitations ("kill test"). | Schema v1.0 drafted. |
| **2026-10-16** | Phase 1: Review & Schema v1.1 | Independent review executed against HEAD of `python/peps`. Formulated Schema v1.1 additions (`DELEGATE_FOR`, `Release`, `Venue`). | Consolidated [docs/Company_Brain.md](file:///d:/Graph%20hacks/docs/Company_Brain.md). |
| **2026-10-25** | Gate G: Environment & API Setup | Smoke-tested FalkorDB in Docker. Tested Google GenAI API with `gemini-embedding-001` (768-dim) and `gemini-3.5-flash`. Documented architectural decisions. | FalkorDB and Gemini API fully verified. Created [scripts/verify_gemini.py](file:///d:/Graph%20hacks/scripts/verify_gemini.py) and [docs/DECISIONS.md](file:///d:/Graph%20hacks/docs/DECISIONS.md). |
| **2026-10-25** | Phase 2: Ingestion & FastEmbed | Installed FastEmbed with `BAAI/bge-base-en-v1.5` for local GPU embeddings on RTX 3050. Built `src/graph/load.py` with Range, Full-Text, and Vector Indexes. Ingested all 12,529 entities. | 100% database audit parity verified via `eval/check_counts.py`. |
| **2026-10-25** | Phase 2: Golden Question Audit | Built `eval/test_golden_questions.py` executing all 19 queries (Q1–Q13 + H1–H6) against FalkorDB. | 19/19 queries passed with 100% pre-validated match against ground truth. |
| **2026-10-25** | Phase 3: Autonomous Agent | Implemented 3-Tier Toolset (`src/agent/tools.py`), system prompts (`src/agent/prompts.py`), and ReAct loop with failover (`src/agent/core.py`). | 5/5 agent evaluation tests passed in `eval/test_agent.py`. |
| **2026-10-25** | Phase 4 & 5: FastAPI & Interactive Web App | Built FastAPI service (`src/api/main.py`) and split-screen Cytoscape.js frontend with Dagre DAG layout, simultaneous live Cypher trace inspector, node click drawer, and slide-over sources window. | Live app running at `http://localhost:8000`. 5/5 backend tests passed in `eval/test_api.py`. |



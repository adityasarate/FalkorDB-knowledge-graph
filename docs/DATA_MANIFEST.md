# Data Manifest & Provenance

This document tracks the dataset source, commit snapshot, file inventory, and verification statistics for the **Company Brain on FalkorDB** project.

---

## 1. Source Repository

* **Upstream URL:** `https://github.com/python/peps.git`
* **Local Folder:** `data/peps/peps/`
* **Snapshot Commit:** `b80c7bf8d5a89fc47b732504a9e1219b79677531`
* **Snapshot Date:** 2026-10-14
* **Licence:** Public domain / CC0 (711 of 744 explicit CC0/public domain statements; remaining 33 contain standard open-source notices).

---

## 2. Inventory & Parsing Metrics

| Metric | Measured Count | Notes |
|---|---|---|
| **Total PEP files parsed** | **744** | `pep-*.rst` files plus `pep-*/index.rst` |
| **PEPs with mandatory headers** | 744 / 744 | `PEP`, `Title`, `Status`, `Type`, `Created`, `Author` |
| **Status Distribution** | | |
| - Final | 375 | Standard track and approved specifications |
| - Rejected | 132 | Includes PEP 401 ("April Fool!") mapped to Rejected |
| - Withdrawn | 72 | Author-withdrawn proposals |
| - Draft | 55 | Proposals under active iteration |
| - Active | 37 | Living process/governance PEPs (e.g. PEP 1) |
| - Deferred | 36 | Postponed decisions |
| - Superseded | 25 | Obsoleted by newer PEPs |
| - Accepted | 11 | Approved but pending release |
| - Provisional | 1 | Released provisionally |
| **Type Distribution** | | |
| - Standards Track | 587 | Normative technical additions to Python |
| - Informational | 104 | Guidelines, commentary, non-normative specs |
| - Process | 53 | Governance and release management procedures |
| **Relationship Extraction** | | |
| - Authors (raw strings) | 373 | Normalized to 370 distinct persons after alias merging |
| - Additional Persons | 2 | Distinct individuals appearing exclusively as Delegate or Sponsor (`370 + 2 = 372` total `Person` nodes) |
| - `WROTE` links | 1,159 | Author-to-PEP relationships |
| - `REPLACES` links | 46 | Combined from `Replaces` (41) and `Superseded-By` (32) |
| - `CITES` links | 1,653 | Explicit `:pep:` role citations (self-citations excluded) |
| - `DELEGATE_FOR` links | 129 | BDFL-Delegate (83) and PEP-Delegate (47) minus group names |
| - `SPONSORED` links | 109 | Explicit core sponsor declarations |
| - `REQUIRES` links | 40 | Explicit prerequisite dependencies across 28 PEPs |
| - `TARGETS_RELEASE` links | 546 | Mapped to 28 distinct `Release` nodes (major.minor) |
| - `DISCUSSED_IN` links | 294 | Mapped to 17 distinct `Venue` nodes |
| - `CO_WROTE_WITH` links | 1,962 | Bidirectional co-authorship collaboration links |
| - Section nodes | 1,399 | Abstract (686), Motivation (283), Rationale (377), Rejection Notice (53) |
| - `SIMILAR_TO` links | 2,632 | Pairwise semantic section similarity edges ($\ge 0.85$ cosine similarity) |
| **Total Graph Entities** | **12,529** | **2,560 Nodes + 9,969 Relationships** in FalkorDB |

---

## 3. Verification Command
To reproduce the file inventory verification:
```powershell
python -c "import glob; print('Count:', len(glob.glob('data/peps/peps/pep-*.rst')) + len(glob.glob('data/peps/peps/pep-*/index.rst')))"
# Expected Output: Count: 744
```

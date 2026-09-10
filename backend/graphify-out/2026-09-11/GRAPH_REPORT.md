# Graph Report - backend  (2026-09-10)

## Corpus Check
- 5 files · ~3,881 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 48 nodes · 64 edges · 8 communities (5 shown, 2 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 5 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d62f091b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- pretrain_utils.py
- SyntheticFragmentCorpus
- ndarray
- Product Requirements Document (PRD)
- 3. Phased Architecture & Functional Requirements
- .blockify
- CLAUDE.md

## God Nodes (most connected - your core abstractions)
1. `SyntheticFragmentCorpus` - 14 edges
2. `Product Requirements Document (PRD)` - 8 edges
3. `_rand_text()` - 5 edges
4. `Triplet` - 5 edges
5. `3. Phased Architecture & Functional Requirements` - 5 edges
6. `get_optimal_execution_providers()` - 2 edges
7. `_make_pdf()` - 2 edges
8. `_make_zip()` - 2 edges
9. `_make_elf()` - 2 edges
10. `_make_pe()` - 2 edges

## Surprising Connections (you probably didn't know these)
- None detected - all connections are within the same source files.

## Import Cycles
- None detected.

## Communities (8 total, 2 thin omitted)

### Community 0 - "pretrain_utils.py"
Cohesion: 0.29
Nodes (8): get_optimal_execution_providers(), _make_elf(), _make_pdf(), _make_pe(), _make_zip(), _rand_text(), Phase 1 (FR1.0): hardware detection + synthetic fragmentation corpus. Air-…, Return ORT provider chain: CUDA first if usable, else CPU only. Never raises.…

### Community 1 - "SyntheticFragmentCorpus"
Cohesion: 0.36
Nodes (4): Blockify benign files into 4KB units and emit degraded contrastive triplets.…, SyntheticFragmentCorpus, Triplet, NamedTuple

### Community 2 - "ndarray"
Cohesion: 0.22
Nodes (5): Cut the tail (lose footer) and zero the remainder., Out-of-order write simulation: permute equal sub-fragments., Insert random junk at a random offset; keep block size fixed., Slack padding: zero a random tail *or* random interior run., ndarray

### Community 3 - "Product Requirements Document (PRD)"
Cohesion: 0.25
Nodes (7): 1. Executive Summary, 2. Strict Engineering Constraints (CRITICAL), 4. Mathematical Specifications, 5. Technology Stack & Dependencies, 6. Required Outputs from Coding Agent, 7. Evaluator Traceability Matrix (PS wording → FR), Product Requirements Document (PRD)

### Community 4 - "3. Phased Architecture & Functional Requirements"
Cohesion: 0.40
Nodes (5): 3. Phased Architecture & Functional Requirements, Phase 1: Byte-Level Triage (Pre-Processing Engine), Phase 2: Signature, Structural, Intelligent & Global Reassembly (SHT Engine), Phase 3: Air-Gapped Semantic Indexing & LLM Triage, Phase 4: Evidential Confidence Matrix (Section 63 Compliance)

## Knowledge Gaps
- **11 isolated node(s):** `graphify`, `1. Executive Summary`, `2. Strict Engineering Constraints (CRITICAL)`, `Phase 1: Byte-Level Triage (Pre-Processing Engine)`, `Phase 2: Signature, Structural, Intelligent & Global Reassembly (SHT Engine)` (+6 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 24 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SyntheticFragmentCorpus` connect `SyntheticFragmentCorpus` to `pretrain_utils.py`, `ndarray`, `.blockify`?**
  _High betweenness centrality (0.279) - this node is a cross-community bridge._
- **Why does `Product Requirements Document (PRD)` connect `Product Requirements Document (PRD)` to `3. Phased Architecture & Functional Requirements`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Why does `Triplet` connect `SyntheticFragmentCorpus` to `pretrain_utils.py`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **What connects `graphify`, `1. Executive Summary`, `2. Strict Engineering Constraints (CRITICAL)` to the rest of the system?**
  _11 weakly-connected nodes found - possible documentation gaps or missing edges._
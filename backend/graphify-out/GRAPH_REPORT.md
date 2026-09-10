# Graph Report - backend  (2026-09-11)

## Corpus Check
- 6 files · ~5,232 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 76 nodes · 118 edges · 13 communities (6 shown, 6 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 9 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d62f091b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- pretrain_utils.py
- .sample
- ndarray
- Product Requirements Document (PRD)
- triage_scorer.py
- SyntheticFragmentCorpus
- CLAUDE.md
- FastBlockTriage
- get_optimal_execution_providers
- .shuffle_fragments
- .insert_bytes
- .zero_fill

## God Nodes (most connected - your core abstractions)
1. `SyntheticFragmentCorpus` - 18 edges
2. `Product Requirements Document (PRD)` - 8 edges
3. `_rand_text()` - 7 edges
4. `build_labeled_blocks()` - 7 edges
5. `FastBlockTriage` - 7 edges
6. `Triplet` - 5 edges
7. `_batch_stats()` - 5 edges
8. `train_model()` - 5 edges
9. `3. Phased Architecture & Functional Requirements` - 5 edges
10. `get_optimal_execution_providers()` - 4 edges

## Surprising Connections (you probably didn't know these)
- `build_labeled_blocks()` --uses--> `SyntheticFragmentCorpus`  [INFERRED]
  engine/triage_scorer.py → engine/pretrain_utils.py
- `FastBlockTriage` --uses--> `SyntheticFragmentCorpus`  [INFERRED]
  engine/triage_scorer.py → engine/pretrain_utils.py
- `train_model()` --uses--> `SyntheticFragmentCorpus`  [INFERRED]
  engine/triage_scorer.py → engine/pretrain_utils.py
- `build_labeled_blocks()` --calls--> `_rand_text()`  [EXTRACTED]
  engine/triage_scorer.py → engine/pretrain_utils.py

## Import Cycles
- None detected.

## Communities (13 total, 6 thin omitted)

### Community 0 - "pretrain_utils.py"
Cohesion: 0.39
Nodes (6): _make_elf(), _make_pdf(), _make_pe(), _make_zip(), _rand_text(), Phase 1 (FR1.0): hardware detection + synthetic fragmentation corpus. Air-…

### Community 3 - "Product Requirements Document (PRD)"
Cohesion: 0.15
Nodes (12): 1. Executive Summary, 2. Strict Engineering Constraints (CRITICAL), 3. Phased Architecture & Functional Requirements, 4. Mathematical Specifications, 5. Technology Stack & Dependencies, 6. Required Outputs from Coding Agent, 7. Evaluator Traceability Matrix (PS wording → FR), Phase 1: Byte-Level Triage (Pre-Processing Engine) (+4 more)

### Community 4 - "triage_scorer.py"
Cohesion: 0.20
Nodes (14): _batch_stats(), BlockClassifierCNN(), build_labeled_blocks(), calculate_byte_frequency(), _CNNFactory, export_to_onnx(), ndarray, Phase 1 (FR1.1-FR1.4): entropy stats, 1D-CNN block triage, ONNX export, fast… (+6 more)

### Community 5 - "SyntheticFragmentCorpus"
Cohesion: 0.50
Nodes (3): Blockify benign files into 4KB units and emit degraded contrastive triplets.…, Split into (n, block_size) uint8; last block zero-padded (slack)., SyntheticFragmentCorpus

### Community 8 - "FastBlockTriage"
Cohesion: 0.28
Nodes (6): calculate_shannon_entropy(), FastBlockTriage, ORT runtime with heuristic bypass and pre-allocated batch buffers., u8: (B, 4096) uint8, B <= batch_size. Returns (label_idx[B], confidence[B])…, Triage a whole image (bytes, flat uint8, or (N, 4096) uint8). Returns (labels,…, Shannon entropy in bits/byte, range [0.0, 8.0].

### Community 9 - "get_optimal_execution_providers"
Cohesion: 0.40
Nodes (4): get_optimal_execution_providers(), Return ORT provider chain: CUDA first if usable, else CPU only. Never raises.…, _boost_process_priority(), Windows 11 + hybrid Intel (P/E cores) demotes a console process to efficiency…

## Knowledge Gaps
- **11 isolated node(s):** `graphify`, `1. Executive Summary`, `2. Strict Engineering Constraints (CRITICAL)`, `Phase 1: Byte-Level Triage (Pre-Processing Engine)`, `Phase 2: Signature, Structural, Intelligent & Global Reassembly (SHT Engine)` (+6 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 34 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SyntheticFragmentCorpus` connect `SyntheticFragmentCorpus` to `pretrain_utils.py`, `.sample`, `ndarray`, `triage_scorer.py`, `FastBlockTriage`, `.shuffle_fragments`, `.insert_bytes`, `.zero_fill`?**
  _High betweenness centrality (0.305) - this node is a cross-community bridge._
- **Why does `FastBlockTriage` connect `FastBlockTriage` to `get_optimal_execution_providers`, `triage_scorer.py`, `SyntheticFragmentCorpus`?**
  _High betweenness centrality (0.085) - this node is a cross-community bridge._
- **Why does `build_labeled_blocks()` connect `triage_scorer.py` to `pretrain_utils.py`, `SyntheticFragmentCorpus`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `SyntheticFragmentCorpus` (e.g. with `build_labeled_blocks()` and `FastBlockTriage`) actually correct?**
  _`SyntheticFragmentCorpus` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `graphify`, `1. Executive Summary`, `2. Strict Engineering Constraints (CRITICAL)` to the rest of the system?**
  _11 weakly-connected nodes found - possible documentation gaps or missing edges._
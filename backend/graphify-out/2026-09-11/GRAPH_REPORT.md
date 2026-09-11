# Graph Report - backend  (2026-09-11)

## Corpus Check
- 11 files · ~11,986 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 180 nodes · 327 edges · 11 communities (8 shown, 1 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 17 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c6691344`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- graph_reassembly.py
- SiameseAdjacency
- SyntheticFragmentCorpus
- Product Requirements Document (PRD)
- triage_scorer.py
- JpegContext
- CLAUDE.md
- carver_ml.py
- ImageBlocks

## God Nodes (most connected - your core abstractions)
1. `SyntheticFragmentCorpus` - 27 edges
2. `main()` - 13 edges
3. `validate_structural_coherence()` - 11 edges
4. `SiameseAdjacency` - 11 edges
5. `ImageBlocks` - 10 edges
6. `GlobalFragmentResolver` - 9 edges
7. `carve()` - 9 edges
8. `JpegContext` - 8 edges
9. `validate_carve()` - 8 edges
10. `Product Requirements Document (PRD)` - 8 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `validate_structural_coherence()`  [EXTRACTED]
  tests/test_reassembly.py → engine/carver_ml.py
- `main()` --calls--> `SiameseAdjacency`  [EXTRACTED]
  tests/test_reassembly.py → engine/carver_ml.py
- `main()` --calls--> `GlobalFragmentResolver`  [EXTRACTED]
  tests/test_reassembly.py → engine/graph_reassembly.py
- `main()` --uses--> `SyntheticFragmentCorpus`  [INFERRED]
  tests/test_reassembly.py → engine/pretrain_utils.py
- `split_shuffled()` --uses--> `SyntheticFragmentCorpus`  [INFERRED]
  tests/test_reassembly.py → engine/pretrain_utils.py

## Import Cycles
- None detected.

## Communities (11 total, 1 thin omitted)

### Community 0 - "graph_reassembly.py"
Cohesion: 0.17
Nodes (18): Phase 2 (FR2.3): global fragment ordering via the Hungarian algorithm. Affinity…, _make_elf(), _make_jpeg(), _make_pdf(), _make_pe(), _make_zip(), _rand_text(), Phase 1 (FR1.0): hardware detection + synthetic fragmentation corpus. Air-… (+10 more)

### Community 1 - "SiameseAdjacency"
Cohesion: 0.14
Nodes (11): ndarray, ORT runtime. N blocks -> one batched pass for embeddings -> NxN P_adjacent via…, M[i, j] = P(block j directly follows block i). Diagonal is 0., SiameseAdjacency, Chain, GlobalFragmentResolver, ndarray, Returns succ[i] = j or -1, via Hungarian on the augmented matrix. (+3 more)

### Community 2 - "SyntheticFragmentCorpus"
Cohesion: 0.10
Nodes (22): ensure_siamese_model(), FR2.0 -> FR2.1 hand-off: keep closed streams whose C_struct >= min_struct;…, validate_carve(), ndarray, Blockify benign files into 4KB units and emit degraded contrastive triplets.…, Split into (n, block_size) uint8; last block zero-padded (slack)., Cut the tail (lose footer) and zero the remainder., Out-of-order write simulation: permute equal sub-fragments. (+14 more)

### Community 3 - "Product Requirements Document (PRD)"
Cohesion: 0.15
Nodes (12): 1. Executive Summary, 2. Strict Engineering Constraints (CRITICAL), 3. Phased Architecture & Functional Requirements, 4. Mathematical Specifications, 5. Technology Stack & Dependencies, 6. Required Outputs from Coding Agent, 7. Evaluator Traceability Matrix (PS wording → FR), Phase 1: Byte-Level Triage (Pre-Processing Engine) (+4 more)

### Community 4 - "triage_scorer.py"
Cohesion: 0.11
Nodes (22): get_optimal_execution_providers(), Return ORT provider chain: CUDA first if usable, else CPU only. Never raises.…, _batch_stats(), BlockClassifierCNN(), _boost_process_priority(), build_labeled_blocks(), calculate_byte_frequency(), _CNNFactory (+14 more)

### Community 5 - "JpegContext"
Cohesion: 0.12
Nodes (9): build_pool_context(), JpegContext, PdfContext, Huffman tables, component layout and restart interval parsed from a JPEG header…, Decode entropy-coded `data` (no markers inside). Returns (complete_mcus,…, Decode the restart interval spanning the A|B join, using cached per-fragment…, Cross-reference table (FR2.1: '/XRef validity') used as an absolute position…, Absolute block index of `frag`, or None when the xref gives no consistent… (+1 more)

### Community 8 - "carver_ml.py"
Cohesion: 0.12
Nodes (23): build_pair_dataset(), export_siamese_onnx(), _FragInfo, _jpeg_scan_stats(), _jpeg_tests(), _pdf_tests(), Phase 2 (FR2.1-FR2.2): Sequential Hypothesis Testing on file structure +…, C_struct in [0, 1]: SHT posterior that `data` is a structurally valid `mime`… (+15 more)

### Community 9 - "ImageBlocks"
Cohesion: 0.20
Nodes (4): ImageBlocks, Read-only block accessor over a memory-mapped image. Indexing returns a *copy*,…, (count, block_size) uint8 copy; the unit the triage/affinity paths consume., mmap

## Knowledge Gaps
- **11 isolated node(s):** `graphify`, `1. Executive Summary`, `2. Strict Engineering Constraints (CRITICAL)`, `Phase 1: Byte-Level Triage (Pre-Processing Engine)`, `Phase 2: Signature, Structural, Intelligent & Global Reassembly (SHT Engine)` (+6 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 74 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SyntheticFragmentCorpus` connect `SyntheticFragmentCorpus` to `carver_ml.py`, `graph_reassembly.py`, `triage_scorer.py`?**
  _High betweenness centrality (0.239) - this node is a cross-community bridge._
- **Why does `JpegContext` connect `JpegContext` to `carver_ml.py`?**
  _High betweenness centrality (0.082) - this node is a cross-community bridge._
- **Why does `SiameseAdjacency` connect `SiameseAdjacency` to `carver_ml.py`, `graph_reassembly.py`, `SyntheticFragmentCorpus`, `triage_scorer.py`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `SyntheticFragmentCorpus` (e.g. with `build_pair_dataset()` and `train_siamese()`) actually correct?**
  _`SyntheticFragmentCorpus` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `graphify`, `1. Executive Summary`, `2. Strict Engineering Constraints (CRITICAL)` to the rest of the system?**
  _11 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `SiameseAdjacency` be split into smaller, more focused modules?**
  _Cohesion score 0.1380952380952381 - nodes in this community are weakly interconnected._
- **Should `SyntheticFragmentCorpus` be split into smaller, more focused modules?**
  _Cohesion score 0.10084033613445378 - nodes in this community are weakly interconnected._
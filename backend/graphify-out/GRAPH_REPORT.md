# Graph Report - backend  (2026-09-14)

## Corpus Check
- 16 files · ~18,623 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 265 nodes · 469 edges · 16 communities (11 shown, 3 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 18 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c8b73c04`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- .resolve
- explainability.py
- SyntheticFragmentCorpus
- Product Requirements Document (PRD)
- triage_scorer.py
- JpegContext
- CLAUDE.md
- carver_ml.py
- graph_reassembly.py
- llm_triage.py
- test_reassembly.py
- ForensicReliabilityScorer
- rules/graphify.md
- workflows/graphify.md

## God Nodes (most connected - your core abstractions)
1. `SyntheticFragmentCorpus` - 28 edges
2. `main()` - 20 edges
3. `validate_structural_coherence()` - 13 edges
4. `SiameseAdjacency` - 11 edges
5. `ForensicReliabilityScorer` - 10 edges
6. `ImageBlocks` - 10 edges
7. `GlobalFragmentResolver` - 9 edges
8. `detect_header()` - 9 edges
9. `carve()` - 9 edges
10. `calculate_shannon_entropy()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `main()` --uses--> `SyntheticFragmentCorpus`  [INFERRED]
  tests/test_reassembly.py → engine/pretrain_utils.py
- `split_shuffled()` --uses--> `SyntheticFragmentCorpus`  [INFERRED]
  tests/test_reassembly.py → engine/pretrain_utils.py
- `main()` --calls--> `validate_structural_coherence()`  [EXTRACTED]
  tests/test_reassembly.py → engine/carver_ml.py
- `main()` --calls--> `ensure_siamese_model()`  [EXTRACTED]
  tests/test_reassembly.py → engine/carver_ml.py
- `main()` --calls--> `ForensicReliabilityScorer`  [EXTRACTED]
  tests/test_reassembly.py → engine/report_gen.py

## Import Cycles
- None detected.

## Communities (16 total, 3 thin omitted)

### Community 0 - ".resolve"
Cohesion: 0.22
Nodes (5): Chain, ndarray, Returns succ[i] = j or -1, via Hungarian on the augmented matrix., Order a pool of orphan fragments. Pools over `max_pool` are solved in slices.…, ResolveResult

### Community 1 - "explainability.py"
Cohesion: 0.15
Nodes (16): batch_block_attributions(), extract_reassembly_rationale(), generate_block_attributions(), _get_session(), _MockChain, _MockResolveResult, ndarray, FR1.5 / FR2.4: model explainability for the forensic pipeline. FR1.5 – SHAP-… (+8 more)

### Community 2 - "SyntheticFragmentCorpus"
Cohesion: 0.16
Nodes (10): ndarray, Blockify benign files into 4KB units and emit degraded contrastive triplets.…, Split into (n, block_size) uint8; last block zero-padded (slack)., Cut the tail (lose footer) and zero the remainder., Out-of-order write simulation: permute equal sub-fragments., Insert random junk at a random offset; keep block size fixed., Slack padding: zero a random tail *or* random interior run., SyntheticFragmentCorpus (+2 more)

### Community 3 - "Product Requirements Document (PRD)"
Cohesion: 0.15
Nodes (12): 1. Executive Summary, 2. Strict Engineering Constraints (CRITICAL), 3. Phased Architecture & Functional Requirements, 4. Mathematical Specifications, 5. Technology Stack & Dependencies, 6. Required Outputs from Coding Agent, 7. Evaluator Traceability Matrix (PS wording → FR), Phase 1: Byte-Level Triage (Pre-Processing Engine) (+4 more)

### Community 4 - "triage_scorer.py"
Cohesion: 0.12
Nodes (20): _batch_stats(), BlockClassifierCNN(), _boost_process_priority(), build_labeled_blocks(), calculate_byte_frequency(), _CNNFactory, export_to_onnx(), FastBlockTriage (+12 more)

### Community 5 - "JpegContext"
Cohesion: 0.12
Nodes (9): build_pool_context(), JpegContext, PdfContext, Huffman tables, component layout and restart interval parsed from a JPEG header…, Decode entropy-coded `data` (no markers inside). Returns (complete_mcus,…, Decode the restart interval spanning the A|B join, using cached per-fragment…, Cross-reference table (FR2.1: '/XRef validity') used as an absolute position…, Absolute block index of `frag`, or None when the xref gives no consistent… (+1 more)

### Community 8 - "carver_ml.py"
Cohesion: 0.12
Nodes (24): build_pair_dataset(), ensure_siamese_model(), export_siamese_onnx(), _FragInfo, _jpeg_scan_stats(), _jpeg_tests(), _pdf_tests(), Phase 2 (FR2.1-FR2.2): Sequential Hypothesis Testing on file structure +… (+16 more)

### Community 9 - "graph_reassembly.py"
Cohesion: 0.10
Nodes (23): Phase 2 (FR2.3): global fragment ordering via the Hungarian algorithm. Affinity…, _make_elf(), _make_jpeg(), _make_pdf(), _make_pe(), _make_zip(), _rand_text(), Phase 1 (FR1.0): hardware detection + synthetic fragmentation corpus. Air-… (+15 more)

### Community 11 - "llm_triage.py"
Cohesion: 0.10
Nodes (22): _detect_vram_mb(), DeterministicPatternFilter, _get_filter(), _get_llm(), LocalForensicLLM, _luhn_valid(), _normalise_llm_output(), PatternResult (+14 more)

### Community 12 - "test_reassembly.py"
Cohesion: 0.08
Nodes (33): ndarray, ORT runtime. N blocks -> one batched pass for embeddings -> NxN P_adjacent via…, M[i, j] = P(block j directly follows block i). Diagonal is 0., SiameseAdjacency, GlobalFragmentResolver, FR2.0 -> FR2.1 hand-off: keep closed streams whose C_struct >= min_struct;…, tau: cost of leaving a block without successor/predecessor. A link is only…, validate_carve() (+25 more)

### Community 13 - "ForensicReliabilityScorer"
Cohesion: 0.16
Nodes (10): export_evaluation_payload(), ForensicReliabilityScorer, C_struct: SHT structural coherence (FR2.1) + normalised assignment residual…, Δ_ent: entropy deviation from expected (FR1.1). Normalised to [0, 1]., C_sem: aggregate Siamese continuity across the reconstructed chain (FR2.2,…, Compute full breakdown. `fragments` + `chain_order` are needed for C_sem., Structured JSON payload for downstream PDF/report generation (FR4.2)., Structured breakdown of the reliability score S. (+2 more)

## Knowledge Gaps
- **15 isolated node(s):** `_MockChain`, `_MockResolveResult`, `graphify`, `Workflow: graphify`, `graphify` (+10 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 118 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SyntheticFragmentCorpus` connect `SyntheticFragmentCorpus` to `carver_ml.py`, `graph_reassembly.py`, `test_reassembly.py`, `triage_scorer.py`?**
  _High betweenness centrality (0.151) - this node is a cross-community bridge._
- **Why does `main()` connect `test_reassembly.py` to `carver_ml.py`, `graph_reassembly.py`, `SyntheticFragmentCorpus`, `ForensicReliabilityScorer`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Why does `JpegContext` connect `JpegContext` to `carver_ml.py`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `SyntheticFragmentCorpus` (e.g. with `build_pair_dataset()` and `train_siamese()`) actually correct?**
  _`SyntheticFragmentCorpus` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `_MockChain`, `_MockResolveResult`, `graphify` to the rest of the system?**
  _15 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `triage_scorer.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12307692307692308 - nodes in this community are weakly interconnected._
- **Should `JpegContext` be split into smaller, more focused modules?**
  _Cohesion score 0.11764705882352941 - nodes in this community are weakly interconnected._
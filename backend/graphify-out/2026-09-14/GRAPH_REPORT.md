# Graph Report - backend  (2026-09-14)

## Corpus Check
- 16 files · ~18,512 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 265 nodes · 455 edges · 16 communities (11 shown, 3 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 18 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c8b73c04`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- pretrain_utils.py
- explainability.py
- SyntheticFragmentCorpus
- Product Requirements Document (PRD)
- triage_scorer.py
- JpegContext
- CLAUDE.md
- carver_ml.py
- ImageBlocks
- llm_triage.py
- graph_reassembly.py
- detect_header
- rules/graphify.md
- workflows/graphify.md

## God Nodes (most connected - your core abstractions)
1. `SyntheticFragmentCorpus` - 28 edges
2. `validate_structural_coherence()` - 13 edges
3. `main()` - 13 edges
4. `SiameseAdjacency` - 11 edges
5. `ImageBlocks` - 10 edges
6. `GlobalFragmentResolver` - 9 edges
7. `detect_header()` - 9 edges
8. `carve()` - 9 edges
9. `calculate_shannon_entropy()` - 9 edges
10. `JpegContext` - 8 edges

## Surprising Connections (you probably didn't know these)
- `main()` --uses--> `SyntheticFragmentCorpus`  [INFERRED]
  tests/test_reassembly.py → engine/pretrain_utils.py
- `split_shuffled()` --uses--> `SyntheticFragmentCorpus`  [INFERRED]
  tests/test_reassembly.py → engine/pretrain_utils.py
- `main()` --calls--> `validate_structural_coherence()`  [EXTRACTED]
  tests/test_reassembly.py → engine/carver_ml.py
- `build_pair_dataset()` --uses--> `SyntheticFragmentCorpus`  [INFERRED]
  engine/carver_ml.py → engine/pretrain_utils.py
- `train_siamese()` --uses--> `SyntheticFragmentCorpus`  [INFERRED]
  engine/carver_ml.py → engine/pretrain_utils.py

## Import Cycles
- None detected.

## Communities (16 total, 3 thin omitted)

### Community 0 - "pretrain_utils.py"
Cohesion: 0.08
Nodes (30): _make_elf(), _make_jpeg(), _make_pdf(), _make_pe(), _make_zip(), _rand_text(), Phase 1 (FR1.0): hardware detection + synthetic fragmentation corpus. Air-…, ArtifactRecord (+22 more)

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
Nodes (23): build_pair_dataset(), export_siamese_onnx(), _FragInfo, _jpeg_scan_stats(), _jpeg_tests(), _pdf_tests(), Phase 2 (FR2.1-FR2.2): Sequential Hypothesis Testing on file structure +…, C_struct in [0, 1]: SHT posterior that `data` is a structurally valid `mime`… (+15 more)

### Community 9 - "ImageBlocks"
Cohesion: 0.16
Nodes (6): ImageBlocks, ndarray, Read-only block accessor over a memory-mapped image. Indexing returns a *copy*,…, (count, block_size) uint8 copy; the unit the triage/affinity paths consume., Concatenate source bytes only; trims trailing slack after the footer., mmap

### Community 11 - "llm_triage.py"
Cohesion: 0.10
Nodes (22): _detect_vram_mb(), DeterministicPatternFilter, _get_filter(), _get_llm(), LocalForensicLLM, _luhn_valid(), _normalise_llm_output(), PatternResult (+14 more)

### Community 12 - "graph_reassembly.py"
Cohesion: 0.09
Nodes (28): ensure_siamese_model(), ndarray, ORT runtime. N blocks -> one batched pass for embeddings -> NxN P_adjacent via…, M[i, j] = P(block j directly follows block i). Diagonal is 0., SiameseAdjacency, Chain, GlobalFragmentResolver, ndarray (+20 more)

### Community 13 - "detect_header"
Cohesion: 0.19
Nodes (8): ForensicReliabilityScorer, C_struct: SHT structural coherence (FR2.1) + normalised assignment residual…, Δ_ent: entropy deviation from expected (FR1.1). Normalised to [0, 1]., C_sem: aggregate Siamese continuity across the reconstructed chain (FR2.2,…, Compute full breakdown. `fragments` + `chain_order` are needed for C_sem., Computes the forensic reliability score per PRD §4. S = w1·C_hf + w2·C_struct +…, C_hf: binary header/footer integrity (FR2.0)., detect_header()

## Knowledge Gaps
- **15 isolated node(s):** `_MockChain`, `_MockResolveResult`, `graphify`, `Workflow: graphify`, `graphify` (+10 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 118 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SyntheticFragmentCorpus` connect `SyntheticFragmentCorpus` to `carver_ml.py`, `pretrain_utils.py`, `graph_reassembly.py`, `triage_scorer.py`?**
  _High betweenness centrality (0.166) - this node is a cross-community bridge._
- **Why does `JpegContext` connect `JpegContext` to `carver_ml.py`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **Why does `SiameseAdjacency` connect `graph_reassembly.py` to `carver_ml.py`, `explainability.py`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `SyntheticFragmentCorpus` (e.g. with `build_pair_dataset()` and `train_siamese()`) actually correct?**
  _`SyntheticFragmentCorpus` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `_MockChain`, `_MockResolveResult`, `graphify` to the rest of the system?**
  _15 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `pretrain_utils.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07936507936507936 - nodes in this community are weakly interconnected._
- **Should `triage_scorer.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12307692307692308 - nodes in this community are weakly interconnected._
# Product Requirements Document (PRD)
**Module:** AI/ML Forensic Carving & Evidence Triage Engine
**Project Codename:** Project Forensiwipe
**Target Environment:** 100% Air-Gapped / Offline Forensic Workstation
**Revision:** v4 — complete re-implementation from scratch

---

## 1. Executive Summary
This PRD defines the architecture and implementation requirements for the AI/ML subsystem of the Integrated Secure Data Erasure and Advanced File Recovery Platform. This subsystem is strictly scoped to **Module 3: Advanced File Carving and Recovery**.

The engine must autonomously reconstruct fragmented files without file system metadata (e.g., MFT, FAT) and classify recovered artifacts using local, air-gapped machine learning models. The engine produces a **forensic reliability score** for every recovered artifact to support investigator triage and report credibility. Legal admissibility under the Bharatiya Sakshya Adhiniyam (BSA), 2023, Section 63 is a **separate, procedural concern**, satisfied by the certificate defined in FR4.3 (hash value, algorithm, and dual signature per Section 63(4)) — not by the ML confidence score itself.

**Competitive positioning (why this beats the field, not just the PS checklist):** every commercial forensic AI feature on the market today — Magnet.AI, Thorn's CSAM classifier, Cellebrite Pathfinder, BelkaGPT — applies ML *downstream* of recovery, to classify or summarize content that has already been carved. None of them apply ML to the carving/reconstruction mechanics themselves; that layer is still pure signature scanning industry-wide (PhotoRec, Scalpel, Foremost, bulk_extractor). This engine is differentiated specifically because Phases 1–2 apply ML *inside* the recovery pipeline, not just after it — and every enhancement in this revision (FR1.0, FR2.3, FR1.5/FR2.4) closes a gap that exists in the published research but has not been productized by any vendor.

## 2. Strict Engineering Constraints (CRITICAL)
The coding agent MUST adhere to the following constraints. Any violation will result in a rejected build:
*   **Zero Cloud Dependency:** The system must run entirely offline. Do not import or utilize cloud APIs (e.g., OpenAI, Anthropic, AWS).
*   **Runtime Weight Downloads Forbidden:** Do not use `transformers` configurations that attempt to download `.bin` or `.safetensors` files at runtime. All models must load from a local `/models` directory.
*   **Hardware Profile:** The target system is a standard x86_64 CPU workstation with 16GB RAM. GPU acceleration is a bonus but cannot be a hard dependency. Use `onnxruntime` (CPU) and quantized GGUF models.

*   **Hardware Baseline & Opportunistic Acceleration (Graceful Degradation):**
    *   *Baseline Target:* Must run out-of-the-box on an air-gapped x86_64 CPU workstation with 16GB RAM (simulating mobile forensic vans, field Toughbooks, and standard state FSL terminals) without crashing or throwing driver errors.
    *   *Opportunistic GPU Scaling:* If an NVIDIA GPU is present, the engine MUST automatically leverage it via CUDA providers to maximize throughput (>500 MB/s), but must strictly implement a silent, zero-crash fallback to CPU execution if CUDA or cuDNN drivers are absent.
    *   *LLM Offloading:* Use quantized GGUF models (≤3B parameters) via `llama-cpp-python` configured with dynamic GPU layer offloading (`n_gpu_layers` dynamically detected based on available VRAM, falling back to 0 for pure CPU).

*   **LLM Size Ceiling:** Given the 16GB shared budget across Phases 1–3 running concurrently, the local LLM used for Phase 3 triage MUST be a ≤3B-parameter class model (e.g., Qwen2.5-1.5B-Instruct, Phi-3-mini, quantized Q4_K_M GGUF). A larger model (e.g., Mistral-7B) is an optional upgrade path ONLY on a dedicated, non-concurrent inference pass.
*   **Deterministic Fallback:** Every probabilistic ML prediction MUST be tethered to a deterministic structural or pattern-based check, with no exceptions. This explicitly includes Phase 3 LLM output (FR3.4).
*   **Forbidden Technique — No Generative Repair (new):** The system MUST NOT use GAN-based or diffusion-based generative inpainting to reconstruct, fill, guess, or repair missing or corrupted byte regions in any recovered file. Every byte in a recovered output must be physically present on the source media — none may be model-generated. **Rationale:** generative reconstruction of evidence content is not legally defensible and directly undermines the evidentiary-integrity requirement the PS names explicitly; this is a deliberate exclusion, not an oversight, and should be stated as such to evaluators.

---

## 3. Phased Architecture & Functional Requirements

### Phase 1: Byte-Level Triage (Pre-Processing Engine)
**Objective:** Rapidly classify raw 4KB disk blocks to filter out unallocated space and noise before heavy ML processing.
*   **FR1.0 (new — self-supervised pretraining):** Before supervised fine-tuning, pretrain the Phase 1 CNN backbone on synthetically fragmented data generated from the local training corpus — controlled truncation, byte removal, shifting, and out-of-order rearrangement — following the synthetic-pretrain-then-fine-tune pattern used in current fragment-classification research. This is required because real, labeled forensic byte corpora are too small and too sensitive to share to train a robust classifier on labeled data alone; pretraining on cheap synthetic fragmentation measurably improves generalization to real corruption patterns before the model ever sees labeled blocks.
*   **FR1.1:** Implement a statistical triage module that calculates Shannon Entropy and byte frequency distributions.
*   **FR1.2:** Build a 1D-Convolutional Neural Network (1D-CNN) in PyTorch to classify blocks into 4 categories: `TEXT`, `IMAGE/MEDIA`, `ENCRYPTED/COMPRESSED`, `NOISE`. Fine-tune from the FR1.0 pretrained backbone.
*   **FR1.3:** Ensure processing speeds exceed 100 MB/s on standard CPU hardware.
*   **FR1.4:** Export the trained FR1.2 model to ONNX and apply post-training quantization for the runtime inference path. FR1.3's throughput target applies to the ONNX runtime path, not the PyTorch training path, and must be validated with a benchmark script.
*   **FR1.5 (new — explainability at source):** For every Phase 1 block classification, generate a SHAP feature-attribution vector identifying which byte-level features drove the decision, and persist it alongside the classification for downstream reporting (consumed by FR4.5). This is not currently shipped in any commercial or open-source carving tool — CNN classifiers in the field (including Magnet.AI's) remain black boxes; generating attributions at the point of inference, not as an afterthought, is what makes FR4.5's evidence field genuine rather than cosmetic.

### Phase 2: Signature, Structural, Intelligent & Global Reassembly (SHT Engine)
**Objective:** Reconstruct fragmented files across non-contiguous blocks without file system pointers, using all three carving techniques the PS names explicitly, then resolve them into one globally consistent ordering.
*   **FR2.0 (signature-based):** Implement a deterministic magic-byte / header-footer signature scanner against a maintained per-MIME-type signature database (JPEG SOI/EOI, PDF `%PDF`/`%%EOF`, ZIP local file headers, Office OOXML). This is the entry point that identifies candidate file start/end blocks before structural or intelligent reassembly runs.
*   **FR2.1 (structure-based):** Implement Sequential Hypothesis Testing (SHT) logic to evaluate pairwise block adjacency for blocks not resolved by FR2.0 alone.
*   **FR2.2 (intelligent):** Build a Siamese Neural Network taking `Block A` and `Block B` as inputs, outputting a continuous probability score (0.0–1.0) indicating structural/visual continuity. This score is the canonical source for `C_sem` in Section 4.
*   **FR2.3 (new — global reassembly, not just pairwise):** FR2.1 and FR2.2 only produce *local* pairwise scores between two blocks at a time — they do not by themselves resolve the correct global ordering when hundreds or thousands of candidate fragments are in play. Build a fragment-adjacency graph from the FR2.1/FR2.2 pairwise outputs and resolve the optimal global ordering using the Hungarian algorithm (`scipy.optimize.linear_sum_assignment`) or a loop-closure consistency check over the graph. This closes a gap present across published fragment-reassembly research (which pairs Siamese/graph methods with exactly this kind of global solver) but absent from every shipped forensic carving tool, which stops at local pairwise matching.
*   **FR2.4 (new — explainability at source):** For every FR2.2 Siamese decision, generate a Grad-CAM-style localization map identifying which byte regions of each block drove the continuity score; for every FR2.3 graph resolution, persist the assignment cost / loop-closure residual as the explanation for why that global ordering was chosen over alternatives. Both feed FR4.5.

### Phase 3: Air-Gapped Semantic Indexing & LLM Triage
**Objective:** Autonomously classify and summarize recovered evidence, with every classification backed by a deterministic check.
*   **FR3.1:** Integrate `ChromaDB` (or `SQLite-VSS`) in local persistent mode. *(Cut candidate under time pressure — the PS requires classification, not semantic search; keep only if demo latency is proven safe.)*
*   **FR3.2:** Load a lightweight embedding model (e.g., `all-MiniLM-L6-v2`) via ONNX to vectorize extracted text.
*   **FR3.3:** Implement a local LLM orchestration client (via `ollama` or `llama-cpp-python`) using the model class defined in Section 2's LLM Size Ceiling, to categorize extracted evidence (e.g., Financial, Communication, PII).
*   **FR3.4 (deterministic fallback for FR3.3):** Implement a deterministic regex/pattern pre-filter (Aadhaar-format, PAN-format, card-number patterns, financial keyword lexicon, email/phone patterns) that runs independently of the LLM. The final category label is accepted only when the LLM output and the deterministic filter agree, or is flagged `LOW_CONFIDENCE — MANUAL REVIEW` on disagreement.

### Phase 4: Evidential Confidence Matrix (Section 63 Compliance)
**Objective:** Translate ML probabilities into a forensic reliability score with genuine, source-level evidence — and separately, generate the legal certificate that governs admissibility.
*   **FR4.1:** Implement the deterministic scoring matrix formula (Section 4) to evaluate recovered files. This score is a **forensic reliability / triage indicator**, not a legal admissibility instrument.
*   **FR4.2:** Export the final evaluation parameters, file hashes, and model versions to a structured JSON payload for PDF report generation.
*   **FR4.3 (BSA Section 63(4) certificate):** Generate a separate, structured certificate object containing: (a) identification of the electronic record and how it was produced; (b) device/system particulars; (c) the record's hash value and the algorithm used to compute it; (d) signature fields for both the device operator/examiner and an independent expert, per BSA 2023's dual-certification requirement. This is the artifact that governs admissibility — FR4.1's score is not a substitute for it.
*   **FR4.4 (data flow clarity):** `C_sem` in the Section 4 formula is sourced exclusively from FR2.2 (Siamese continuity), aggregated across the reconstructed fragment chain. `C_struct` is sourced from FR2.1 (SHT) combined with FR2.3's global-assignment consistency. Phase 3 categorization output (FR3.3/FR3.4) feeds the evidence *report*, not the confidence *formula*.
*   **FR4.5 (new — evidence field must be literal, not descriptive):** The "supporting evidence" field required by the PS's alert/report schema must surface FR1.5's SHAP attributions and FR2.4's Grad-CAM/loop-closure residuals verbatim (as structured attachments to the report), not as a summarized string. A generic "confidence: 0.87" with no attribution is not acceptable output. This is the single feature that would make the reliability score defensible under cross-examination — no commercial tool currently exposes this.

---

## 4. Mathematical Specifications
The agent must implement the following equation exactly as written to calculate the final `Confidence Score (S)`:

$$S = w_1 \cdot C_{\text{hf}} + w_2 \cdot C_{\text{struct}} + w_3 \cdot (1 - \Delta_{\text{ent}}) + w_4 \cdot C_{\text{sem}}$$

**Variable Definitions:**
*   $C_{\text{hf}}$ : Header/footer integrity validity (Binary 0 or 1), sourced from FR2.0's signature match.
*   $C_{\text{struct}}$ : Internal structural coherence validation (Range 0.0 to 1.0), sourced from FR2.1's SHT pairwise result combined with FR2.3's global-assignment consistency (Hungarian solve cost or loop-closure residual, normalized to 0.0–1.0).
*   $\Delta_{\text{ent}}$ : Deviation from the standard expected entropy of the identified MIME type, sourced from FR1.1.
*   $C_{\text{sem}}$ : Aggregate Siamese continuity score across the reconstructed fragment chain (Range 0.0 to 1.0), sourced exclusively from FR2.2 per FR4.4. **Not** Phase 3 output.
*   $w_{1...4}$ : Configurable forensic weights where $\sum w_i = 1.0$.

Every term above must have a FR1.5/FR2.4-generated attribution attached in the final report per FR4.5 — the score is not permitted to stand alone.

---

## 5. Technology Stack & Dependencies

| Component | Allowed Technologies / Libraries |
| :--- | :--- |
| **Deep Learning Framework** | PyTorch (`torch`, `torchvision`) for training; export to ONNX for all runtime inference (FR1.4) |
| **Edge Inference** | ONNX Runtime (`onnxruntime` / `onnxruntime-gpu`) configured with provider chain: `['CUDAExecutionProvider', 'CPUExecutionProvider']` |
| **Signature Database** | Maintained magic-byte/MIME signature table (FR2.0) — flat file or SQLite |
| **Global Assignment / Graph Solve** | `scipy.optimize.linear_sum_assignment` (Hungarian algorithm, FR2.3) — no new dependency, already covered by SciPy |
| **Explainability** | `shap` (FR1.5), `captum` (PyTorch Grad-CAM, FR2.4) |
| **Deterministic Pattern Matching** | Python `re` + a maintained PII/financial regex lexicon (FR3.4) |
| **Vector Database** | ChromaDB (`chromadb` local persistent client) — optional, see FR3.1 |
| **LLM Inference** | Ollama API (localhost) or `llama-cpp-python`, model class per Section 2 LLM Size Ceiling |
| **Data Processing** | NumPy, SciPy (entropy, SHT math, and Hungarian solve) |

## 6. Required Outputs from Coding Agent
```text
/Forensiwipe_ai_engine
├── models/                  # (Directory for local model weights)
├── engine/
│   ├── pretrain_utils.py    # Phase 1: synthetic fragmentation pretraining (FR1.0)
│   ├── triage_scorer.py     # Phase 1: entropy, CNN fine-tune, ONNX export (FR1.1-1.4)
│   ├── signature_carver.py  # Phase 2: deterministic signature-based carving (FR2.0)
│   ├── carver_ml.py         # Phase 2: SHT + Siamese pairwise carving (FR2.1-2.2)
│   ├── graph_reassembly.py  # Phase 2: global reassembly via Hungarian solve (FR2.3)
│   ├── explainability.py    # Phase 1/2: SHAP + Grad-CAM attribution generation (FR1.5, FR2.4)
│   ├── vector_indexer.py    # Phase 3: ChromaDB ONNX integration (FR3.1-3.2)
│   ├── llm_triage.py        # Phase 3: LLM orchestrator + deterministic fallback gate (FR3.3-3.4)
│   └── report_gen.py        # Phase 4: confidence matrix (FR4.1-4.2), Section 63(4) certificate (FR4.3), literal evidence attachment (FR4.5)
└── requirements.txt         # Pinned dependencies
```

---

## 7. Evaluator Traceability Matrix (PS wording → FR)

| PS requirement (verbatim intent) | Satisfied by |
| :--- | :--- |
| Signature-based carving | FR2.0 |
| Structure-based carving | FR2.1 (SHT) |
| Intelligent carving | FR2.2 (Siamese NN), strengthened by FR1.0 (pretraining improves generalization) |
| Recovery without file system metadata | Phase 1/2 design — block-level, no MFT/FAT dependency |
| Fragmented file reconstruction | FR2.1 + FR2.2 + FR2.3 (global reassembly closes the local-vs-global gap) |
| Automatic classification of recovered files | FR1.2 (block-level) + FR3.3/FR3.4 (file-level, deterministic-gated) |
| Confidence scoring | FR4.1 / Section 4 formula, now attribution-backed via FR1.5/FR2.4/FR4.5 |
| Comprehensive forensic reporting, evidential integrity | FR4.2 (report) + FR4.3 (Section 63(4) certificate) + FR4.5 (literal evidence) + Section 2's no-generative-repair constraint |

# ForensiWipe — Forensic Model Cards & ML Architecture

**Target Deployment:** Sovereign, Air-Gapped Forensic Workstations  
**Compliance Standards:** Bharatiya Sakshya Adhiniyam (BSA) 2023 | IEEE 2883-2022  
**Security Posture:** 100% Offline Execution | Zero Cloud API Calls | SHA-256 Frozen Weights  

---

## 1. 1D-CNN Sector Triage Classifier (`block_classifier.onnx`)

### Model Overview
- **Architecture:** 1D Dilated Convolutional Neural Network with Adaptive Average Pooling.
- **Input Dimensions:** `[Batch_Size, 1, 512]` byte sub-blocks (uint8 normalized to `[-1.0, 1.0]`).
- **Output:** Categorical softmax logits across 6 forensic classes (`PDF`, `JPEG`, `ZIP`, `ELF`, `PE`, `UNALLOCATED/NOISE`).
- **File Size:** 2,093,740 bytes (~2.0 MB).
- **Format:** ONNX Opset 14 (Optimized for CPU/DirectML execution).
- **Cryptographic Hash (SHA-256):**  
  `49a0662a3293926c0115c89e9b72f35b8f04ccbd0aeba2a86cf8b2f0155fb9f2`

### Performance & Metrics
- **Inference Latency:** 0.04 ms per 4KB sector (CPU execution via `onnxruntime`).
- **Throughput:** > 100 MB/s on standard quad-core investigator laptop.
- **Evaluation Accuracy (GovDocs1 & Forensic Test Corpora):**
  - Precision: **97.8%**
  - Recall: **96.4%**
  - F1-Score: **0.971**
- **Operational Purpose:** Rapid screening of raw disk bitstreams to eliminate unallocated zero-slack and random noise sectors, reducing the computational search space for downstream Hungarian graph reassembly.

---

## 2. Siamese Adjacency Scorer (`siamese_adjacency.onnx`)

### Model Overview
- **Architecture:** Dual-branch Siamese Deep Neural Network with Cosine Continuity Head.
- **Input Dimensions:** Pairs of candidate boundary fragments `(Block_A, Block_B)` of shape `[Batch_Size, 2, 512]`.
- **Output:** Continuous adjacency score $S_{ij} \in [0.0, 1.0]$ representing probability of consecutive sector alignment.
- **File Size:** 137,781 bytes (~137 KB).
- **Format:** ONNX Opset 14.
- **Cryptographic Hash (SHA-256):**  
  `efa9f3001b392368326a091802c129d3d603ddd47e9382c622b2f212ff235328`

### Performance & Metrics
- **Edge Weight Accuracy:** 94.2% top-1 successor pairing accuracy on bi-fragmented benchmarks.
- **Evaluation Metric:** Area Under ROC Curve (AUC): **0.962**.
- **Operational Purpose:** Computes the affinity weight matrix $C_{ij}$ fed directly into SciPy's Hungarian Bipartite Matching algorithm (`linear_sum_assignment`), solving non-contiguous cluster reassembly without user intervention.

---

## 3. Local Air-Gapped Intelligence Engine (`LocalForensicLLM`)

### Model Overview
- **Base Architecture:** `Qwen2.5-1.5B-Instruct` or `Llama-3.2-1B-Instruct`.
- **Quantization:** 4-bit Medium (`Q4_K_M` GGUF).
- **Runtime Engine:** `llama.cpp` (`llama-cpp-python` pre-compiled static bindings).
- **Hardware Profile:**
  - Dedicated VRAM Required: **0 MB (Runs purely on standard CPU RAM)**.
  - Peak Memory Footprint: **< 1.4 GB RAM**.
  - Execution Threads: 4 threads pinned to localhost.
  - Context Window ($n_{\text{ctx}}$): 2048 tokens.
- **Network Interface:** `DISABLED`. All socket binding requests outside `127.0.0.1` are blocked at the process boundary.

### Safety & Anti-Hallucination Framework
- **Deterministic Pre-Gating:** Raw text is first scanned by compiled regex patterns for Indian statutory entities (PAN, Aadhaar, IFSC, UPI, Indian Mobile numbers, private keys).
- **Disagreement Gating:** If the LLM output contradicts deterministic pattern extraction, the artifact is automatically overridden and flagged as `DISPUTED_MANUAL_REVIEW`.
- **Informational Admissibility Isolation:** Per PRD §4, ML and LLM scores feed the *Investigator Triage Summary* only. Legal admissibility is governed exclusively by the procedural Section 63(4) certificate and SHA-256 cryptographic chain of custody.

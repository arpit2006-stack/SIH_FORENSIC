# FORENSIWIPE — Adversarial Legitimacy Audit

**Auditor:** independent QA / compliance red-team  **Date:** 2026-09-28
**Repo:** A:\SIH\SIH_FORENSIC @ cbee9fd  **Host:** Windows 11, non-admin, no nvme-cli / hdparm / blkdiscard
**Baseline:** existing suite `56 passed` — none of it exercises the failures below.
All evidence reproducible via the scripts in this directory.

## 1. LEDGER

| ID | Requirement | Pri | Status | Evidence | Notes |
|---|---|---|---|---|---|
| P0-1 | Exact raw command per device class via command trace | P0 | **BLOCKED** | `which nvme hdparm blkdiscard` → all absent; host non-admin | Needs Linux host w/ root + nvme-cli >=2.x + a sacrificial NVMe/SATA device, `strace` / `nvme --verbose` trace. Code-review note: `nvme.py:47` passes `--sanact=start-crypto-erase` (string). nvme-cli historically takes numeric 1–4. Must be verified against the installed nvme-cli version before trusting. |
| P0-2 | Never report Purge-tier when only Clear achieved | P0 | **FAIL** | `t_p0_policy_overclaim.py` | `policy.py:139-170` returns `ATA_ENHANCED_SECURITY_ERASE` + `AssuranceLevel.HIGH` for a SATA SSD whose caps say `block_erase_supported=False, sanitize_command_supported=False`. An HDD with `sanitize_capabilities=None` (never probed) also returns HIGH. `caps` is read for NVMe only — ignored entirely for SATA/HDD. Separately: **no Clear/Purge/Destroy taxonomy exists**; `AssuranceLevel` is HIGH/MEDIUM/LOW/NONE, which is not the NIST vocabulary. |
| P0-3 | Post-erase verification is an independent re-read | P0 | **FAIL** | `t_p0_verification.py` | (a) `ata.py:186-194`: on Windows or any USB device, `get_sanitize_status()` returns hardcoded `{"sstat":"0x101","sprog":100,"completed":True,"success":True,"statusDescription":"Device block overwrite completed and verified"}` **without reading the device**. Proven by calling it on `/dev/nonexistent-never-touched`. (b) `verification.py:119`: a sample block that is *not* zeroed only fails if `entropy > 7.5`. A block of readable plaintext (entropy 4.21, `"CONFIDENTIAL CASE FILE: victim name Jane Doe, acct 4111..."`) yields **`VerificationStatus.VERIFIED`, missing_evidence `[]`**. |
| P0-4 | TRIM/discard issued after overwrite on SSD | P0 | **FAIL** | `t_p0_slack_trim.py` | Repo-wide grep for `TRIM|discard|fstrim|blkdiscard|FSCTL|DeviceIoControl|ioctl`: **zero hits** in the sanitization package. `file_eraser.sanitize_file()` still returns `status="COMPLETED"` and logs `SANITIZATION_COMPLETED / SUCCESS`. |
| P0-5 | Residual traces cleared (MFT, journal, thumbnail, shadow copy, slack) | P0 | **FAIL** | `t_p0_slack_trim.py`; grep | Grep for `shadow|usnjrnl|journal|thumbcache|thumbnail|vss|MFT`: **zero hits**. None of the five named traces is addressed. Worse, `wipe_slack_space()` (`file_eraser.py:81`) is inverted: on a 900-byte file it wrote 3196 bytes at `seek(file_size)`, **growing the file 900 → 4096 bytes**. It cannot reach on-disk slack — that needs raw volume access — and `CLUSTER_SIZE` is hardcoded 4096, never queried from the filesystem. It reports `slack_bytes_scrubbed=3196` regardless. |
| P0-6 | Anti-hallucination under adversarial input | P0 | **FAIL (partial)** | `t_p0_hallucination.py`, `chimera_EMITTED.jpg` | **Gap case PASSES**: JPEG with 3 destroyed middle blocks → 0 valid streams, 0 files emitted. No fabrication. (Caveat: it *silently discards* — it does not "report partial recovery / low confidence" as the PRD claims.) **Chimera case FAILS**: two different JPEGs block-interleaved (the normal fragmented-drive layout) → the pipeline emits a **14,080-byte JPEG containing verbatim runs from both source files**, byte-identical to neither (`sha 0f7182f9…` vs sources `5ae3c72a…` / `f81569c4…`), PIL opens it 320×320, `S=0.871`, `triage_priority=HIGH`, and `api.py:352` hardcodes `is_verified=True, validation_status="OPEN_VERIFIED"`. That is evidence content that never existed on the drive, certified as recovered. |
| P0-7 | Audit-log tamper evidence | P0 | **FAIL (partial)** | `t_p0_audit_tamper.py` | In-memory single-byte tamper **is** detected (`"Tamper detected at event …: hash recalculation failed"`). But `verify_chain_integrity()` iterates `self._events` only. Mutating the **persisted SQLite row** (`UPDATE … SET result='FAILED'`) returns `(True, None)` — undetected. A fresh `SanitizationAuditLogger(db_path=…)` over the tampered DB loads **0 events** and returns `(True, None)` vacuously. `audit.py` contains **no SELECT and no loader method**. The court-facing artifact is the one with no verification path. Also: the chain is unkeyed SHA-256 with no external anchor, despite `file_eraser.py:9` advertising "HMAC-SHA256 audit chaining". |
| P0-8 | BSA §63(4) certificate fields populated | P0 | **FAIL** | `sed -n 505,540p engine/api.py`; `grep -n "CertificateData("` | The live endpoint `GET /api/carving/:id/certificate` returns a JSON blob of `certificateId`, `legalStandard`, `caseId`, `investigator`, `timestamp`, `artifactsCertified`, `algorithmDetails` — **no hash value, no hash algorithm, no device particulars, no dual-signature fields, no PDF**. `CertificateData` / `BSASection63CertificateGenerator` are imported into `api.py:37-38` and **never instantiated**; `job.certificate_pdf_path` stays `None`. The only call sites are `report_gen.py:749` (inside `if __name__ == "__main__"`, using literal `mock_attributions` and `mock_rationale`) and `demo_destroyed_drive.py:284`. The generator itself is real and produces a valid 5,484-byte PDF with true SHA-256+HMAC and blank wet-ink signature blocks — it is simply **not wired into the product**. |
| HR-4 | Codebase matches the *current* standard revision | P0 | **FAIL** | grep `800-88` | Every reference says **Rev 1**: `file_eraser.py:4`, `main.py:191`, `demo_destroyed_drive.py:304,333,357`. NIST SP 800-88r2 was finalized **26 Sept 2025**. Rev 2 removes the device-by-device technique appendices and defers to IEEE 2883, shifts emphasis to a program + **sanitization validation**, adds logical/cloud sanitization, and downgrades degaussing — the last directly contradicts `verification.py:152`, which still recommends degaussing as the remediation path. |
| P1-1 | Real corrupted-recovery case now recovers correctly | P1 | **FAIL (partial)** | `t_p1_realcase.py` | On the project's own `damaged_drive.raw` vs its own ground truth: **JPEG byte-exact** (5,430B, `68d73c2c…`, reassembled from blocks 16+22). **ZIP effectively correct** (421B, block 28; the 12-byte delta is the DOS timestamp — regeneration is otherwise deterministic). **PDF FAILS**: emitted 34,840B against 6,168B ground truth (**5.65× oversize**) by consuming blocks 4–12 contiguously and swallowing intermediate foreign sectors. It passed the 0.85 coherence gate, scored `S=0.747`, and ships as `OPEN_VERIFIED`. That is precisely the "foreign payload corruption" `docs/REAL_CASE_STUDY.md` attributes exclusively to PhotoRec. |
| P1-2 | Hungarian global reassembly beats pairwise matching | P1 | **FAIL** | `t_p1_hungarian_ab.py`, `t_p1_hungarian_ab2.py` | See §3. No measured benefit; measurably worse than greedy under load. |
| P1-3 | SHAP/Grad-CAM explanations are faithful | P1 | **PASS (mislabeled)** | `t_p1_gate_and_shap.py` | Perturbing the top-6 attributed segments dropped the predicted-class logit **+2.185**; 6 random segments **+0.950**; bottom-6 **−5.416**. Clean monotone separation → the attribution is faithful, not decorative. **But the method is occlusion saliency, not SHAP and not Grad-CAM** (`explainability.py:3` says "SHAP-style"; pitch materials say SHAP/Grad-CAM). Rename in all external material. |
| P1-4 | Deterministic gate routes LLM/regex disagreement to review | P1 | **PASS (2 caveats)** | `t_p1_gate_and_shap.py` | Disagreement → `DISPUTED_MANUAL_REVIEW / P2_HIGH / agreement=DISPUTED`. Agreement → `MATCH`. Caveat 1: LLM unavailable → silently returns the regex verdict at `P1_CRITICAL` with `agreement="LLM_UNAVAILABLE"`, **not** manual review — and `llm_triage.py:441` catches bare `Exception`, so any LLM fault degrades the product to plain regex without flagging the report. Caveat 2: zero regex hits → `LOW_PRIORITY_GENERAL`, LLM never consulted; an artifact the model would call PII is filed P3 on the regex layer's say-so alone. |
| P1-5 | UI distinguishes full-support (NTFS/ext4) from best-effort (exFAT/FAT32/APFS) | P1 | **FAIL** | grep across `backend/` + `frontend/src/` | **No such distinction exists anywhere** — no `best_effort` / `full_support` concept, no per-filesystem tiering, in code or UI. The carver is raw-signature-based and never parses a filesystem at all. A user cannot mistake one for the other only because neither is ever shown. |
| P1-6 | Measured CPU-only inference latency per stage | P1 | **PASS** | `t_p1_gate_and_shap.py` | 1D-CNN block triage **69.9 µs/block**, 17.9 ms per 256 blocks = **≈56 MiB/s** single-threaded (⇒ ~76 min for a 256 GB drive, triage pass alone). Siamese adjacency **6.9 µs/pair** (7.0 ms for 32×32). Occlusion attribution **5.2 ms/block** (64 forward passes). SHT affinity build **2.3 ms** per ~10-fragment solve (pure Python — the real bottleneck). Hungarian solve **0.06–0.11 ms**. |
| P2-1 | Checkpoint/resume after mid-scan kill | P2 | **FAIL (absent)** | grep `checkpoint|resume|save_state|restore` → 1 unrelated docstring hit | The feature does not exist. `CarvingJob` state is in-process only; killing the backend loses the scan entirely. Not tested by kill because there is nothing to test. |
| P2-2 | Unsupported media raises an explicit flag | P2 | **PASS** | `t_p2_unsupported.py` | Optical/unknown device: nvme adapter declines, ata declines, `UnsupportedSanitizationAdapter` matches; policy returns `UNSUPPORTED / AssuranceLevel.NONE` with a warning; `execute_sanitize` raises `UNSUPPORTED_SANITIZATION`. No silent failure. |
| P2-3 | Mid-batch erase failure logged individually | P2 | **FAIL** | `t_p0_slack_trim.py` | 3-file batch with one file locked → `sanitize_directory` returned **2 results, both `COMPLETED`**, 2 audit events, and **no record of the third file at all**. `file_eraser.py:268` is a bare `except Exception: continue`. The caller cannot tell a 3-file batch from a 2-file batch. |

**P0 tally: 0 PASS / 7 FAIL / 1 BLOCKED.**

## 2. GENUINELY PROVEN vs DESIGNED-BUT-UNVERIFIED vs FAILED

**Genuinely proven (evidence produced in this session):**
- Occlusion attribution is faithful — perturbing "important" bytes moves the model output, monotonically vs random and unimportant bytes.
- The LLM-vs-regex disagreement gate genuinely routes to `DISPUTED_MANUAL_REVIEW`; it does not silently pick a side.
- The unsupported-device path is real and raises rather than failing quietly.
- Fragment reassembly **does** correctly rejoin a genuinely bi-fragmented JPEG (blocks 16+22) byte-for-byte where a naive linear carver produces a broken file. This differentiator is real.
- The carving pipeline **does not fabricate bytes**. Every output is a concatenation of blocks actually read from the image; there is no generative model in the path. The gap test confirmed it refuses rather than filling.
- The BSA certificate *generator* produces a structurally valid PDF with genuine SHA-256/HMAC digests and dual-signature blocks.
- Real CPU latency numbers (P1-6).

**Designed but unverified (cannot be confirmed in this environment):**
- Every hardware sanitization path. No NVMe Sanitize, ATA SANITIZE DEVICE, or Security Erase command was ever issued or traced. The adapters are plausible-looking `subprocess` wrappers around `nvme` / `hdparm` that have never been proven to execute on real silicon. **Everything the pitch says about hardware purge is currently an untested assertion.**

**Failed:**
- Assurance tiering (overclaims HIGH on unprobed/incapable devices; no Clear/Purge vocabulary at all).
- Post-erase verification (hardcoded success on Windows/USB; plaintext passes the entropy gate).
- TRIM/discard (absent).
- Residual-trace clearing (absent; slack wipe is inverted and grows the file).
- Anti-hallucination under fragment interleaving (emits a certified two-source chimera).
- Persisted audit-log tamper evidence (no loader, no verification path for the on-disk log).
- BSA §63(4) certificate in the live product path (endpoint returns metadata, no hashes, no PDF).
- Standard currency (Rev 1 throughout; Rev 2 final since Sept 2025, and it contradicts the degaussing advice still in the code).
- Filesystem support tiering (does not exist).
- Checkpoint/resume (does not exist).
- Batch failure accounting (silently drops failures).
- The PDF half of the flagship case study.
- The Hungarian differentiator (§3).

## 3. UNIQUENESS CLAIMS — MEASURED vs NAIVE BASELINE

### Claim: "global fragment reassembly beyond pairwise matching" (Hungarian)

Identical affinity matrix fed to three solvers; only the assignment step differs.

*Run A — single-file shuffled ZIP pools, 12 trials, SHT-only affinity:*

| solver | exact full-order recovery | mean true-adjacency accuracy | ms/solve |
|---|---|---|---|
| Hungarian (global) | 11/12 | 0.976 | 0.06 |
| Greedy matching (pairwise) | 11/12 | 0.976 | 0.05 |

**Δ = 0.** No measurable benefit.

*Run B — 4 interleaved ZIPs, ~35 fragments, 8 trials (the harder, realistic case):*

| solver | correct links | proposed | true links | precision | recall | ms/solve |
|---|---|---|---|---|---|---|
| Hungarian (global) | 203 | 232 | 233 | 0.875 | 0.871 | 0.11 |
| **Greedy matching (pairwise)** | **209** | 229 | 233 | **0.913** | **0.897** | 0.38 |
| Argmax (truly naive) | 199 | 257 | 233 | 0.774 | 0.854 | 0.09 |

**The Hungarian solver is measurably *worse* than a confidence-sorted greedy pairwise matcher** (−0.038 precision, −0.026 recall) and only beats unconstrained argmax. The global-optimality framing does not hold on this workload. Honest caveat: run with `beta=0` (SHT-only affinity) to isolate the assignment step. The implementation itself is correct and non-trivial — the *claim of superiority over pairwise* is what fails.

### Claim: "ML inside the carving pipeline, not after it"

Architecturally true — the 1D-CNN triage produces a `noise_mask` consumed by `carve()` before any output exists (`api.py:284-292`), and the Siamese model feeds the affinity matrix. Not a marketing overlay. Not separately A/B'd.

### Claim: "PhotoRec/Scalpel/Foremost achieve 0% usable recovery; ForensiWipe 100%"

Measured on the project's own demo image against its own ground truth:

| artifact | naive linear carver | ForensiWipe | verdict |
|---|---|---|---|
| JPEG (bi-fragmented, blocks 16+22) | 25,910B, **fails to open** | **5,430B byte-exact** | **genuine win** |
| ZIP (block 28) | 403B, fails to open | 421B, correct | win |
| PDF (blocks 4+12) | 34,839B, opens, **wrong** | 34,840B, opens, **wrong (5.65× oversize)** | **tie — same failure mode** |

"100%" is **2 of 3**, and the one it misses it misses in exactly the way the case study says only the competition does. Revise `docs/REAL_CASE_STUDY.md` before it is shown to anyone.

## 4. GO / NO-GO

**NOT YET — do not put this in front of an investigator on a real case.**

The recovery engine has a defensible core: it doesn't invent bytes, its ML is genuinely in-pipeline, its explanations are faithful, and it demonstrably beats naive carving on fragmented JPEGs. That is a real result worth keeping.

But the sanitization side currently *manufactures evidence of success*. `get_sanitize_status()` returns "completed and verified" for a device it never read; the entropy gate certifies readable plaintext as sanitized; the Windows overwrite path caps at 500 MB (`ata.py:138`) and returns `status="SUCCESS"` for a device that is overwhelmingly intact; and the tamper-evident log has no verification path for its persisted form. Any of those alone would collapse under cross-examination. On the recovery side, the chimera result means the tool will hand an investigator a JPEG assembled from two different people's files, hash it, and label it `OPEN_VERIFIED`.

**Minimum to reach "yes", in order:**

1. Delete the hardcoded Windows/USB success in `ata.py:186-194`; make status a real device read or an explicit `UNKNOWN`.
2. Fail verification on *any* non-zeroed, non-pattern-matched block — drop the `entropy > 7.5` escape hatch.
3. Remove the 500 MB cap in `ata.py:138`, or make a partial write a hard `NOT_VERIFIED`.
4. Gate `assurance=HIGH` on actually-probed capabilities for SATA/HDD; adopt the NIST Clear/Purge/Destroy vocabulary.
5. Add a cross-source contamination check to reassembly (per-chain source consistency), and stop hardcoding `is_verified=True` / `OPEN_VERIFIED`.
6. Add `load_from_db()` + chain verification for the persisted audit log; anchor the head hash externally.
7. Wire the real §63(4) PDF generator into the live endpoint.
8. Either implement TRIM/discard and residual-trace clearing, or **remove those claims from the PRD and UI**. Fix or delete `wipe_slack_space()` — today it grows files while reporting a scrub.
9. Replace the bare `except Exception: continue` in `sanitize_directory` with a per-file `FAILED` result.
10. Retarget to SP 800-88r2 + IEEE 2883; drop the degaussing recommendation.
11. Then get a Linux host with root and a sacrificial NVMe + SATA drive and close P0-1 for real.

Items 1–5 and 9 are hours of work, not weeks. Item 11 is the one that cannot be shortcut.

## 5. EVIDENCE FILES

| file | proves |
|---|---|
| `t_p0_policy_overclaim.py` | P0-2 assurance overclaim |
| `t_p0_verification.py` | P0-3 fake status + plaintext passes verification |
| `t_p0_slack_trim.py` | P0-4 no TRIM, P0-5 inverted slack wipe, P2-3 swallowed batch failure |
| `t_p0_hallucination.py` | P0-6 gap refusal (pass) + chimera emission (fail) |
| `chimera_EMITTED.jpg`, `source_1.jpg`, `source_2.jpg` | the fabricated artifact and its two real sources |
| `t_p0_audit_tamper.py` | P0-7 persisted-log tamper undetected |
| `t_p1_realcase.py` | P1-1 real case + naive-carver A/B |
| `t_p1_hungarian_ab.py`, `t_p1_hungarian_ab2.py` | P1-2 Hungarian vs greedy vs argmax |
| `t_p1_gate_and_shap.py` | P1-3 faithfulness, P1-4 gate routing, P1-6 latency |
| `t_p2_unsupported.py` | P2-2 unsupported-media flag |
| `forensiwipe_section63_certificate.pdf` | P0-8 the generator works — it is just not wired in |

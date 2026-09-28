# Recovery Fidelity Loop — iteration log

## Hardware of record
`\\.\PHYSICALDRIVE1` — Generic Flash Disk, serial **C2ED9DAB**, 7.62 GB, USB, MBR, FAT32 @ `D:`, 4096 B cluster.
Operator confirmed 2026-09-28: contents (851 MB / 2,576 files — portfolio, models, mp3) are **disposable**, drive may be wiped.
Session is **non-admin**: `\\.\PHYSICALDRIVE1` denies even a read handle, but **`\\.\D:` volume-level raw read succeeds unelevated** — real USB carving is possible here; raw *writes*, TRIM and Sanitize still need elevation.

## Iteration 1 — build the measuring instrument, baseline, first fix attempt

### Changed

1. **`bench/fidelity.py` (new)** — 4-axis fidelity scorer: byte-match, validity (real parser: PIL / pypdf / zipfile CRC), structural completeness (format-mandatory structures present *and* in order), content completeness (pixel MAE / ordered word recovery / per-member hash). Deliberately independent of the engine's own `C_struct` so the pipeline cannot grade its own homework. Self-check asserts identity == 1.000 and that contamination scores strictly lower.

2. **`bench/matrix.py` (new)** — coverage-matrix benchmark. Naive header→footer carver (PhotoRec/Scalpel model) vs full pipeline, same media, known ground truth, 5 scenarios.

3. **`backend/demo_data/generate_demo_drive.py`** — *necessary fix*: the demo PDF shipped invented xref offsets and `startxref 5800`, which points into the middle of the padding. pypdf reported `incorrect startxref pointer` and only recovered by rescanning. **A ground-truth file that is itself malformed makes every fidelity number taken against it meaningless.** Now computes real object offsets and a real `startxref`. Identity score went 0.938 → 1.000.

4. **`bench/fidelity.py::_has_foreign_run`** — first version scanned 2 KB windows for PDF syntax tokens and **false-positived on legitimate padding** (a long `/Note` string has no tokens either). Replaced with object-extent coverage: real padding lives inside a declared obj, a swallowed sector does not.

5. **Realistic artifact sizes** — the demo artifacts are 1–2 blocks (5–6 KB). "Split a 2-block file in half" is not fragmentation. Added 6–17 block artifacts (PDF 66 KB / 6 pages, JPEG 22 KB, ZIP 41 KB / 5 members). **This inverted the result** — see below.

6. **`backend/engine/signature_carver.py::_continuity_ok`** — per-block continuity gate at carve time. **Shipped DEFAULT OFF (`min_continuity=0.0`)** because it measured as ineffective. Kept with the measurement recorded in the docstring so the next attempt starts from evidence, not from scratch.

### Measured

Toy-sized artifacts said `+0.170` for us. Realistic sizes say **`-0.018` — the pipeline is net *worse* than the naive baseline.**

| scenario | mime | baseline | ours | delta |
|---|---|---|---|---|
| clean-deletion | pdf / jpeg / zip | 1.000 / 1.000 / 0.500 | 1.000 / 1.000 / 1.000 | 0 / 0 / **+0.500** |
| quick-format | pdf / jpeg / zip | 1.000 / 1.000 / 0.500 | 1.000 / 1.000 / 1.000 | 0 / 0 / **+0.500** |
| fragmented | pdf / jpeg / zip | 0.834 / 0.796 / 0.347 | 0.834 / 0.796 / 0.000 | 0 / 0 / **−0.347** |
| partial-overwrite | pdf / jpeg / zip | 0.985 / 0.455 / 0.475 | 0.985 / 0.000 / 0.000 | 0 / **−0.455** / **−0.475** |
| damaged-sectors | pdf / jpeg / zip | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000 | 0 / 0 / 0 |
| **MEAN** | | **0.593** | **0.574** | **−0.018** |

### Three defects isolated

**A — `C_struct` cannot see swallowed foreign sectors.** Fragmented JPEG: 9 blocks, 34,901 B vs 22,613 truth, 12 KB of foreign filler injected mid-scan, **`C_struct` = 1.0000**. Fragmented PDF: 78,287 vs 65,999, **`C_struct` = 0.8901** — both clear the 0.85 gate and are emitted, tying the naive baseline exactly on the one scenario that is supposed to be the differentiator. Cause: `_jpeg_tests` keys on the 0xFF escape rule inside the scan; filler containing no 0xFF produces zero violations *and earns a passing bonus*. `_zip_tests` walks the local-header chain and correctly scored 0.0000 — which is why ZIP is the only mime that reaches reassembly.

**B — reassembly drops fragments.** Fragmented ZIP: 13 candidate orphan blocks (10 real + 3 filler), the Hungarian chain used only **5**, yielding 20,054 B vs 40,534 truth. `tau=0.55` makes "no successor" too cheap, so the assignment prefers dropping links to taking them.

**C — the strict rejection gate destroys partial recoveries.** All reassembled chains failed `verify_carved_file` (must fully open) and were `continue`d. Net effect: we emit **nothing** in 3 cells where the naive baseline surfaces a usable partial (0.347 / 0.455 / 0.475). For an investigator a flagged partial beats silence.

### Fix attempt 1/3 on defect A — failed, and why

Added a carve-time continuity gate using the engine's own `sht_pair_affinity`. Swept thresholds 0.0–0.50: a cliff between 0.20 and 0.30 flips every stream at once. Measured the distributions directly instead of tuning further:

```
TRUE adjacencies      n=27  mean 0.8285  range 0.2702 .. 0.9984
CONTAMINATION bounds  n=6   mean 0.4478  range 0.2702 .. 0.8029
SEPARABLE? NO — ranges overlap
```

The posterior collapses to a handful of discrete values (0.9984 / 0.8556 / 0.8029 / 0.2702) because **`sht_pair_affinity` has JPEG-specific pairwise tests but none for PDF or ZIP** — those fall back to generic entropy/header/footer tests, so every PDF boundary, real or contaminated, returns the identical 0.8029. This is a capability ceiling of the primitive, not a tuning problem. Gate shipped off; no regression (56/56 tests pass, matrix byte-identical to pre-edit).

### Next iteration
1. Add PDF and ZIP **pairwise** continuity tests to `sht_pair_affinity` (prerequisite for defect A). PDF: object-number monotonicity and stream-extent straddling across the boundary. ZIP: local-header offset arithmetic, which `_zip_tests` already proves works whole-stream.
2. Defect C: emit low-confidence partials with an explicit `PARTIAL / reliability` label instead of `continue`.
3. Defect B: calibrate `tau` against known-correct chains rather than the current intuition value.
4. Erasure side — not started. File-level erasure on `D:` works unelevated; raw verify/TRIM needs the elevated session.

---

## Iteration 2 — fix the downstream first, then the detector

### Correction to iteration 1
I reported "sht_pair_affinity has no PDF pairwise tests". **Wrong** — `carver_ml.py:518-526` has three of them (xref-pin adjacency, object-number succession, open-stream straddling). The real defect is that **every one is gated on `ib.objs` being non-empty**. A filler block contains no ` obj` token, so all three go neutral and only the generic tests run — which is why a contaminated boundary returned the identical 0.8029 as a true one. Also found: `_FragInfo.pin` is only populated inside `build_pool_context`, so the strongest PDF adjacency test never fires at carve time at all.

### Changed

1. **`carver_ml.py` — `_repeat_unit` / `_period_continues` (new), wired as a generic pairwise test.**
   Nearly shipped a bad discriminator first: raw "is this block periodic" flags filler, but **legitimate content is often periodic too** — this repo's own test PDF has a `/Note` padding object repeating one phrase across 9 blocks. The valid test is *phase-continuous* periodicity: does B's head continue A's tail repetition **in phase**. Real padding spanning a block boundary does; an unrelated filler sector starts its own cycle.

   | | before | after |
   |---|---|---|
   | true adjacencies (n=27) | mean 0.8285, min 0.2702 | mean **0.8825**, min 0.2702 |
   | contamination (n=6) | mean 0.4478, **max 0.8029** | mean **0.1323**, max **0.2702** |

   Contamination mean fell 3.4×. Still not fully separable — one true boundary sits at 0.2702 too.

2. **`signature_carver.py` — carve-time continuity gate left OFF.** Measured end-to-end at thresholds 0.28–0.70: fidelity on the fragmented cell **collapsed 0.543 → 0.144**. Cutting the stream at the contamination boundary is *correct*, but the blocks then land in a reassembler that cannot rebuild them, so a correct split is worse than a contaminated-but-openable file. **Defect A's fix is blocked by defects B and C — I had the ordering wrong.** The improved affinity is kept (it also feeds reassembly); the gate stays off until reassembly can absorb the split.

3. **`api.py` — strict rejection gate → triage gate.** Was `continue` on any imperfect carve, which emitted *nothing* where the naive baseline surfaced a usable partial. Now every signature-bearing carve is surfaced, but `is_verified` / `validation_status` are computed (`OPEN_VERIFIED` vs `PARTIAL_UNVERIFIED`) and priority drops to `REVIEW` when unverified. This also removes the hardcoded `is_verified=True` the audit flagged.

4. **Candidate ranking by reliability score, not size.** Ranking unverified candidates by length made the pipeline emit a 40,960 B block-aligned chain (fidelity 0.113) over a shorter structurally-intact carve (0.475). Now: verified beats unverified; among unverified, higher `S` wins.

5. **`api.py` — demoted streams retained as fallback candidates.** `validate_carve` discarded them entirely; when reassembly produced something worse, the worse result shipped. Both are now surfaced, distinguished by the partial label.

### Measured — full matrix

| scenario | mime | baseline | ours | delta |
|---|---|---|---|---|
| clean-deletion | pdf / jpeg / zip | 1.000 / 1.000 / 0.500 | 1.000 / 1.000 / 1.000 | 0 / 0 / **+0.500** |
| quick-format | pdf / jpeg / zip | 1.000 / 1.000 / 0.500 | 1.000 / 1.000 / 1.000 | 0 / 0 / **+0.500** |
| fragmented | pdf / jpeg / zip | 0.834 / 0.796 / 0.347 | 0.834 / 0.796 / 0.326 | 0 / 0 / −0.021 |
| partial-overwrite | pdf / jpeg / zip | 0.985 / 0.455 / 0.475 | 0.985 / 0.455 / 0.475 | 0 / 0 / 0 |
| damaged-sectors | pdf / jpeg / zip | 0.000 / 0.000 / 0.000 | 0.404 / 0.254 / 0.113 | **+0.404 / +0.254 / +0.113** |
| **MEAN** | | **0.593** | **0.709** | **+0.117** |

**Trajectory: −0.018 → +0.080 → +0.117.** `damaged-sectors` went from three zeros to three wins. All three `partial-overwrite` losses became ties. One marginal loss remains (fragmented zip, −0.021). 56/56 tests pass.

### Still open / not fixed
- **Chimera still self-labels `OPEN_VERIFIED`.** Re-ran the audit's two-interleaved-JPEG case: 14,080 B, S=0.871, opens cleanly, byte-exact to neither source — so the partial-label fix does not touch it. Needs cross-source contamination detection, which phase-continuity cannot provide (no periodic filler involved). **Audit P0-6 remains FAILED.**
- **Defect B (reassembly drops fragments)** untouched — `tau=0.55` still uncalibrated.
- **`fragmented` PDF/JPEG still exactly tie the naive baseline** — the headline differentiator is still unproven on that cell, blocked on defect B.
- **Erasure side: not started.**

### Next
1. Defect B: calibrate `tau` against known-correct chains, then re-test enabling the continuity gate (the blocked path from this iteration).
2. Cross-source contamination detection for the chimera case.
3. Erasure side — file-level on `D:` works unelevated; raw verify/TRIM needs the elevated session.

---

## Iteration 3 — the Siamese model is the bottleneck

### Correction to iteration 1
I attributed defect B to `tau=0.55` making "no successor" too cheap. **Wrong.** Swept tau across 0.25–0.95: the recovered chain was **5 blocks at every single value**. tau has no effect on this case at all.

### Root cause, measured
Ranked each fragment's true successor in a shuffled single-file pool — no contamination, the easiest possible case — and compared the three affinity sources the resolver can use:

| affinity source | pdf (16 links) | jpeg (5) | zip (9) | **total top-1** |
|---|---|---|---|---|
| SHT only (`alpha=1, beta=0`) | 15 | 5 | 9 | **29/30 = 96.7%** |
| Siamese only (`beta=1`) | 1 | 1 | 1 | **3/30 = 10.0%** |
| blend 50/50 — **the shipped default** | 15 | 1 | 2 | **18/30 = 60.0%** |

Chance for a pool of n is ~1/n ≈ 10%. **The Siamese adjacency model performs at chance**, and averaging it 50/50 with a near-perfect deterministic ranker dragged 96.7% down to 60.0%. That is the actual cause of reassembly emitting mis-ordered chains — on the fragmented ZIP it returned blocks `[35, 36, 45, 38, 47]` where the truth is `35,36,37,38,39`.

Secondary finding: `resolve()` drops every chain whose head is not a file header (`valid_chains` filter), so the *second half* of each fragmented file — necessarily headless — was discarded. Fixing the affinity made this moot for ZIP, but it remains a latent limitation.

### Changed
**`graph_reassembly.py` — `GlobalFragmentResolver` default `alpha=0.5, beta=0.5` → `alpha=1.0, beta=0.0`.** One line. The Siamese model is still used for candidate pruning on large pools, never for ranking. The measurement table above is recorded in the docstring so beta is only re-enabled against evidence.

### Measured

| scenario | mime | baseline | ours | delta |
|---|---|---|---|---|
| clean-deletion | pdf / jpeg / zip | 1.000 / 1.000 / 0.500 | 1.000 / 1.000 / 1.000 | 0 / 0 / **+0.500** |
| quick-format | pdf / jpeg / zip | 1.000 / 1.000 / 0.500 | 1.000 / 1.000 / 1.000 | 0 / 0 / **+0.500** |
| fragmented | pdf / jpeg / zip | 0.834 / 0.796 / 0.347 | 0.834 / 0.796 / **1.000** | 0 / 0 / **+0.653** |
| partial-overwrite | pdf / jpeg / zip | 0.985 / 0.455 / 0.475 | 0.985 / 0.455 / 0.475 | 0 / 0 / 0 |
| damaged-sectors | pdf / jpeg / zip | 0.000 / 0.000 / 0.000 | 0.404 / 0.000 / 0.102 | **+0.404** / 0 / **+0.102** |
| **MEAN** | | **0.593** | **0.737** | **+0.144** |

**Trajectory: −0.018 → +0.080 → +0.117 → +0.144.**
`fragmented zip` went 0.326 → **1.000, byte-exact** — the flagship "reassembles fragmented files where signature carvers cannot" claim, finally demonstrated on a measured cell rather than asserted. 56/56 tests pass.

Regression accepted: `damaged-sectors jpeg` 0.254 → 0.000. The previous 0.254 came from a Siamese-noise chain that happened to be partially valid; losing it is the cost of removing a chance-level ranker, and 0.254 was not a usable recovery anyway.

### Attempt 3/3 on defect A — rejected on evidence
With reassembly now working, re-tested the carve-time continuity gate. It is genuinely useful *and* genuinely harmful, on the same cell:

| threshold | frag-pdf | frag-jpeg | frag-zip | mean |
|---|---|---|---|---|
| 0.00 (off) | **0.834** | 0.796 | 1.000 | **0.876** |
| 0.28–0.50 | 0.484 | **1.000** | 1.000 | 0.828 |

The gate makes fragmented JPEG **byte-exact** but wrecks PDF, because phase-continuity is confused by PDF padding objects. Tried dual-carve — run both, let the reliability score arbitrate. **Measured 0.716, worse than 0.737**: `S` ranked the cut PDF (fidelity 0.484) above the contiguous one (fidelity 0.834).

**So `S` is not a usable proxy for fidelity.** That is the `w1..w4`-set-by-intuition problem, and it now blocks a change that is otherwise worth +0.204 on fragmented JPEG. Dual-carve reverted; gate stays off.

### Next
1. **Calibrate `w1..w4` against measured fidelity** — the bench now produces exactly the labelled data needed (candidate → true fidelity). This unblocks dual-carve, worth ~+0.2 on fragmented JPEG.
2. Headless-chain splicing in `resolve()`.
3. Chimera cross-source detection — **audit P0-6 still FAILED**.
4. Erasure side — still not started.

---

## Iteration 4 — calibrate the reliability weights

### Correction to iteration 3
I concluded "S is not a usable proxy for fidelity" and made weight calibration the blocker for dual-carve. **That was too strong.** Built `bench/calibrate.py`, harvested 156 candidates over 5 scenarios x 8 seeds with measured fidelity labels, and validated on held-out seeds:

| weights | train rank-acc | **held-out rank-acc** |
|---|---|---|
| shipped (0.30/0.30/0.15/0.25) | 85.7% | **91.1%** |
| fit-on-train (→ C_struct only) | 92.9% | 89.3% |
| hf+struct (0.35/0.65/0/0) | 92.9% | 89.3% |
| struct+ent | 85.7% | 89.3% |

**The train-selected optimum underperforms the shipped weights on held-out data.** Every alternative lands within a few groups of 56 — noise. **The weights were NOT changed**: there is no evidence they are miscalibrated. S ranks candidates correctly ~91% of the time; the dual-carve failure was one of the other 9%, not a systematic defect.

An earlier run also looked wrong for a harness reason: `rank_quality` pooled all 8 seeds into one group, giving only 14 groups and making a 1-group difference look like +7%. Fixed to group per (scenario, seed, mime) → 112 groups.

### Component-level finding that *is* solid (n=156)
Correlation of each score component with measured fidelity:

| component | r | verdict |
|---|---|---|
| `C_struct` | **+0.846** | by far the best predictor |
| `C_hf` | +0.630 | solid |
| `1 - Δ_ent` | −0.175 | weakly anti-correlated globally, but discriminates *within* a candidate group (Simpson's paradox) |
| `C_sem` | **−0.337** | anti-correlated, and it carries w4 = 0.25 |

`C_sem` is sourced *exclusively* from the Siamese model that iteration 3 measured at chance. It does not merely fail to help — it anti-predicts fidelity. Left in place for now because removing it did not improve held-out ranking (89.3% vs 91.1%); flagged as the strongest candidate for removal once the model is retrained or dropped.

### Changed
**`carver_ml.py::_pdf_tests` — `startxref` resolution test given weight 3.0.**
Root cause traced exactly: the test *does* fail on a contaminated PDF, but at weight 1.0 its LLR of −4.60 was outvoted by five cheap passing tests totalling +6.69, yielding posterior 0.8901 — just over the 0.85 coherence gate. A PDF whose `startxref` does not resolve has had bytes inserted or removed; that is a hard invariant, not one vote among six.

| | before | after |
|---|---|---|
| contaminated PDF (78,287 B vs 65,999 truth) | C_struct **0.8901** — cleared the gate | **0.0008** — demoted |
| clean truth PDF | 1.0000 | 1.0000 |
| clean-deletion / quick-format / partial-overwrite carves | 1.0000 | 1.0000 |

No false positives. 56/56 tests pass.

### Measured

| scenario | mime | baseline | ours | delta |
|---|---|---|---|---|
| clean-deletion | pdf / jpeg / zip | 1.000 / 1.000 / 0.500 | 1.000 / 1.000 / 1.000 | 0 / 0 / **+0.500** |
| quick-format | pdf / jpeg / zip | 1.000 / 1.000 / 0.500 | 1.000 / 1.000 / 1.000 | 0 / 0 / **+0.500** |
| fragmented | pdf / jpeg / zip | 0.834 / 0.796 / 0.347 | 0.484 / 0.796 / **1.000** | −0.350 / 0 / **+0.653** |
| partial-overwrite | pdf / jpeg / zip | 0.985 / 0.455 / 0.475 | 0.985 / 0.455 / 0.475 | 0 / 0 / 0 |
| damaged-sectors | pdf / jpeg / zip | 0.000 / 0.000 / 0.000 | 0.404 / 0.000 / 0.102 | **+0.404** / 0 / **+0.102** |
| **MEAN** | | **0.593** | **0.713** | **+0.121** |

**Trajectory: −0.018 → +0.080 → +0.117 → +0.144 → +0.121.**

This iteration is a **−0.024 regression on the bench metric, accepted deliberately.** The bench forces exactly one candidate per mime; the product does not. Verified what `engine/api.py` now emits for the fragmented cell:

```
[VALID           ] image/jpeg       34901B S=0.859 fidelity=0.796 -> OPEN_VERIFIED
[DEMOTED-FALLBACK] application/pdf  78287B S=0.537 fidelity=0.834 -> PARTIAL_UNVERIFIED
[DEMOTED-FALLBACK] application/zip  52822B S=0.570 fidelity=0.347 -> PARTIAL_UNVERIFIED
```

The 0.834 PDF still reaches the investigator — it is simply no longer *certified structurally sound* while carrying 12 KB of foreign sectors. Trading 0.024 of a single-pick metric for correct evidentiary labelling is the right trade for this tool.

### Still open
- **JPEG contamination remains undetected.** That 34,901 B JPEG is 1.54× its 22,613 B truth and still labelled `OPEN_VERIFIED`, because `_jpeg_tests` keys on the 0xFF escape rule and filler containing no 0xFF produces zero violations. Needs the same treatment `_pdf_tests` just got — a hard structural invariant with real weight. **This is also the chimera case: audit P0-6 still FAILED.**
- Headless-chain splicing in `resolve()` — PDF reassembly still produces 0.484.
- `C_sem` / Siamese model: retrain or remove.
- **Erasure side: still not started.**

---

## Iteration 5 — JPEG contamination: two approaches, both rejected

Target was the JPEG counterpart of iteration 4's PDF fix: a hard structural invariant that
detects foreign sectors swallowed into an entropy-coded scan. **Both attempts failed. No
fidelity change — MEAN stays 0.713 / +0.121, 56/56 tests pass.** Two findings are worth more
than the non-result.

### Attempt 1 — 0xFF density in the scan. REJECTED on false positives.
The escape-rule test is blind to filler containing no 0xFF. Density looked like a clean
discriminator:

| content | 0xFF per 4096 B window |
|---|---|
| real JPEG scan (`big_jpeg`) | 170, 216, 246, 248, 304 |
| filler / zeros / ASCII text / PDF body | **0** |
| uniform random bytes | 17 |

`P(zero 0xFF in 4096 B of random data) = 1.1e-07`, so a zero-FF window inside a scan looked
impossible. Then I checked legitimate low-detail images:

| image | min 0xFF/4 KB | zero-FF windows |
|---|---|---|
| flat grey 1024x1024 | **0** | 4 of 4 |
| smooth gradient 1024x1024 | **0** | 14 of 14 |
| solid black 512x512 | 1 | 1 of 1 |

Flat and gradient JPEGs compress to scans with **no** 0xFF bytes at all. The test would flag
screenshots, document scans and flat-background photos — exactly what forensic work is full
of — as contaminated. Rejected before shipping.

### Attempt 2 — decode the scan, compare MCU count. BLOCKED by a broken decoder.
The real invariant: a baseline JPEG must decode to exactly `ceil(W/8Hmax) * ceil(H/8Vmax)`
MCUs and end cleanly. Implemented it against the engine's existing `JpegContext`. Measured:

```
big_jpeg CLEAN    512x512  comps=3 hmax=2 vmax=2  expected=1024  got=1 clean=False
solid black 512   512x512  comps=3 hmax=2 vmax=2  expected=1024  got=1 clean=False
noisy 1024       1024x1024 comps=3 hmax=2 vmax=2  expected=4096  got=1 clean=False
grayscale 512     512x512  comps=1 hmax=1 vmax=1  expected=4096  got=1 clean=False
```

**`JpegContext.count_mcus` returns exactly 1 MCU for every JPEG tested, valid ones included.**
It does not work for whole-stream decoding. Shipping the test on top of it gave zero
discrimination (clean and contaminated both 0.8676) *and* 0.0001 on every flat image.
Reverted in full; false positives confirmed gone (flat grey / gradient / grayscale back to
0.9860, clean 1.0000, all clear of the 0.85 gate).

### Two findings worth keeping

1. **`JpegContext.parse` returns `None` for every JPEG without restart markers.** The guard is
   `if not comps or not huff or not sos_tables or dri == 0: return None`. PIL emits no DRI, and
   neither do the common camera encoders — verified at quality 50 and 95. So the engine's
   entire JPEG MCU-decode path, including the `boundary_ok` restart-interval test that
   `sht_pair_affinity` advertises as its strongest JPEG evidence, **never fires in production.**
2. **`count_mcus` is non-functional** (finding above). Relaxing the `dri == 0` guard alone
   achieves nothing — both must be fixed together, and that is a real Huffman-decoder debugging
   task, not a tuning change.

Both are now documented in code at the point of failure rather than left to be rediscovered.

### Status after 5 iterations

| scenario | mime | baseline | ours | delta |
|---|---|---|---|---|
| clean-deletion | pdf / jpeg / zip | 1.000 / 1.000 / 0.500 | 1.000 / 1.000 / 1.000 | 0 / 0 / **+0.500** |
| quick-format | pdf / jpeg / zip | 1.000 / 1.000 / 0.500 | 1.000 / 1.000 / 1.000 | 0 / 0 / **+0.500** |
| fragmented | pdf / jpeg / zip | 0.834 / 0.796 / 0.347 | 0.484 / 0.796 / **1.000** | −0.350 / 0 / **+0.653** |
| partial-overwrite | pdf / jpeg / zip | 0.985 / 0.455 / 0.475 | 0.985 / 0.455 / 0.475 | 0 / 0 / 0 |
| damaged-sectors | pdf / jpeg / zip | 0.000 / 0.000 / 0.000 | 0.404 / 0.000 / 0.102 | **+0.404** / 0 / **+0.102** |
| **MEAN** | | **0.593** | **0.713** | **+0.121** |

**Trajectory: −0.018 → +0.080 → +0.117 → +0.144 → +0.121 → +0.121.**

### Next
1. Fix `count_mcus` + the `dri == 0` guard together — the only route to JPEG contamination
   detection, and therefore to **audit P0-6 (chimera), still FAILED**.
2. Headless-chain splicing in `resolve()` — PDF reassembly still 0.484.
3. **Erasure side: still not started.** This is now the largest untouched area; the USB
   (`C2ED9DAB`) is confirmed wipeable and file-level work on `D:` needs no elevation.

"""Coverage-matrix benchmark: naive market-equivalent carving vs the ForensiWipe pipeline,
scored on the same synthetic media with known ground truth.

Every cell reports baseline -> ours -> delta. Nothing is reported without a baseline.
"""
from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "bench"))

from fidelity import score, null_score, Fidelity          # noqa: E402
from engine.pretrain_utils import BLOCK_SIZE               # noqa: E402
from engine.signature_carver import carve                  # noqa: E402
from engine.graph_reassembly import validate_carve, GlobalFragmentResolver  # noqa: E402
from engine.carver_ml import SiameseAdjacency              # noqa: E402
from engine.api import verify_carved_file                  # noqa: E402
from engine.report_gen import ForensicReliabilityScorer    # noqa: E402

_spec = importlib.util.spec_from_file_location("g", str(ROOT / "backend/demo_data/generate_demo_drive.py"))
G = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(G)

def big_pdf(seed: int = 3) -> bytes:
    """~90 KB / 22 blocks. The demo generator's 6 KB PDF is 2 blocks, which is too
    small for any fragmentation scenario to actually bite — a 'split in half'
    of a 2-block file is not fragmentation, it is a 1-block move."""
    objs, body = [], b"%PDF-1.4\n"
    body += b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    kids = " ".join(f"{3+i} 0 R" for i in range(6))
    body += b"2 0 obj\n<< /Type /Pages /Kids [" + kids.encode() + b"] /Count 6 >>\nendobj\n"
    n = 3
    for pg in range(6):
        body += (b"%d 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                 b"/Contents %d 0 R /Resources << /Font << /F1 99 0 R >> >> >>\nendobj\n" % (n, n + 6))
        n += 1
    for pg in range(6):
        lines = b"".join(
            b"BT /F1 11 Tf 50 %d Td (CASE 2026-904 PAGE %d LINE %02d LEDGER ENTRY %06d) Tj ET\n"
            % (740 - 12 * k, pg + 1, k, pg * 1000 + k) for k in range(55))
        body += b"%d 0 obj\n<< /Length %d >>\nstream\n" % (n, len(lines)) + lines + b"endstream\nendobj\n"
        n += 1
    body += b"99 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    pad = b"100 0 obj\n<< /Note (" + (b"CLASSIFIED EVIDENCE RECORD " * 1400) + b") >>\nendobj\n"
    body += pad
    import re as _re
    ents = sorted((int(m.group(1)), m.start()) for m in _re.finditer(rb"(?m)^(\d+) 0 obj", body))
    xref_off = len(body)
    xref = b"xref\n0 1\n0000000000 65535 f \n"
    for num, off in ents:
        xref += b"%d 1\n%010d 00000 n \n" % (num, off)
    return body + xref + b"trailer\n<< /Size 101 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % xref_off


def big_jpeg(seed: int = 3) -> bytes:
    """~80 KB / 20 blocks of real entropy-coded scan data."""
    import io as _io
    from PIL import Image as _Im
    r = np.random.default_rng(seed)
    a = np.zeros((512, 512, 3), np.uint8)
    for _ in range(160):
        x, y, w, h = r.integers(0, 480, 4)
        a[y:y + h, x:x + w] = r.integers(0, 255, 3)
    b = _io.BytesIO(); _Im.fromarray(a).save(b, "JPEG", quality=95); return b.getvalue()


def big_zip(seed: int = 3) -> bytes:
    """~60 KB / 15 blocks across several members."""
    import io as _io, zipfile as _zf
    r = np.random.default_rng(seed)
    b = _io.BytesIO()
    with _zf.ZipFile(b, "w", _zf.ZIP_DEFLATED) as z:
        for i in range(5):
            z.writestr(f"ledger_{i:02d}.csv",
                       "".join(f"{i},{k},ACC{r.integers(10**9,10**10)},{r.integers(1,99999)}\n"
                               for k in range(700)))
    return b.getvalue()


MIMES = {"application/pdf": big_pdf,
         "image/jpeg": big_jpeg,
         "application/zip": big_zip}

CONTINUITY_TH = 0.30

FILLER = (b"OBSOLETE RESIDUAL CONTAMINATED SECTOR - PURGE REQUIRED " * 80)[:BLOCK_SIZE]


def blockify(b: bytes) -> list[bytes]:
    n = (len(b) + BLOCK_SIZE - 1) // BLOCK_SIZE
    return [b[i * BLOCK_SIZE:(i + 1) * BLOCK_SIZE].ljust(BLOCK_SIZE, b"\0") for i in range(n)]


# --------------------------------------------------------------------------- #
# scenario builders -> (image, {mime: truth_bytes})
# --------------------------------------------------------------------------- #
def build(scenario: str, rng: np.random.Generator) -> tuple[np.ndarray, dict[str, bytes]]:
    truth = {m: fn() for m, fn in MIMES.items()}
    blks = {m: blockify(d) for m, d in truth.items()}
    zero = b"\0" * BLOCK_SIZE
    disk: list[bytes] = [zero] * 4                      # leading unallocated

    if scenario == "clean-deletion":
        # contiguous, metadata gone, data intact — the easy case
        for m in truth:
            disk += blks[m] + [zero]
    elif scenario == "quick-format":
        # same layout, but FS metadata region zeroed and a stale boot sector up front
        disk = [zero] * 8
        for m in truth:
            disk += blks[m] + [zero] * 2
    elif scenario == "fragmented":
        # each file split across non-contiguous blocks, foreign filler between halves
        for m in truth:
            b = blks[m]
            half = max(1, len(b) // 2)
            disk += b[:half] + [FILLER] * 3 + b[half:] + [zero]
    elif scenario == "partial-overwrite":
        # a later file has clobbered the middle of each artifact — unrecoverable gap
        for m in truth:
            b = list(blks[m])
            if len(b) >= 3:
                b[len(b) // 2] = bytes(rng.integers(0, 256, BLOCK_SIZE, dtype=np.uint8))
            disk += b + [zero]
    elif scenario == "damaged-sectors":
        # simulated bad sectors read back as 0xFF runs inside each artifact
        for m in truth:
            b = list(blks[m])
            if len(b) >= 2:
                b[-1] = b"\xff" * BLOCK_SIZE
            disk += b + [zero]
    else:
        raise ValueError(scenario)

    disk += [zero] * 4
    return np.frombuffer(b"".join(disk), np.uint8).reshape(-1, BLOCK_SIZE), truth


# --------------------------------------------------------------------------- #
# BASELINE: plain signature carving (PhotoRec / Scalpel model)
# --------------------------------------------------------------------------- #
SIGS = {"image/jpeg": (b"\xff\xd8\xff", b"\xff\xd9"),
        "application/pdf": (b"%PDF-", b"%%EOF"),
        "application/zip": (b"PK\x03\x04", b"PK\x05\x06")}


def naive_carve(raw: bytes) -> dict[str, bytes]:
    """Header -> first following footer, consume everything in between. No structural
    validation, no fragment matching. This is what most existing tools do."""
    out: dict[str, bytes] = {}
    for mime, (hdr, ftr) in SIGS.items():
        h = raw.find(hdr)
        if h < 0:
            continue
        f = raw.find(ftr, h + len(hdr))
        if f < 0:
            continue
        out[mime] = raw[h:f + len(ftr)]
    return out


# --------------------------------------------------------------------------- #
# OURS: full pipeline
# --------------------------------------------------------------------------- #
_SIA = None


def forensiwipe_carve(image: np.ndarray, deep: bool = True) -> dict[str, bytes]:
    global _SIA
    scorer = ForensicReliabilityScorer()
    # Single contiguous carve. Dual-carve (also running the continuity gate and letting
    # the reliability ranking arbitrate) was measured and REJECTED at 0.716 vs 0.737:
    # the gate makes fragmented JPEG byte-exact (0.796 -> 1.000) but wrecks PDF
    # (0.834 -> 0.484), and S picks the wrong one because S is not calibrated against
    # actual fidelity. Re-try dual-carve once w1..w4 are fitted — see ITERATION_LOG.md.
    res = carve(image)
    valid, orphans = validate_carve(image, res, min_struct=0.85)


    # mirrors engine/api.py: a verified candidate always beats an unverified one.
    # Among unverified candidates rank by the engine's own reliability score S, NOT by
    # size — "bigger" is not "better" once nothing validates, and ranking by length made
    # the pipeline emit a 40,960 B block-aligned chain (fidelity 0.113) over a shorter,
    # structurally intact carve.
    best: dict[str, tuple[int, float, bytes]] = {}

    def offer(mime: str, data: bytes, verified: bool, S: float):
        key = (1 if verified else 0, S)
        if mime not in best or key > best[mime][:2]:
            best[mime] = (key[0], key[1], data)

    def consider_stream(s):
        if s.mime == "application/octet-stream":
            return
        d = s.assemble(image)
        ok, _ = verify_carved_file(d, s.mime)
        sc = scorer.score(data=d, mime=s.mime)
        offer(s.mime, d, bool(ok) and sc.S >= 0.65, sc.S)

    for s in valid:
        consider_stream(s)
    # Streams demoted by the coherence gate still go to reassembly, but their straight
    # assembly is retained as a fallback candidate. Discarding it outright meant that
    # when reassembly produced something worse, we shipped the worse result.
    for s in res.streams:
        if s.closed:
            consider_stream(s)

    if deep and orphans:
        if _SIA is None:
            _SIA = SiameseAdjacency()
        cand = [b for b in orphans if image[b].any()][:200]
        if cand:
            ob = [image[b].tobytes() for b in cand]
            rr = GlobalFragmentResolver(siamese=_SIA).resolve(ob, mime=None)
            for ch in rr.chains:
                if not ch.mime or ch.mime == "application/octet-stream":
                    continue
                d = ch.assemble(ob)
                if not d.strip(b"\0") or len(d) < 64:
                    continue
                ok, _ = verify_carved_file(d, ch.mime)
                sc = scorer.score(data=d, mime=ch.mime, fragments=ob,
                                  chain_order=ch.order, chain_residual=ch.residual, siamese=_SIA)
                offer(ch.mime, d, bool(ok) and sc.S >= 0.65, sc.S)

    return {m: v[2] for m, v in best.items()}


# --------------------------------------------------------------------------- #
SCENARIOS = ["clean-deletion", "quick-format", "fragmented", "partial-overwrite", "damaged-sectors"]


def run(scenarios=SCENARIOS, verbose=True) -> dict:
    rng = np.random.default_rng(1234)
    results = {}
    for sc in scenarios:
        img, truth = build(sc, rng)
        raw = img.tobytes()
        t0 = time.perf_counter(); base = naive_carve(raw); t_base = time.perf_counter() - t0
        t0 = time.perf_counter(); ours = forensiwipe_carve(img); t_ours = time.perf_counter() - t0
        row = {}
        for mime, tr in truth.items():
            fb = score(base[mime], tr, mime) if mime in base else null_score(mime, tr, "nothing recovered")
            fo = score(ours[mime], tr, mime) if mime in ours else null_score(mime, tr, "nothing recovered")
            row[mime] = (fb, fo)
        results[sc] = {"rows": row, "t_base": t_base, "t_ours": t_ours, "blocks": len(img)}
        if verbose:
            print(f"\n### {sc}  ({len(img)} blocks, baseline {t_base*1000:.0f} ms, ours {t_ours*1000:.0f} ms)")
            for mime, (fb, fo) in row.items():
                d = fo.overall - fb.overall
                print(f"  {mime:<16} base={fb.overall:.3f}  ours={fo.overall:.3f}  delta={d:+.3f}")
                print(f"      base: {fb.row()}")
                print(f"      ours: {fo.row()}  | {fo.notes.get('structural','')[:70]}")
    return results


def summary(results: dict) -> None:
    print("\n" + "=" * 100)
    print(f"{'scenario':<20}{'mime':<18}{'baseline':>10}{'ours':>10}{'delta':>10}  verdict")
    print("=" * 100)
    agg_b, agg_o = [], []
    for sc, r in results.items():
        for mime, (fb, fo) in r["rows"].items():
            d = fo.overall - fb.overall
            v = "WIN" if d > 0.02 else ("TIE" if abs(d) <= 0.02 else "LOSS")
            print(f"{sc:<20}{mime:<18}{fb.overall:>10.3f}{fo.overall:>10.3f}{d:>+10.3f}  {v}")
            agg_b.append(fb.overall); agg_o.append(fo.overall)
    print("-" * 100)
    print(f"{'MEAN':<38}{np.mean(agg_b):>10.3f}{np.mean(agg_o):>10.3f}{np.mean(agg_o)-np.mean(agg_b):>+10.3f}")


if __name__ == "__main__":
    summary(run())

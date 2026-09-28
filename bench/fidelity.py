"""Recovery fidelity scoring — the measurable version of "close to the original".

Four axes per the fidelity bar. Each returns [0,1]; `overall` is their mean over
the axes that apply to the file type. No axis is allowed to default to 1.0 when
it cannot be evaluated — it returns None and is excluded, and the caller reports
which axes were skipped.
"""
from __future__ import annotations

import io
import hashlib
import zipfile
from dataclasses import dataclass, field, asdict
from typing import Any


# --------------------------------------------------------------------------- #
# axis 1: byte match
# --------------------------------------------------------------------------- #
def byte_match(recovered: bytes, truth: bytes) -> float:
    """Longest-common-subsequence-free cheap measure: fraction of truth bytes that
    appear at the correct offset once the best alignment offset is chosen.

    A carved file that is byte-identical scores 1.0. One that prepends/appends
    junk but contains the truth verbatim scores len(truth)/len(recovered) —
    i.e. oversize output is penalised, which is the whole point.
    """
    if not truth:
        return 0.0
    if recovered == truth:
        return 1.0
    # best alignment: does truth appear verbatim?
    idx = recovered.find(truth)
    if idx >= 0:
        return len(truth) / len(recovered)
    # otherwise positional agreement at offset 0, normalised by the larger size
    n = min(len(recovered), len(truth))
    same = sum(1 for a, b in zip(recovered[:n], truth[:n]) if a == b)
    return same / max(len(recovered), len(truth))


# --------------------------------------------------------------------------- #
# axis 2: validity — does it open in a real parser
# --------------------------------------------------------------------------- #
def validity(data: bytes, mime: str) -> tuple[float, str]:
    try:
        if mime == "image/jpeg" or mime == "image/png":
            from PIL import Image
            with Image.open(io.BytesIO(data)) as im:
                im.verify()
            with Image.open(io.BytesIO(data)) as im:
                im.load()
            return 1.0, "decodes"
        if mime == "application/pdf":
            import pypdf
            r = pypdf.PdfReader(io.BytesIO(data), strict=False)
            _ = len(r.pages)
            return 1.0, f"{len(r.pages)} page(s)"
        if mime == "application/zip":
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                bad = z.testzip()
            return (0.0, f"CRC fail on {bad}") if bad else (1.0, "all members CRC-ok")
    except Exception as exc:
        return 0.0, f"{type(exc).__name__}: {str(exc)[:60]}"
    return 0.0, "unknown mime"


# --------------------------------------------------------------------------- #
# axis 3: structural completeness — required internal structures, in order
# --------------------------------------------------------------------------- #
def structural(data: bytes, mime: str) -> tuple[float, str]:
    """Fraction of the format's mandatory structures that are present AND in the
    correct relative order. Deliberately independent of the engine's own
    C_struct so it cannot grade its own homework."""
    if mime == "image/jpeg":
        req = [b"\xff\xd8", b"\xff\xdb", b"\xff\xc0", b"\xff\xc4", b"\xff\xda", b"\xff\xd9"]
        pos, ok, last = [], 0, -1
        for m in req:
            p = data.find(m, last + 1)
            pos.append(p)
            if p > last:
                ok += 1
                last = p
        return ok / len(req), f"markers in order {ok}/{len(req)}"
    if mime == "application/pdf":
        checks = {
            "%PDF- header": data.startswith(b"%PDF-"),
            "obj/endobj balanced": data.count(b" obj") == data.count(b"endobj") and data.count(b"endobj") > 0,
            "stream/endstream balanced": data.count(b"stream") == 2 * data.count(b"endstream") and data.count(b"endstream") > 0,
            "xref table present": b"xref" in data,
            "trailer present": b"trailer" in data,
            "startxref resolves": _startxref_resolves(data),
            "%%EOF terminal": data.rstrip(b"\0\r\n").endswith(b"%%EOF"),
            "no foreign filler": not _has_foreign_run(data),
        }
        ok = sum(1 for v in checks.values() if v)
        bad = [k for k, v in checks.items() if not v]
        return ok / len(checks), ("all present" if not bad else "missing: " + ", ".join(bad))
    if mime == "application/zip":
        checks = {
            "local header": data.startswith(b"PK\x03\x04"),
            "central directory": b"PK\x01\x02" in data,
            "EOCD": b"PK\x05\x06" in data,
            "EOCD is terminal": data.rstrip(b"\0").rfind(b"PK\x05\x06") >= len(data.rstrip(b"\0")) - 128,
        }
        ok = sum(1 for v in checks.values() if v)
        bad = [k for k, v in checks.items() if not v]
        return ok / len(checks), ("all present" if not bad else "missing: " + ", ".join(bad))
    return 0.0, "unknown mime"


def _startxref_resolves(d: bytes) -> bool:
    import re
    sx = d.rfind(b"startxref")
    if sx < 0:
        return False
    m = re.match(rb"\s*(\d+)", d[sx + 9:sx + 40])
    if not m:
        return False
    off = int(m.group(1))
    return 0 <= off < len(d) and (d[off:off + 4] == b"xref" or re.match(rb"\d+\s+\d+\s+obj", d[off:off + 32]) is not None)


def _has_foreign_run(d: bytes, gap: int = 1024) -> bool:
    """True if >=1KB of the file is covered by no declared PDF object and lies
    outside the header/trailer regions — i.e. swallowed foreign sectors.

    Window-scanning for syntax tokens was tried first and false-positives on
    legitimate padding held *inside* an object (a long /Note string has no PDF
    tokens in it either). Coverage by declared object extents is the correct test:
    real padding is inside an obj, a swallowed sector is not.
    """
    import re
    covered = []
    for m in re.finditer(rb"\d+\s+\d+\s+obj", d):
        end = d.find(b"endobj", m.start())
        covered.append((m.start(), (end + 6) if end >= 0 else len(d)))
    xr = d.find(b"xref")
    covered.append((0, min(len(d), 1024)))                       # header region
    if xr >= 0:
        covered.append((xr, len(d)))                             # xref + trailer region
    covered.sort()
    cursor = 0
    for s, e in covered:
        if s - cursor >= gap:
            return True
        cursor = max(cursor, e)
    return len(d) - cursor >= gap


# --------------------------------------------------------------------------- #
# axis 4: content completeness — is the payload all there, in order
# --------------------------------------------------------------------------- #
def content(data: bytes, truth: bytes, mime: str) -> tuple[float | None, str]:
    try:
        if mime == "image/jpeg":
            from PIL import Image
            import numpy as np
            with Image.open(io.BytesIO(data)) as a:
                ra = np.asarray(a.convert("RGB"), dtype=np.int16)
            with Image.open(io.BytesIO(truth)) as b:
                rb = np.asarray(b.convert("RGB"), dtype=np.int16)
            if ra.shape != rb.shape:
                return 0.0, f"dimension mismatch {ra.shape} vs {rb.shape}"
            mae = float(np.abs(ra - rb).mean())
            return max(0.0, 1.0 - mae / 255.0), f"pixel MAE {mae:.2f}/255"
        if mime == "application/pdf":
            import pypdf
            def words(b: bytes) -> list[str]:
                r = pypdf.PdfReader(io.BytesIO(b), strict=False)
                return " ".join((p.extract_text() or "") for p in r.pages).split()
            wa, wb = words(data), words(truth)
            if not wb:
                return None, "ground truth has no extractable text"
            # ordered overlap
            i = j = hit = 0
            while i < len(wa) and j < len(wb):
                if wa[i] == wb[j]:
                    hit += 1; i += 1; j += 1
                else:
                    i += 1
            return hit / len(wb), f"{hit}/{len(wb)} truth words recovered in order"
        if mime == "application/zip":
            def names(b: bytes) -> dict[str, str]:
                with zipfile.ZipFile(io.BytesIO(b)) as z:
                    return {n: hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}
            na, nb = names(data), names(truth)
            if not nb:
                return None, "empty archive"
            hit = sum(1 for k, v in nb.items() if na.get(k) == v)
            return hit / len(nb), f"{hit}/{len(nb)} members byte-identical"
    except Exception as exc:
        return 0.0, f"{type(exc).__name__}: {str(exc)[:50]}"
    return None, "n/a"


# --------------------------------------------------------------------------- #
@dataclass
class Fidelity:
    mime: str
    size_recovered: int
    size_truth: int
    byte_match: float
    validity: float
    structural: float
    content: float | None
    overall: float
    notes: dict[str, str] = field(default_factory=dict)

    def row(self) -> str:
        c = "n/a" if self.content is None else f"{self.content:.3f}"
        return (f"{self.mime:<16} {self.size_recovered:>7}/{self.size_truth:<7} "
                f"byte={self.byte_match:.3f} valid={self.validity:.0f} "
                f"struct={self.structural:.3f} content={c} => {self.overall:.3f}")


def score(recovered: bytes, truth: bytes, mime: str) -> Fidelity:
    bm = byte_match(recovered, truth)
    v, vn = validity(recovered, mime)
    s, sn = structural(recovered, mime)
    c, cn = content(recovered, truth, mime)
    axes = [bm, v, s] + ([c] if c is not None else [])
    return Fidelity(mime, len(recovered), len(truth), bm, v, s, c,
                    sum(axes) / len(axes), {"validity": vn, "structural": sn, "content": cn})


def null_score(mime: str, truth: bytes, why: str) -> Fidelity:
    """Nothing was recovered at all. Scores zero on every axis — not skipped."""
    return Fidelity(mime, 0, len(truth), 0.0, 0.0, 0.0, 0.0, 0.0,
                    {"validity": why, "structural": why, "content": why})


if __name__ == "__main__":
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "backend"))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "g", str(pathlib.Path(__file__).resolve().parents[1] / "backend/demo_data/generate_demo_drive.py"))
    g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)

    pdf, jpg, zp = g.generate_valid_pdf(), g.generate_valid_jpeg(), g.generate_valid_zip()
    # self-check: a file scored against itself must be 1.0 on every axis
    for data, mime in ((pdf, "application/pdf"), (jpg, "image/jpeg"), (zp, "application/zip")):
        f = score(data, data, mime)
        print("IDENTITY", f.row(), f.notes)
        assert f.byte_match == 1.0 and f.validity == 1.0, f
    # and a deliberately contaminated PDF must score clearly lower
    bad = pdf[:4096] + b"OBSOLETE RESIDUAL CONTAMINATED SECTOR - PURGE REQUIRED " * 520 + pdf[4096:]
    fb = score(bad, pdf, "application/pdf")
    print("CONTAMINATED", fb.row(), fb.notes)
    assert fb.overall < score(pdf, pdf, "application/pdf").overall, "scorer fails to penalise contamination"
    print("OK fidelity scorer self-check")

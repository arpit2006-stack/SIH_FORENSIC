"""Phase 2 (FR2.1-FR2.2): Sequential Hypothesis Testing on file structure + Siamese adjacency.

SHT: every structural check is a Bernoulli test with known pass-rates under
H1 (valid / adjacent) and H0 (corrupt / not adjacent). Log-likelihood ratios
accumulate sequentially (Wald's SPRT) and the posterior P(H1) is the score.
Tests that do not apply to the data (e.g. no RST markers present) contribute
no evidence rather than a guess.

Siamese: shared 1D-CNN trunk over the last 256 bytes of A and the first 256
bytes of B; cosine similarity -> sigmoid(scale*cos + bias) = P_adjacent.
"""
from __future__ import annotations

import logging
import math
import os
import re
from pathlib import Path
from typing import Optional

import numpy as np

from engine.pretrain_utils import BLOCK_SIZE, FILE_TYPES, SyntheticFragmentCorpus, get_optimal_execution_providers
from engine.signature_carver import SIGNATURES, detect_header
from engine.triage_scorer import calculate_shannon_entropy

log = logging.getLogger(__name__)

WINDOW = 256
SIAMESE_MODEL_PATH = "models/siamese_adjacency.onnx"
_MIME_OF = {"jpeg": "image/jpeg", "pdf": "application/pdf", "zip": "application/zip"}
_OBJ_RE = re.compile(rb"(?<![0-9])(\d{1,7}) 0 obj\b")


# --------------------------------------------------------------------------- #
# SHT core
# --------------------------------------------------------------------------- #
def sht_posterior(tests: list[tuple], prior: float = 0.5) -> float:
    """tests: (passed | None=not applicable, P(pass|H1), P(pass|H0)[, weight]).

    `weight` is the number of independent observations the test summarises, so a check
    that found 6 restart-marker violations counts as 6 pieces of evidence rather than one.
    Without it a single structural break is outvoted by a handful of cheap passing tests.
    Returns P(H1).
    """
    llr = math.log(prior / (1 - prior))
    for test in tests:
        passed, p1, p0 = test[0], test[1], test[2]
        w = test[3] if len(test) > 3 else 1.0
        if passed is None or w <= 0:
            continue
        llr += w * (math.log(p1 / p0) if passed else math.log((1 - p1) / (1 - p0)))
    llr = max(-30.0, min(30.0, llr))
    return 1.0 / (1.0 + math.exp(-llr))


# --------------------------------------------------------------------------- #
# Whole-stream structural validity  (C_struct)
# --------------------------------------------------------------------------- #
def _jpeg_scan_stats(d: bytes) -> tuple[int, int, int, int]:
    """(escape_violations, ff_count, rst_count, rst_order_violations) over entropy-coded data."""
    viol = ffs = rst = rst_bad = 0
    prev_rst = -1
    i = d.find(b"\xff")
    while 0 <= i < len(d) - 1:
        ffs += 1
        nxt = d[i + 1]
        if 0xD0 <= nxt <= 0xD7:
            rst += 1
            if prev_rst >= 0 and (nxt - 0xD0) != (prev_rst + 1) % 8:
                rst_bad += 1
            prev_rst = nxt - 0xD0
        elif nxt not in (0x00, 0xFF, 0xD9):
            viol += 1
        i = d.find(b"\xff", i + 1)
    return viol, ffs, rst, rst_bad


# C_struct is evaluated on a candidate that signature carving already header-matched, so
# "starts with the right magic" is nearly guaranteed under both hypotheses and must carry
# almost no weight (p0 close to p1). The discriminating evidence is internal consistency:
# escape rules, restart cycles, cross-reference targets, central-directory pointers.
_P_HEADER = (0.999, 0.9)     # weak: implied by the carver
_P_FATAL = (0.99, 0.01)      # decisive: a violation means bytes are missing or reordered


def _jpeg_tests(d: bytes) -> list:
    t = [(d[:3] == b"\xff\xd8\xff", *_P_HEADER)]
    # Walk marker segments to SOS.
    pos, ok, sos = 2, False, -1
    for _ in range(64):
        if pos + 4 > len(d) or d[pos] != 0xFF:
            break
        marker = d[pos + 1]
        if marker == 0xDA:
            ok, sos = True, pos
            break
        seg_len = int.from_bytes(d[pos + 2:pos + 4], "big")
        if seg_len < 2:
            break
        pos += 2 + seg_len
    t.append((ok, 0.99, 0.5))
    if ok:
        sos_len = int.from_bytes(d[sos + 2:sos + 4], "big")
        scan = d[sos + 2 + sos_len:]
        viol, ffs, rst, rst_bad = _jpeg_scan_stats(scan)
        # Weighted by observation count: every violation is independent evidence of damage,
        # and every intact restart cycle is independent evidence of integrity.
        if viol:
            t.append((False, *_P_FATAL, min(viol, 12)))          # 0xFF escape rule
        elif ffs:
            t.append((True, 0.98, 0.1, min(ffs // 200 + 1, 6)))
        if rst >= 3:
            if rst_bad:
                t.append((False, *_P_FATAL, min(rst_bad, 12)))   # RSTn must cycle 0..7
            else:
                t.append((True, 0.99, 0.15, min(rst // 8 + 1, 6)))
    t.append((d.rstrip(b"\0").endswith(b"\xff\xd9"), 0.98, 0.3))
    return t


def _pdf_tests(d: bytes) -> list:
    t = [(d.startswith(b"%PDF-"), *_P_HEADER)]
    n_obj, n_endobj = d.count(b" obj"), d.count(b"endobj")
    n_str, n_endstr = d.count(b"stream"), d.count(b"endstream")
    t.append((n_obj == n_endobj, 0.95, 0.2))
    t.append((n_str == 2 * n_endstr if n_endstr else None, 0.95, 0.2))
    nums = [int(m.group(1)) for m in _OBJ_RE.finditer(d)]
    t.append((len(nums) == len(set(nums)) if nums else None, 0.98, 0.3))
    sx = d.rfind(b"startxref")
    if sx >= 0:
        m = re.match(rb"\s*(\d+)", d[sx + 9:sx + 32])
        off = int(m.group(1)) if m else -1
        target = d[off:off + 32] if 0 <= off < len(d) else b""
        t.append((target.startswith(b"xref") or bool(_OBJ_RE.match(target)), *_P_FATAL))  # /XRef target
    else:
        t.append((False, *_P_FATAL))
    t.append((b"%%EOF" in d[-64:].rstrip(b"\0") or d.rstrip(b"\0").endswith(b"%%EOF"), 0.98, 0.1))
    return t


def _zip_tests(d: bytes) -> list:
    t = [(d.startswith(b"PK\x03\x04"), *_P_HEADER)]
    pos, hops, good = 0, 0, 0
    while d[pos:pos + 4] == b"PK\x03\x04" and pos + 30 <= len(d) and hops < 10_000:
        csize = int.from_bytes(d[pos + 18:pos + 22], "little")
        nlen = int.from_bytes(d[pos + 26:pos + 28], "little")
        elen = int.from_bytes(d[pos + 28:pos + 30], "little")
        pos += 30 + nlen + elen + csize
        hops += 1
        good += d[pos:pos + 2] == b"PK"
    t.append((good == hops if hops else None, 0.99, 0.05, min(max(hops, 1), 8)))
    eocd = d.rfind(b"PK\x05\x06")
    if eocd >= 0 and eocd + 22 <= len(d):
        cd_off = int.from_bytes(d[eocd + 16:eocd + 20], "little")
        t.append((d[cd_off:cd_off + 4] == b"PK\x01\x02", *_P_FATAL))
    else:
        t.append((False, *_P_FATAL))
    return t


def validate_structural_coherence(data: bytes, mime: str) -> float:
    """C_struct in [0, 1]: SHT posterior that `data` is a structurally valid `mime` file."""
    if mime == "image/jpeg":
        tests = _jpeg_tests(data)
    elif mime == "application/pdf":
        tests = _pdf_tests(data)
    elif mime == "application/zip":
        tests = _zip_tests(data)
    else:  # unknown container: only entropy sanity
        h = calculate_shannon_entropy(data)
        tests = [(0.5 < h < 7.999, 0.9, 0.5)]
    return sht_posterior(tests)


# --------------------------------------------------------------------------- #
# Baseline JPEG scan decoder: counts MCUs in a restart interval (exact boundary test)
# --------------------------------------------------------------------------- #
class JpegContext:
    """Huffman tables, component layout and restart interval parsed from a JPEG header block.

    Lets the pairwise test decode the restart interval that straddles an A|B boundary:
    a true boundary decodes to exactly `dri` MCUs and ends cleanly at the next marker.
    Baseline (SOF0/SOF1) only; progressive returns None from `parse`.
    """

    def __init__(self, huff: dict, comps: list, dri: int, sos_tables: dict, scan_start: int):
        self.huff, self.comps, self.dri, self.sos_tables, self.scan_start = huff, comps, dri, sos_tables, scan_start
        # blocks per MCU per component, in scan order
        if len(comps) == 1:
            self.mcu_layout = [(comps[0][0], 1)]
        else:
            self.mcu_layout = [(cid, h * v) for cid, h, v in comps]

    @classmethod
    def parse(cls, d: bytes) -> "JpegContext | None":
        if d[:2] != b"\xff\xd8":
            return None
        huff, comps, dri, sos_tables, pos = {}, [], 0, {}, 2
        while pos + 4 <= len(d) and d[pos] == 0xFF:
            marker, seg_len = d[pos + 1], int.from_bytes(d[pos + 2:pos + 4], "big")
            seg = d[pos + 4:pos + 2 + seg_len]
            if marker in (0xC0, 0xC1):                       # SOF0/1 baseline
                for k in range(seg[5]):
                    cid, hv = seg[6 + 3 * k], seg[7 + 3 * k]
                    comps.append((cid, hv >> 4, hv & 15))
            elif marker == 0xC2 or (0xC3 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC)):
                return None                                    # progressive / lossless: unsupported
            elif marker == 0xC4:                               # DHT (may hold several tables)
                q = 0
                while q < len(seg):
                    tc, th = seg[q] >> 4, seg[q] & 15
                    counts = seg[q + 1:q + 17]
                    syms = seg[q + 17:q + 17 + sum(counts)]
                    table, code, si = {}, 0, 0
                    for ln in range(1, 17):
                        for _ in range(counts[ln - 1]):
                            table[(ln, code)] = syms[si]
                            code += 1
                            si += 1
                        code <<= 1
                    huff[(tc, th)] = table
                    q += 17 + sum(counts)
            elif marker == 0xDD:                               # DRI
                dri = int.from_bytes(seg[:2], "big")
            elif marker == 0xDA:                               # SOS
                for k in range(seg[0]):
                    cid, tt = seg[1 + 2 * k], seg[2 + 2 * k]
                    sos_tables[cid] = (tt >> 4, tt & 15)
                pos += 2 + seg_len
                break
            pos += 2 + seg_len
        else:
            return None
        if not comps or not huff or not sos_tables or dri == 0:
            return None
        return cls(huff, comps, dri, sos_tables, pos)

    def count_mcus(self, data: bytes) -> tuple[int, bool]:
        """Decode entropy-coded `data` (no markers inside). Returns (complete_mcus, clean_end)."""
        # unstuff FF00 -> FF, and stop at any real marker
        buf = bytearray()
        i = 0
        while i < len(data):
            c = data[i]
            if c == 0xFF:
                if i + 1 < len(data) and data[i + 1] == 0x00:
                    buf.append(0xFF)
                    i += 2
                    continue
                break
            buf.append(c)
            i += 1
        nbits = len(buf) * 8
        bitpos = 0

        def read_bit():
            nonlocal bitpos
            if bitpos >= nbits:
                raise EOFError
            v = (buf[bitpos >> 3] >> (7 - (bitpos & 7))) & 1
            bitpos += 1
            return v

        def read_bits(n):
            v = 0
            for _ in range(n):
                v = (v << 1) | read_bit()
            return v

        def decode_sym(table):
            code, ln = 0, 0
            while ln < 16:
                code = (code << 1) | read_bit()
                ln += 1
                s = table.get((ln, code))
                if s is not None:
                    return s
            raise ValueError("bad huffman code")

        def decode_block(dc_t, ac_t):
            t = decode_sym(dc_t)
            if t > 11:
                raise ValueError("bad DC size")
            read_bits(t)
            k = 1
            while k < 64:
                rs = decode_sym(ac_t)
                r, s = rs >> 4, rs & 15
                if s == 0:
                    if r == 15:
                        k += 16
                        continue
                    break
                k += r
                if k > 63:
                    raise ValueError("AC overrun")
                read_bits(s)
                k += 1

        mcus = 0
        try:
            while bitpos < nbits:
                start = bitpos
                # A trailing run of 1-bits shorter than a byte is padding, not an MCU.
                if nbits - bitpos < 8 and all(read_bit() == 1 for _ in range(nbits - bitpos)):
                    return mcus, True
                bitpos = start
                for cid, nblk in self.mcu_layout:
                    dc_id, ac_id = self.sos_tables[cid]
                    for _ in range(nblk):
                        decode_block(self.huff[(0, dc_id)], self.huff[(1, ac_id)])
                mcus += 1
                if mcus > self.dri:
                    return mcus, False
        except (EOFError, ValueError, KeyError):
            return mcus, False
        return mcus, True

    def boundary_ok(self, ia: "_FragInfo", ib: "_FragInfo") -> bool | None:
        """Decode the restart interval spanning the A|B join, using cached per-fragment
        marker positions. Returns None when the pair carries no decodable interval."""
        if ia.soi and not ia.rst:
            tail = ia.raw[self.scan_start:]          # first interval starts right after SOS
        elif ia.rst:
            tail = ia.tail_seg
        else:
            return None
        if ib.rst and (ib.eoi < 0 or ib.rst[0] < ib.eoi):
            n, clean = self.count_mcus(tail + ib.raw[:ib.rst[0]])
            return clean and n == self.dri
        if ib.eoi >= 0:                              # last interval before EOI may be short
            n, clean = self.count_mcus(tail + ib.raw[:ib.eoi])
            return clean and 0 < n <= self.dri
        return None

    # Interval-length plausibility: complete RST-to-RST intervals observed inside the pool's
    # blocks give this file's length range. A boundary-spanning interval outside it is implausible.
    lo: int = 0
    hi: int = 0
    p0_len: float = 0.9  # P(pass | not adjacent) = range width / (2 * median); tight range -> strong test

    def fit_interval_lengths(self, infos: list["_FragInfo"]) -> None:
        lens = []
        for fi in infos:
            lens += [b - a for a, b in zip(fi.rst, fi.rst[1:])]
        if len(lens) < 8:
            return
        arr = np.array(lens)
        lo, hi = np.percentile(arr, 1), np.percentile(arr, 99)
        pad = 0.1 * (hi - lo) + 4
        self.lo, self.hi = int(lo - pad), int(hi + pad)
        self.p0_len = float(min(0.9, max(0.05, (self.hi - self.lo) / (2 * np.median(arr)))))

    def length_plausible(self, ia: "_FragInfo", ib: "_FragInfo") -> bool | None:
        if self.hi <= 0 or not ia.rst or not ib.rst:
            return None
        if 0 <= ib.eoi < ib.rst[0]:
            return None                                  # final (possibly short) interval: no evidence
        return self.lo <= len(ia.tail_seg) + 2 + ib.rst[0] <= self.hi


class PdfContext:
    """Cross-reference table (FR2.1: '/XRef validity') used as an absolute position oracle.

    The xref table lists the byte offset of every indirect object. An object found at
    internal offset `o` inside a fragment therefore pins that fragment's absolute start
    to `xref[n] - o`, which on a block-aligned image must be a multiple of block_size.
    Deterministic, and it needs no bytes beyond those present in the fragments.
    """

    def __init__(self, offsets: dict[int, int], block_size: int = BLOCK_SIZE):
        self.offsets, self.block_size = offsets, block_size

    @classmethod
    def parse(cls, fragments: list[bytes], block_size: int = BLOCK_SIZE) -> "PdfContext | None":
        for f in fragments:
            i = f.find(b"xref\n")
            if i < 0:
                i = f.find(b"xref\r\n")
            if i < 0 or not re.match(rb"xref\s+\d+\s+\d+", f[i:i + 32]):
                continue
            m = re.match(rb"xref\s+(\d+)\s+(\d+)\s*", f[i:i + 40])
            first, count = int(m.group(1)), int(m.group(2))
            body = f[i + m.end():]
            offsets = {}
            for k, em in enumerate(re.finditer(rb"(\d{10}) (\d{5}) ([nf])[ \r\n]{0,2}", body[:20 * count])):
                if em.group(3) == b"n":
                    offsets[first + k] = int(em.group(1))
            if len(offsets) >= 4:
                return cls(offsets, block_size)
        return None

    def pin(self, frag: bytes) -> int | None:
        """Absolute block index of `frag`, or None when the xref gives no consistent answer."""
        votes: dict[int, int] = {}
        for m in _OBJ_RE.finditer(frag):
            off = self.offsets.get(int(m.group(1)))
            if off is None:
                continue
            start = off - m.start()
            if start >= 0 and start % self.block_size == 0:
                votes[start // self.block_size] = votes.get(start // self.block_size, 0) + 1
        if not votes:
            return None
        best, n = max(votes.items(), key=lambda kv: kv[1])
        return best if n >= 2 or len(votes) == 1 else None


class _FragInfo:
    """Per-fragment markers, windows and entropies, computed once instead of per pair.

    The pairwise SHT is O(N^2); anything that depends on one fragment alone belongs here.
    """
    __slots__ = ("raw", "rst", "tail_seg", "eoi", "soi", "header", "ends_footer", "ends_ff",
                 "ends_zeros", "ent_tail", "ent_head", "objs", "open_stream", "first_endstream",
                 "first_obj_at", "zip_next", "pin")

    def __init__(self, f: bytes):
        self.raw = f
        self.rst = [i for i in range(len(f) - 1) if f[i] == 0xFF and 0xD0 <= f[i + 1] <= 0xD7]
        self.tail_seg = f[self.rst[-1] + 2:] if self.rst else b""
        self.eoi = f.find(b"\xff\xd9")
        self.soi = f[:2] == b"\xff\xd8"
        self.header = detect_header(f)
        stripped = f.rstrip(b"\0")
        self.ends_footer = any(stripped.endswith(foot) for _, foot in SIGNATURES.values())
        self.ends_ff = f[-1:] == b"\xff"
        self.ends_zeros = f.endswith(b"\0" * 64)
        self.ent_tail = calculate_shannon_entropy(f[-WINDOW:])
        self.ent_head = calculate_shannon_entropy(f[:WINDOW])
        self.objs = [int(m.group(1)) for m in _OBJ_RE.finditer(f)]
        self.first_obj_at = f.find(b" obj")
        last_stream, last_end = f.rfind(b"stream"), f.rfind(b"endstream")
        self.open_stream = last_stream > last_end
        self.first_endstream = f.find(b"endstream")
        self.zip_next = -1
        pos = f.rfind(b"PK\x03\x04")
        if pos >= 0 and pos + 30 <= len(f):
            csize = int.from_bytes(f[pos + 18:pos + 22], "little")
            nlen = int.from_bytes(f[pos + 26:pos + 28], "little")
            elen = int.from_bytes(f[pos + 28:pos + 30], "little")
            self.zip_next = pos + 30 + nlen + elen + csize - len(f)
        self.pin: int | None = None


def build_pool_context(fragments: list[bytes]) -> dict:
    """Parse the pool once: per-fragment info, JPEG header contexts, PDF xref pins."""
    infos = {id(f): _FragInfo(f) for f in fragments}
    ctx: dict = {"info": infos, "jpeg": []}
    uniq = list(infos.values())
    for fi in uniq:
        if fi.raw[:3] == b"\xff\xd8\xff":
            jc = JpegContext.parse(fi.raw)
            if jc:
                jc.fit_interval_lengths(uniq)
                ctx["jpeg"].append(jc)
    pdf = PdfContext.parse(fragments)
    if pdf:
        ctx["pdf"] = pdf
        for fi in uniq:
            fi.pin = pdf.pin(fi.raw)
    return ctx


# --------------------------------------------------------------------------- #
# Pairwise SHT adjacency  (SHT_ij for the affinity matrix)
# --------------------------------------------------------------------------- #
def _rst_seq(b: bytes) -> list[int]:
    return [b[i + 1] - 0xD0 for i in range(len(b) - 1) if b[i] == 0xFF and 0xD0 <= b[i + 1] <= 0xD7]


def sht_pair_affinity(a: bytes, b: bytes, mime: str | None = None, ctx: dict | None = None) -> float:
    """P(B directly follows A) from deterministic structure only. mime=None runs every
    format's tests; tests whose markers are absent from both blocks stay neutral.
    ctx: output of build_pool_context (enables exact JPEG interval decoding)."""
    cache = (ctx or {}).get("info") or {}
    ia = cache.get(id(a)) or _FragInfo(a)
    ib = cache.get(id(b)) or _FragInfo(b)
    t: list = []
    # Generic boundary tests
    t.append((ib.header is None, 0.999, 0.7))                    # a file start has no predecessor
    t.append((not ia.ends_footer, 0.999, 0.7))                   # a file end has no successor
    t.append((abs(ia.ent_tail - ib.ent_head) < 1.0, 0.9, 0.45))
    if ia.ends_zeros:
        t.append((b[0] == 0 or ib.ent_head < 1.0, 0.8, 0.3))     # slack run continues or the file ended

    mimes = [mime] if mime else list(SIGNATURES)
    if "image/jpeg" in mimes:
        if ia.rst and ib.rst:
            ra_last = a[ia.rst[-1] + 1] - 0xD0
            rb_first = b[ib.rst[0] + 1] - 0xD0
            split = [b[0] - 0xD0] if ia.ends_ff and 0xD0 <= b[0] <= 0xD7 else []
            seq = [ra_last] + split + [rb_first]
            t.append((all((y - x) % 8 == 1 for x, y in zip(seq, seq[1:])), 0.98, 0.125))  # RSTn continues mod 8
        if ia.ends_ff:
            t.append((b[0] in (0x00, 0xD9, 0xFF) or 0xD0 <= b[0] <= 0xD7, 0.99, 0.1))
        for jc in (ctx or {}).get("jpeg", []):
            ok = jc.boundary_ok(ia, ib)
            if ok is not None:
                t.append((ok, 0.99, 0.25))                              # interval decodes to exactly DRI MCUs
                t.append((jc.length_plausible(ia, ib), 0.98, jc.p0_len))  # and has a plausible byte length
                break
    if "application/pdf" in mimes:
        if ia.pin is not None and ib.pin is not None:
            t.append((ib.pin == ia.pin + 1, 0.99, 0.01))     # xref pins both fragments: exact adjacency
        if ia.objs and ib.objs:
            t.append((ib.objs[0] == ia.objs[-1] + 1, 0.85, 0.05))         # next object number
            t.append((ib.objs[0] > ia.objs[-1], 0.97, 0.5))
        # inside an unterminated stream, the successor must not open a new object first
        if ia.open_stream and ib.objs:
            t.append((ib.first_endstream >= 0 and ib.first_obj_at > ib.first_endstream, 0.95, 0.2))
    if "application/zip" in mimes and 0 <= ia.zip_next < len(b) - 2:
        t.append((b[ia.zip_next:ia.zip_next + 2] == b"PK", 0.98, 0.01))   # local-header chain lands in B
    return sht_posterior(t)


# --------------------------------------------------------------------------- #
# Siamese adjacency network
# --------------------------------------------------------------------------- #
def _torch():
    import torch
    import torch.nn as nn
    return torch, nn


class _SiameseFactory:
    _cls = None

    @classmethod
    def get(cls):
        if cls._cls is None:
            torch, nn = _torch()

            class SiameseAdjacencyNet(nn.Module):
                """Shared trunk; inputs (B,1,256) floats in [0,1]. Returns (prob, emb_a, emb_b)."""

                def __init__(self, emb: int = 64):
                    super().__init__()
                    self.trunk = nn.Sequential(
                        nn.Conv1d(1, 16, 5, stride=2), nn.ReLU(inplace=True),    # 126
                        nn.Conv1d(16, 32, 5, stride=2), nn.ReLU(inplace=True),   # 61
                        nn.MaxPool1d(4),                                          # 15
                        nn.Flatten(), nn.Linear(32 * 15, emb),
                    )
                    self.scale = nn.Parameter(torch.tensor(5.0))
                    self.bias = nn.Parameter(torch.tensor(0.0))

                def embed(self, x):
                    return torch.nn.functional.normalize(self.trunk(x), dim=1)

                def forward(self, tail, head):
                    ea, eb = self.embed(tail), self.embed(head)
                    cos = (ea * eb).sum(1)
                    return torch.sigmoid(self.scale * cos + self.bias), ea, eb

            cls._cls = SiameseAdjacencyNet
        return cls._cls


def SiameseAdjacencyNet(*a, **kw):  # noqa: N802
    return _SiameseFactory.get()(*a, **kw)


def build_pair_dataset(corpus: SyntheticFragmentCorpus, n_pairs: int = 12_000):
    """(tail_a, head_b, y): y=1 adjacent; y=0 other-file or same-file-non-adjacent block."""
    rng = corpus.rng
    tails = np.empty((n_pairs, WINDOW), np.uint8)
    heads = np.empty((n_pairs, WINDOW), np.uint8)
    y = np.empty(n_pairs, np.float32)
    for k in range(n_pairs):
        t = FILE_TYPES[rng.integers(len(FILE_TYPES))]
        a, p = corpus._pick_adjacent(t)
        r = rng.random()
        if r < 0.5:
            b, lab = p, 1.0
        elif r < 0.75:
            b, lab = corpus._pick_any(t), 0.0       # hard negative: same file type
        else:
            other = FILE_TYPES[(FILE_TYPES.index(t) + int(rng.integers(1, len(FILE_TYPES)))) % len(FILE_TYPES)]
            b, lab = corpus._pick_any(other), 0.0
        a, b = corpus.degrade(a), corpus.degrade(b)
        tails[k], heads[k], y[k] = a[-WINDOW:], b[:WINDOW], lab
    return tails, heads, y


def train_siamese(corpus: SyntheticFragmentCorpus, epochs: int = 5, batch_size: int = 128, lr: float = 1e-3):
    torch, nn = _torch()
    torch.manual_seed(0)
    ta, hb, y = build_pair_dataset(corpus)
    n_val = len(y) // 8
    xt = torch.from_numpy(ta).float().div_(255).unsqueeze(1)
    xh = torch.from_numpy(hb).float().div_(255).unsqueeze(1)
    yt = torch.from_numpy(y)
    model = SiameseAdjacencyNet()
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    bce = nn.BCELoss()
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(len(y) - n_val) + n_val
        tot = 0.0
        for i in range(0, len(perm), batch_size):
            idx = perm[i:i + batch_size]
            opt.zero_grad()
            p, _, _ = model(xt[idx], xh[idx])
            loss = bce(p, yt[idx])
            loss.backward()
            opt.step()
            tot += loss.item() * len(idx)
        model.eval()
        with torch.no_grad():
            p, _, _ = model(xt[:n_val], xh[:n_val])
            acc = ((p > 0.5).float() == yt[:n_val]).float().mean().item()
        log.info("siamese epoch %d/%d loss=%.4f val_acc=%.3f", ep + 1, epochs, tot / len(perm), acc)
    model.eval()
    return model


def export_siamese_onnx(model, export_path: str = SIAMESE_MODEL_PATH) -> str:
    torch, _ = _torch()
    import onnx
    Path(export_path).parent.mkdir(parents=True, exist_ok=True)
    dummy = torch.zeros(1, 1, WINDOW)
    torch.onnx.export(model, (dummy, dummy), export_path, input_names=["tail", "head"],
                      output_names=["prob", "emb_tail", "emb_head"],
                      dynamic_axes={k: {0: "batch"} for k in ("tail", "head", "prob", "emb_tail", "emb_head")},
                      opset_version=17, dynamo=False)
    m = onnx.load(export_path)  # stash scale/bias so the runtime can score NxN from embeddings
    for k, v in (("scale", model.scale.item()), ("bias", model.bias.item())):
        m.metadata_props.add(key=k, value=repr(v))
    onnx.save(m, export_path)
    log.info("exported %s (%d KB)", export_path, os.path.getsize(export_path) // 1024)
    return export_path


class SiameseAdjacency:
    """ORT runtime. N blocks -> one batched pass for embeddings -> NxN P_adjacent via cosine."""

    def __init__(self, model_path: str = SIAMESE_MODEL_PATH, intra_op_threads: int = 4):
        import onnxruntime as ort
        so = ort.SessionOptions()
        so.intra_op_num_threads = intra_op_threads
        so.log_severity_level = 3
        self.providers = get_optimal_execution_providers()
        self.session = ort.InferenceSession(model_path, so, providers=self.providers)
        meta = self.session.get_modelmeta().custom_metadata_map
        self.scale, self.bias = float(meta["scale"]), float(meta["bias"])

    @staticmethod
    def _windows(blocks: list[bytes]) -> tuple[np.ndarray, np.ndarray]:
        n = len(blocks)
        tails = np.zeros((n, 1, WINDOW), np.float32)
        heads = np.zeros((n, 1, WINDOW), np.float32)
        for i, blk in enumerate(blocks):
            t = np.frombuffer(blk[-WINDOW:], np.uint8)
            h = np.frombuffer(blk[:WINDOW], np.uint8)
            tails[i, 0, WINDOW - len(t):] = t / 255.0
            heads[i, 0, :len(h)] = h / 255.0
        return tails, heads

    def affinity_matrix(self, blocks: list[bytes]) -> np.ndarray:
        """M[i, j] = P(block j directly follows block i). Diagonal is 0."""
        tails, heads = self._windows(blocks)
        _, et, eh = self.session.run(None, {"tail": tails, "head": heads})
        cos = et @ eh.T
        m = 1.0 / (1.0 + np.exp(-(self.scale * cos + self.bias)))
        np.fill_diagonal(m, 0.0)
        return m.astype(np.float32)

    def predict_pair(self, a: bytes, b: bytes) -> float:
        tails, heads = self._windows([a, b])
        p, _, _ = self.session.run(None, {"tail": tails[:1], "head": heads[1:2]})
        return float(p[0])


def ensure_siamese_model(path: str = SIAMESE_MODEL_PATH, seed: int = 11) -> str:
    if not os.path.exists(path):
        export_siamese_onnx(train_siamese(SyntheticFragmentCorpus(seed=seed)), path)
    return path


if __name__ == "__main__":
    from engine.pretrain_utils import _make_jpeg, _make_pdf, _make_zip

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    rng = np.random.default_rng(5)

    # A real encoder's output is the only fair C_struct target: the Node 01 synthetic JPEG/PDF
    # have no Huffman stream and no valid xref, so both valid and corrupted score ~1.0 there.
    import io as _io

    from PIL import Image as _Image
    _buf = _io.BytesIO()
    _Image.fromarray(rng.integers(0, 256, (320, 320, 3), dtype=np.uint8)).save(
        _buf, "JPEG", quality=85, restart_marker_blocks=4)
    real_jpeg = _buf.getvalue()

    for name, good, mime in (("jpeg(real)", real_jpeg, "image/jpeg"),
                             ("zip", _make_zip(rng, 40_000), "application/zip")):
        cut = len(good) // 2
        bad = good[:cut] + good[cut + 2048:]        # drop 2KB from the middle
        cg, cb = validate_structural_coherence(good, mime), validate_structural_coherence(bad, mime)
        print(f"{name}: C_struct valid={cg:.3f} corrupted={cb:.3f}")
        assert cg > 0.9 > cb, (name, cg, cb)
    # pairwise: adjacent blocks of a pdf beat a shuffled pair
    blocks = SyntheticFragmentCorpus.blockify(_make_pdf(rng, 60_000))
    adj = sht_pair_affinity(blocks[2].tobytes(), blocks[3].tobytes())
    non = sht_pair_affinity(blocks[2].tobytes(), blocks[7].tobytes())
    print(f"pdf SHT adjacent={adj:.3f} non-adjacent={non:.3f}")
    assert adj > non

    ensure_siamese_model()
    sia = SiameseAdjacency()
    print("providers:", sia.providers)
    m = sia.affinity_matrix([b.tobytes() for b in blocks[:6]])
    assert m.shape == (6, 6) and (m.diagonal() == 0).all() and m.min() >= 0 and m.max() <= 1
    p_adj = sia.predict_pair(blocks[2].tobytes(), blocks[3].tobytes())
    print(f"siamese P_adjacent(2->3)={p_adj:.3f}  row2={np.round(m[2], 2)}")
    print("OK carver_ml")

"""Phase 2 (FR2.0): deterministic signature-based carving over 4KB blocks.

Finds file-start blocks by magic bytes at block offset 0, walks forward while
the stream stays plausibly contiguous, and closes the stream at the first block
containing the footer. Anything it cannot close is handed back as an *open*
stream plus a pool of orphan blocks for FR2.1-FR2.3.

All output is block indices. No bytes are synthesised anywhere.
"""
from __future__ import annotations

import mmap
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator

import numpy as np

from engine.pretrain_utils import BLOCK_SIZE

# mime -> (list of header magics at offset 0, footer magic searched anywhere in block)
SIGNATURES: dict[str, tuple[list[bytes], bytes]] = {
    "image/jpeg": ([b"\xff\xd8\xff"], b"\xff\xd9"),
    "application/pdf": ([b"%PDF-"], b"%%EOF"),
    "application/zip": ([b"PK\x03\x04"], b"PK\x05\x06"),  # covers DOCX/XLSX/PPTX/JAR
}


@dataclass
class Stream:
    mime: str
    blocks: list[int]          # block indices in carved order
    closed: bool               # footer found -> complete contiguous file
    footer_offset: int = -1    # byte offset of footer end inside last block (closed only)
    header_offset: int = 0     # byte offset of header start inside first block (default 0)

    def assemble(self, image: np.ndarray) -> bytes:
        """Concatenate source bytes only; trims trailing slack after the footer and sector offset before header."""
        raw = b"".join(image[i].tobytes() for i in self.blocks)
        if self.closed and self.footer_offset > 0:
            raw = raw[: (len(self.blocks) - 1) * BLOCK_SIZE + self.footer_offset]
        if self.header_offset > 0:
            raw = raw[self.header_offset:]
        return raw


@dataclass
class CarveResult:
    streams: list[Stream] = field(default_factory=list)
    orphans: list[int] = field(default_factory=list)   # candidate blocks for ML reassembly
    header_blocks: dict[int, str] = field(default_factory=dict)  # idx -> mime
    footer_blocks: dict[int, str] = field(default_factory=dict)
    header_offsets: dict[int, int] = field(default_factory=dict) # idx -> byte offset in block


def detect_header(block: bytes | np.ndarray) -> str | None:
    b = block.tobytes() if isinstance(block, np.ndarray) else block
    for mime, (heads, _) in SIGNATURES.items():
        if any(b.startswith(h) for h in heads):
            return mime
    return None


def detect_header_offset(block: bytes | np.ndarray, sector_size: int = 512) -> tuple[str, int] | None:
    """Byte-accurate detection for 512-byte sector-aligned or block-aligned file headers.
    Returns (mime, offset_in_block) or None. Prioritizes offset 0.
    """
    b = block.tobytes() if isinstance(block, np.ndarray) else block
    for mime, (heads, _) in SIGNATURES.items():
        if any(b.startswith(h) for h in heads):
            return mime, 0
    for off in range(sector_size, len(b), sector_size):
        sub = b[off:]
        for mime, (heads, _) in SIGNATURES.items():
            if any(sub.startswith(h) for h in heads):
                return mime, off
    return None


def find_footer(block: bytes | np.ndarray, mime: str) -> int:
    """Byte offset just past the footer inside `block`, or -1."""
    b = block.tobytes() if isinstance(block, np.ndarray) else block
    foot = SIGNATURES[mime][1]
    pos = b.rfind(foot)
    if pos < 0:
        return -1
    end = pos + len(foot)
    if mime == "application/zip":  # EOCD record is 22 bytes + optional comment (len at +20)
        comment_len = int.from_bytes(b[pos + 20:pos + 22], "little") if pos + 22 <= len(b) else 0
        end = min(pos + 22 + comment_len, len(b))
    elif mime == "application/pdf":  # %%EOF is usually followed by \r\n or \n
        while end < len(b) and b[end:end + 1] in (b"\r", b"\n"):
            end += 1
    return end


def _continuity_ok(prev: bytes, nxt: bytes, mime: str, threshold: float) -> bool:
    """Would `nxt` plausibly follow `prev` inside a `mime` stream?

    Whole-stream C_struct cannot catch a swallowed foreign sector: for JPEG the
    injected bytes just look like more entropy-coded scan data (measured
    C_struct = 1.0000 on a stream with 12 KB of foreign filler), and for PDF the
    obj/endobj counts still balance (measured 0.8901, over the 0.85 gate). Both
    were emitted as valid, tying the naive header->footer baseline exactly.

    Checking adjacency at carve time instead stops the stream at the contamination
    boundary, so the real blocks reach the orphan pool where reassembly can
    reorder them. Uses the same pairwise primitive the reassembler already relies on.

    DEFAULT OFF (min_continuity=0.0) — measured, not assumed. On the `fragmented`
    benchmark cell sht_pair_affinity does not separate the two populations:
        true adjacencies     n=27  mean 0.8285  range 0.2702 .. 0.9984
        contamination bounds n=6   mean 0.4478  range 0.2702 .. 0.8029
    The ranges overlap, so no threshold exists. The cause is that the posterior
    collapses to a few discrete levels: sht_pair_affinity has JPEG-specific
    pairwise tests but none for PDF or ZIP, so those fall back to the generic
    entropy/header/footer tests and every PDF boundary — real or contaminated —
    returns the same 0.8029. Adding format-specific pairwise continuity tests for
    PDF and ZIP is the prerequisite for turning this gate on; see bench/matrix.py.
    """
    if threshold <= 0.0:
        return True
    try:
        from engine.carver_ml import sht_pair_affinity
        return sht_pair_affinity(prev, nxt, mime) >= threshold
    except Exception:
        return True          # never let the gate turn a recoverable stream into a crash


def carve(image: np.ndarray, noise_mask: np.ndarray | None = None,
          max_stream_blocks: int = 1 << 16, min_continuity: float = 0.0) -> CarveResult:
    """image: (N, 4096) uint8. noise_mask: optional bool[N] from FastBlockTriage (True = skip).

    Contiguity heuristic: a stream stays open while the next block is not a
    header of any foreign type and (if provided) not flagged as noise. It closes on the
    valid footer. Streams that hit a foreign header/noise/end-of-image before the footer are
    returned open; their blocks and every unclaimed non-noise block become orphans.
    """
    n = len(image)
    noise = noise_mask if noise_mask is not None else np.zeros(n, dtype=bool)
    res = CarveResult()
    for i in range(n):
        if noise[i]:
            continue
        hdr = detect_header_offset(image[i])
        if hdr:
            mime, off = hdr
            res.header_blocks[i] = mime
            res.header_offsets[i] = off
        for mime in SIGNATURES:
            if find_footer(image[i], mime) >= 0:
                res.footer_blocks.setdefault(i, mime)

    claimed = np.zeros(n, dtype=bool)
    for start, mime in sorted(res.header_blocks.items()):
        if claimed[start]:
            continue
        blocks = [start]
        closed, foff = False, -1
        j = start
        has_sos = (mime != "image/jpeg")
        while len(blocks) <= max_stream_blocks:
            blk_bytes = image[j].tobytes()
            if mime == "image/jpeg" and not has_sos:
                if b"\xff\xda" in blk_bytes:
                    has_sos = True

            foff = -1
            if has_sos:
                foff = find_footer(blk_bytes, mime)
                if mime == "image/jpeg" and foff >= 0:
                    sos_pos = blk_bytes.rfind(b"\xff\xda")
                    if sos_pos >= 0 and foff <= sos_pos + 2:
                        foff = -1

            if foff >= 0 and not (j == start and foff < len(SIGNATURES[mime][0][0]) + 4):
                closed = True
                break
            j += 1
            # Stop if next block is out of bounds, noise, claimed, or a header of another file type.
            # For application/zip, internal file entries also start with PK\x03\x04, so only abort
            # if encountering a foreign header (e.g. PDF/JPEG).
            is_foreign_header = (
                j in res.header_blocks
                and (mime != "application/zip" or res.header_blocks[j] != "application/zip")
            )
            if j >= n or noise[j] or is_foreign_header or claimed[j]:
                break
            if not _continuity_ok(image[blocks[-1]].tobytes(), image[j].tobytes(), mime, min_continuity):
                break          # contamination boundary: leave open, blocks fall through to orphans
            blocks.append(j)
        hoff = res.header_offsets.get(start, 0)
        stream = Stream(mime, blocks, closed, foff if closed else -1, header_offset=hoff)
        res.streams.append(stream)
        if closed:
            claimed[blocks] = True

    res.orphans = [i for i in range(n) if not claimed[i] and not noise[i]]
    return res


class ImageBlocks:
    """Read-only block accessor over a memory-mapped image.

    Indexing returns a *copy*, never a view. A numpy view over an mmap exports a buffer
    pointer, and `mmap.close()` then raises BufferError ("cannot close exported pointers
    exist") for as long as any caller holds it, which leaves the file handle open and is
    exactly the disk-IO deadlock the engine must avoid. Copying one 4KB block at a time
    keeps peak memory flat on a multi-terabyte image and lets close() always succeed.
    """

    def __init__(self, mm: mmap.mmap, block_size: int = BLOCK_SIZE):
        self._mm = mm
        self.block_size = block_size
        self.n_blocks = len(mm) // block_size

    def __len__(self) -> int:
        return self.n_blocks

    @property
    def shape(self) -> tuple[int, int]:
        return (self.n_blocks, self.block_size)

    def raw(self, i: int) -> bytes:
        if not 0 <= i < self.n_blocks:
            raise IndexError(i)
        off = i * self.block_size
        return self._mm[off:off + self.block_size]

    def __getitem__(self, i: int) -> np.ndarray:
        return np.frombuffer(self.raw(i), dtype=np.uint8)

    def batch(self, start: int, count: int) -> np.ndarray:
        """(count, block_size) uint8 copy; the unit the triage/affinity paths consume."""
        stop = min(start + count, self.n_blocks)
        buf = self._mm[start * self.block_size: stop * self.block_size]
        return np.frombuffer(buf, dtype=np.uint8).reshape(-1, self.block_size)

    def close(self) -> None:
        self._mm.close()


@contextmanager
def open_image_blocks(path: str) -> Iterator[ImageBlocks]:
    """Memory-map a disk image as read-only 4KB blocks; the map is always closed on exit."""
    with open(path, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        img = ImageBlocks(mm)
        try:
            yield img
        finally:
            img.close()


if __name__ == "__main__":
    from engine.pretrain_utils import SyntheticFragmentCorpus, _make_jpeg, _make_pdf, _make_zip

    rng = np.random.default_rng(3)
    files = [_make_jpeg(rng, 5 * BLOCK_SIZE), _make_pdf(rng, 6 * BLOCK_SIZE), _make_zip(rng, 4 * BLOCK_SIZE)]
    blocks = [SyntheticFragmentCorpus.blockify(f) for f in files]
    image = np.concatenate([blocks[0], np.zeros((2, BLOCK_SIZE), np.uint8), blocks[1], blocks[2]])
    res = carve(image)
    closed = [s for s in res.streams if s.closed]
    assert [s.mime for s in closed] == ["image/jpeg", "application/pdf", "application/zip"], res.streams
    assert closed[0].assemble(image) == files[0]
    assert closed[2].assemble(image) == files[2]
    assert res.orphans == [5, 6], res.orphans  # zero blocks are orphans without a noise mask
    # fragmented: interleave two files -> jpeg cannot close contiguously
    frag = np.concatenate([blocks[0][:2], blocks[1][:3], blocks[0][2:], blocks[1][3:]])
    res2 = carve(frag)
    open_ = [s for s in res2.streams if not s.closed]
    assert len(open_) == 1 and open_[0].mime == "image/jpeg" and open_[0].blocks == [0, 1], res2.streams
    assert res2.orphans == [0, 1], res2.orphans
    # Signature-only carving mis-closes the PDF around the foreign JPEG blocks: this is the
    # known ceiling of FR2.0. carver_ml.validate_structural_coherence scores that stream low
    # and the caller demotes its blocks to orphans for FR2.1-2.3.
    bad_pdf = [s for s in res2.streams if s.mime == "application/pdf"][0]
    assert bad_pdf.closed and set(bad_pdf.blocks) >= {5, 6, 7}
    print("OK signature_carver:", len(closed), "closed streams;", len(res2.orphans), "orphans in fragmented image")

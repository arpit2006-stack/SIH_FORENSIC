"""Phase 1 (FR1.0): hardware detection + synthetic fragmentation corpus.

Air-gapped: no network, no downloads. Everything operates on raw bytes /
np.uint8 arrays.
"""
from __future__ import annotations

import logging
import os
import shutil
import struct
import zlib
from typing import Iterator, NamedTuple

import numpy as np

log = logging.getLogger(__name__)

BLOCK_SIZE = 4096
FILE_TYPES = ("pdf", "jpeg", "zip", "elf", "pe")
LABELS = {t: i for i, t in enumerate(FILE_TYPES)}


# --------------------------------------------------------------------------- #
# Hardware detection
# --------------------------------------------------------------------------- #
def get_optimal_execution_providers() -> list[str]:
    """Return ORT provider chain: CUDA first if usable, else CPU only.

    Never raises. Every probe is wrapped; any failure means CPU fallback.
    """
    cpu_only = ["CPUExecutionProvider"]
    try:
        import onnxruntime as ort  # noqa: WPS433
    except Exception as exc:  # pragma: no cover - ORT missing entirely
        log.warning("onnxruntime unavailable (%s); defaulting to CPU", exc)
        return cpu_only

    try:
        available = set(ort.get_available_providers())
    except Exception as exc:
        log.warning("ORT provider query failed (%s); defaulting to CPU", exc)
        return cpu_only

    if "CUDAExecutionProvider" not in available:
        log.info("ORT build has no CUDA provider; using CPU")
        return cpu_only

    # Driver present? nvidia-smi on PATH or a CUDA-ish env var is a cheap hint.
    driver_hint = bool(shutil.which("nvidia-smi") or os.environ.get("CUDA_PATH")
                       or os.environ.get("CUDA_HOME"))
    if not driver_hint:
        log.info("CUDA provider built but no NVIDIA driver detected; using CPU")
        return cpu_only

    # Real probe: ORT reports CUDA but silently drops it when cuDNN/cuBLAS are
    # missing. Build a trivial session and check what actually got loaded.
    try:
        import onnx
        from onnx import TensorProto, helper

        node = helper.make_node("Identity", ["x"], ["y"])
        graph = helper.make_graph(
            [node], "probe",
            [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1])],
            [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1])],
        )
        model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
        model.ir_version = 8
        ort.set_default_logger_severity(4)  # silence native "Failed to create CUDA EP" spam
        so = ort.SessionOptions()
        so.log_severity_level = 4
        sess = ort.InferenceSession(
            model.SerializeToString(), so,
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
        if "CUDAExecutionProvider" in sess.get_providers():
            log.info("CUDA execution provider verified")
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]
        log.info("CUDA provider failed to load (missing cuDNN/cuBLAS?); using CPU")
    except Exception as exc:
        log.info("CUDA probe failed (%s); using CPU", exc)
    return cpu_only


# --------------------------------------------------------------------------- #
# Synthetic benign file generators (no external fixtures needed)
# --------------------------------------------------------------------------- #
def _rand_text(rng: np.random.Generator, n: int) -> bytes:
    words = [b"evidence", b"invoice", b"total", b"account", b"report", b"the",
             b"forensic", b"block", b"transfer", b"date", b"2026", b"INR"]
    out = bytearray()
    while len(out) < n:
        out += words[rng.integers(len(words))] + b" "
    return bytes(out[:n])


def _make_pdf(rng: np.random.Generator, size: int) -> bytes:
    body = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj = 3
    while len(body) < size - 200:
        stream = zlib.compress(_rand_text(rng, rng.integers(512, 4096)))
        body += (f"{obj} 0 obj\n<< /Length {len(stream)} /Filter /FlateDecode >>\nstream\n"
                 .encode() + stream + b"\nendstream\nendobj\n")
        obj += 1
    body += b"xref\n0 1\n0000000000 65535 f \ntrailer\n<< /Root 1 0 R >>\nstartxref\n9\n%%EOF\n"
    return body


def _make_jpeg(rng: np.random.Generator, size: int) -> bytes:
    # SOI + APP0 + DQT-ish header, then entropy-coded-looking payload w/o 0xFF, then EOI.
    hdr = (b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00\x48\x00\x48\x00\x00"
           b"\xff\xdb\x00\x43\x00" + bytes(rng.integers(1, 64, 64, dtype=np.uint8))
           + b"\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00")
    payload = rng.integers(0, 255, max(size - len(hdr) - 2, 0), dtype=np.uint8)  # never 0xFF
    return hdr + payload.tobytes() + b"\xff\xd9"


def _make_zip(rng: np.random.Generator, size: int) -> bytes:
    # Minimal ZIP/DOCX-shaped container built by hand (stored + deflated members).
    members, central, offset = bytearray(), bytearray(), 0
    names = [b"[Content_Types].xml", b"word/document.xml", b"word/styles.xml", b"docProps/core.xml"]
    i = 0
    while len(members) < size - 512:
        name = names[i % len(names)] + (b"" if i < len(names) else str(i).encode())
        raw = _rand_text(rng, rng.integers(1024, 8192))
        comp = zlib.compress(raw)[2:-4]  # raw deflate
        crc = zlib.crc32(raw)
        local = (b"PK\x03\x04" + struct.pack("<HHHHHIIIHH", 20, 0, 8, 0, 0, crc, len(comp), len(raw), len(name), 0)
                 + name + comp)
        central += (b"PK\x01\x02" + struct.pack("<HHHHHHIIIHHHHHII", 20, 20, 0, 8, 0, 0, crc, len(comp), len(raw),
                                                  len(name), 0, 0, 0, 0, 0, offset) + name)
        members += local
        offset += len(local)
        i += 1
    eocd = b"PK\x05\x06" + struct.pack("<HHHHIIH", 0, 0, i, i, len(central), offset, 0)
    return bytes(members + central + eocd)


def _make_elf(rng: np.random.Generator, size: int) -> bytes:
    hdr = (b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 8
           + struct.pack("<HHIQQQIHHHHHH", 2, 0x3E, 1, 0x401000, 64, 0, 0, 64, 56, 1, 64, 0, 0))
    # x86-64 code-ish: mix of common opcode bytes, plus .rodata strings.
    ops = np.array([0x48, 0x89, 0xE5, 0x55, 0x5D, 0xC3, 0x8B, 0x45, 0xE8, 0x0F, 0x1F, 0x00, 0x90, 0xFF], dtype=np.uint8)
    code = ops[rng.integers(0, len(ops), size // 2)].tobytes()
    strings = _rand_text(rng, size - len(hdr) - len(code)).replace(b" ", b"\x00")
    return hdr + code + strings


def _make_pe(rng: np.random.Generator, size: int) -> bytes:
    dos = b"MZ\x90\x00" + b"\x00" * 56 + struct.pack("<I", 0x80) + b"\x00" * 64
    dos += b"\x0e\x1f\xba\x0e\x00\xb4\x09\xcd\x21\xb8\x01\x4c\xcd\x21This program cannot be run in DOS mode.\r\r\n$"
    dos = dos.ljust(0x80, b"\x00")
    pe = b"PE\x00\x00" + struct.pack("<HHIIIHH", 0x8664, 2, 0, 0, 0, 240, 0x22)
    ops = np.array([0x48, 0x8B, 0x0D, 0x89, 0xE5, 0xC3, 0xFF, 0x15, 0xCC, 0x90, 0x00], dtype=np.uint8)
    code = ops[rng.integers(0, len(ops), size // 2)].tobytes()
    rest = _rand_text(rng, size - len(dos) - len(pe) - len(code)).replace(b" ", b"\x00")
    return dos + pe + code + rest


_GENERATORS = {"pdf": _make_pdf, "jpeg": _make_jpeg, "zip": _make_zip, "elf": _make_elf, "pe": _make_pe}


# --------------------------------------------------------------------------- #
# Corpus
# --------------------------------------------------------------------------- #
class Triplet(NamedTuple):
    anchor_block: bytes
    positive_block: bytes
    negative_block: bytes
    label: int  # file-type index of anchor (see LABELS)


class SyntheticFragmentCorpus:
    """Blockify benign files into 4KB units and emit degraded contrastive triplets.

    anchor/positive are adjacent blocks of one file (continuity = 1);
    negative is a block from a different file. Each block passes through
    random degradation so the model never sees pristine boundaries only.
    """

    def __init__(self, seed: int = 0, n_files_per_type: int = 4,
                 file_size_range: tuple[int, int] = (16 * BLOCK_SIZE, 64 * BLOCK_SIZE),
                 degrade_p: float = 0.5, source_files: dict[str, list[bytes]] | None = None):
        self.rng = np.random.default_rng(seed)
        self.degrade_p = degrade_p
        # {type: [np.uint8 array of blocks (n, 4096)]}
        self.blocks: dict[str, list[np.ndarray]] = {t: [] for t in FILE_TYPES}
        src = source_files or {}
        for t in FILE_TYPES:
            files = src.get(t) or [
                _GENERATORS[t](self.rng, int(self.rng.integers(*file_size_range)))
                for _ in range(n_files_per_type)
            ]
            for f in files:
                self.blocks[t].append(self.blockify(f))

    # -- block ops (all on np.uint8) --------------------------------------- #
    @staticmethod
    def blockify(data: bytes, block_size: int = BLOCK_SIZE) -> np.ndarray:
        """Split into (n, block_size) uint8; last block zero-padded (slack)."""
        arr = np.frombuffer(data, dtype=np.uint8)
        pad = (-len(arr)) % block_size
        arr = np.concatenate([arr, np.zeros(pad, dtype=np.uint8)])
        return arr.reshape(-1, block_size)

    def truncate(self, blk: np.ndarray) -> np.ndarray:
        """Cut the tail (lose footer) and zero the remainder."""
        cut = int(self.rng.integers(BLOCK_SIZE // 4, BLOCK_SIZE))
        out = blk.copy()
        out[cut:] = 0
        return out

    def shuffle_fragments(self, blk: np.ndarray, n_parts: int = 4) -> np.ndarray:
        """Out-of-order write simulation: permute equal sub-fragments."""
        parts = blk.reshape(n_parts, -1)
        return parts[self.rng.permutation(n_parts)].reshape(-1)

    def insert_bytes(self, blk: np.ndarray) -> np.ndarray:
        """Insert random junk at a random offset; keep block size fixed."""
        n = int(self.rng.integers(1, 256))
        at = int(self.rng.integers(0, BLOCK_SIZE - n))
        junk = self.rng.integers(0, 256, n, dtype=np.uint8)
        return np.concatenate([blk[:at], junk, blk[at:]])[:BLOCK_SIZE]

    def zero_fill(self, blk: np.ndarray) -> np.ndarray:
        """Slack padding: zero a random tail *or* random interior run."""
        out = blk.copy()
        start = int(self.rng.integers(0, BLOCK_SIZE - 64))
        end = BLOCK_SIZE if self.rng.random() < 0.5 else int(self.rng.integers(start + 64, BLOCK_SIZE + 1))
        out[start:end] = 0
        return out

    def degrade(self, blk: np.ndarray) -> np.ndarray:
        if self.rng.random() >= self.degrade_p:
            return blk
        op = self.rng.choice([self.truncate, self.shuffle_fragments, self.insert_bytes, self.zero_fill])
        return op(blk)

    # -- sampling ---------------------------------------------------------- #
    def _pick_adjacent(self, t: str) -> tuple[np.ndarray, np.ndarray]:
        f = self.blocks[t][self.rng.integers(len(self.blocks[t]))]
        i = int(self.rng.integers(0, len(f) - 1))
        return f[i], f[i + 1]

    def _pick_any(self, t: str) -> np.ndarray:
        f = self.blocks[t][self.rng.integers(len(self.blocks[t]))]
        return f[self.rng.integers(len(f))]

    def sample(self) -> Triplet:
        t = FILE_TYPES[self.rng.integers(len(FILE_TYPES))]
        neg_t = FILE_TYPES[(LABELS[t] + int(self.rng.integers(1, len(FILE_TYPES)))) % len(FILE_TYPES)]
        a, p = self._pick_adjacent(t)
        n = self._pick_any(neg_t)
        return Triplet(self.degrade(a).tobytes(), self.degrade(p).tobytes(),
                       self.degrade(n).tobytes(), LABELS[t])

    def batches(self, n: int, batch_size: int = 32) -> Iterator[list[Triplet]]:
        for start in range(0, n, batch_size):
            yield [self.sample() for _ in range(min(batch_size, n - start))]

    def split(self, n_train: int, n_val: int) -> tuple[list[Triplet], list[Triplet]]:
        return [self.sample() for _ in range(n_train)], [self.sample() for _ in range(n_val)]


# --------------------------------------------------------------------------- #
# Self-check: python -m engine.pretrain_utils
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    providers = get_optimal_execution_providers()
    assert providers in (["CPUExecutionProvider"], ["CUDAExecutionProvider", "CPUExecutionProvider"]), providers
    print("providers:", providers)

    corpus = SyntheticFragmentCorpus(seed=42)
    trips = [t for b in corpus.batches(1000, batch_size=64) for t in b]
    assert len(trips) == 1000
    for t in trips:
        assert len(t.anchor_block) == len(t.positive_block) == len(t.negative_block) == BLOCK_SIZE
        assert isinstance(t.anchor_block, bytes) and 0 <= t.label < len(FILE_TYPES)
    labels = np.bincount([t.label for t in trips], minlength=len(FILE_TYPES))
    assert (labels > 0).all(), labels
    # determinism
    c2 = SyntheticFragmentCorpus(seed=42)
    assert c2.sample() == SyntheticFragmentCorpus(seed=42).sample()
    print(f"OK: 1000 triplets, label counts {dict(zip(FILE_TYPES, labels.tolist()))}")

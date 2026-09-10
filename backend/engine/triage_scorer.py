"""Phase 1 (FR1.1-FR1.4): entropy stats, 1D-CNN block triage, ONNX export, fast ORT runtime.

Hot path is batched: per-block ORT calls cost ~100us each, which alone caps
throughput at ~40 MB/s. `FastBlockTriage.predict_blocks` is the >100 MB/s path;
`predict_block` is the single-block convenience wrapper.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Tuple

import numpy as np

from engine.pretrain_utils import (BLOCK_SIZE, SyntheticFragmentCorpus, _rand_text,
                                   get_optimal_execution_providers)

log = logging.getLogger(__name__)

CLASSES = ("TEXT", "IMAGE_MEDIA", "COMPRESSED_ENCRYPTED", "NOISE_EMPTY")
NOISE_IDX = CLASSES.index("NOISE_EMPTY")
DEFAULT_MODEL_PATH = "models/block_classifier.onnx"
ENTROPY_BYPASS = 0.5
ZERO_FRAC_BYPASS = 0.95


# --------------------------------------------------------------------------- #
# 1. Deterministic statistics
# --------------------------------------------------------------------------- #
def calculate_byte_frequency(block: bytes) -> np.ndarray:
    """Normalized 256-bin histogram (sums to 1.0; all-zero for empty input)."""
    counts = np.bincount(np.frombuffer(block, dtype=np.uint8), minlength=256).astype(np.float64)
    n = counts.sum()
    return counts / n if n else counts


def calculate_shannon_entropy(block: bytes) -> float:
    """Shannon entropy in bits/byte, range [0.0, 8.0]."""
    p = calculate_byte_frequency(block)
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum()) if p.size else 0.0


def _batch_stats(u8: np.ndarray, stride: int = 4) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized (entropy, zero_fraction) for a (B, N) uint8 array.

    ponytail: entropy is estimated from every `stride`-th byte (1024 samples/block);
    that is plenty for a 0.5-bit bypass threshold and halves the stats cost.
    Set stride=1 for exact. zero_fraction is always exact.
    """
    b, n = u8.shape
    s = u8[:, ::stride]
    idx = s.astype(np.int32) + (np.arange(b, dtype=np.int32) * 256)[:, None]
    counts = np.bincount(idx.ravel(), minlength=b * 256).reshape(b, 256)
    p = counts / s.shape[1]
    with np.errstate(divide="ignore", invalid="ignore"):
        ent = -np.nansum(p * np.log2(p), axis=1)
    return ent, np.count_nonzero(u8 == 0, axis=1) / n


def _boost_process_priority() -> None:
    """Windows 11 + hybrid Intel (P/E cores) demotes a console process to efficiency
    scheduling after a few seconds of sustained load: measured 7-10x slowdown of ORT
    *and* numpy. HIGH_PRIORITY_CLASS restores full speed. No-op elsewhere / on failure."""
    if os.name != "nt":
        return
    try:
        import psutil
        psutil.Process().nice(psutil.HIGH_PRIORITY_CLASS)
    except Exception as exc:  # pragma: no cover
        log.debug("priority boost skipped: %s", exc)


# --------------------------------------------------------------------------- #
# 2. PyTorch 1D-CNN
# --------------------------------------------------------------------------- #
def _torch():
    import torch  # lazy: runtime path must not need torch
    import torch.nn as nn
    return torch, nn


class _CNNFactory:
    """Deferred class creation so importing this module never imports torch."""
    _cls = None

    @classmethod
    def get(cls):
        if cls._cls is None:
            torch, nn = _torch()

            class BlockClassifierCNN(nn.Module):
                def __init__(self, n_classes: int = len(CLASSES)):
                    super().__init__()
                    self.features = nn.Sequential(
                        nn.Conv1d(1, 16, kernel_size=8, stride=4),   # (16, 1023)
                        nn.BatchNorm1d(16),
                        nn.ReLU(inplace=True),
                        nn.Conv1d(16, 32, kernel_size=4, stride=2),  # (32, 510)
                        nn.MaxPool1d(4),                              # (32, 127)
                        nn.Flatten(),
                    )
                    self.head = nn.Sequential(
                        nn.Linear(32 * 127, 128),
                        nn.Dropout(0.2),
                        nn.Linear(128, n_classes),
                    )

                def forward(self, x):  # x: (B, 1, 4096) float in [0, 1]
                    return self.head(self.features(x))

            cls._cls = BlockClassifierCNN
        return cls._cls


def BlockClassifierCNN(*a, **kw):  # noqa: N802 - keep the PRD's class name callable
    return _CNNFactory.get()(*a, **kw)


def build_labeled_blocks(corpus: SyntheticFragmentCorpus, n_per_class: int = 1500
                         ) -> tuple[np.ndarray, np.ndarray]:
    """Derive 4-class labels from the Node 01 corpus.

    TEXT   <- plain text blocks; IMAGE_MEDIA <- JPEG blocks;
    COMPRESSED_ENCRYPTED <- ZIP/PDF-flate blocks + os.urandom;
    NOISE_EMPTY <- zero blocks, slack-padded and truncated blocks.
    Every block then passes corpus.degrade() so labels survive fragmentation.
    """
    rng = corpus.rng
    pool = {t: np.concatenate(corpus.blocks[t]) for t in corpus.blocks}

    def pick(t, k):
        return pool[t][rng.integers(len(pool[t]), size=k)]

    text = np.stack([np.frombuffer(_rand_text(rng, BLOCK_SIZE), np.uint8) for _ in range(n_per_class)])
    image = pick("jpeg", n_per_class)
    comp = np.concatenate([pick("zip", n_per_class // 2), pick("pdf", n_per_class // 4),
                           rng.integers(0, 256, (n_per_class - n_per_class // 2 - n_per_class // 4, BLOCK_SIZE),
                                        dtype=np.uint8)])
    noise = np.zeros((n_per_class, BLOCK_SIZE), np.uint8)
    for i in range(n_per_class):
        if rng.random() < 0.5:  # mostly-zero slack with a small live prefix
            k = int(rng.integers(0, BLOCK_SIZE // 20))
            noise[i, :k] = rng.integers(0, 256, k, dtype=np.uint8)

    x = np.concatenate([text, image, comp, noise])
    y = np.repeat(np.arange(len(CLASSES)), [len(text), len(image), len(comp), len(noise)])
    x = np.stack([corpus.degrade(b) for b in x])
    # Degradation may zero-fill a real block into noise; relabel by the bypass rule.
    ent, zf = _batch_stats(x)
    y = np.where((ent < ENTROPY_BYPASS) | (zf > ZERO_FRAC_BYPASS), NOISE_IDX, y)
    perm = rng.permutation(len(x))
    return x[perm], y[perm].astype(np.int64)


def train_model(corpus: SyntheticFragmentCorpus, epochs: int = 5, batch_size: int = 64,
                lr: float = 1e-3, val_frac: float = 0.15):
    torch, nn = _torch()
    torch.manual_seed(0)
    x, y = build_labeled_blocks(corpus)
    n_val = int(len(x) * val_frac)
    xt = torch.from_numpy(x).float().div_(255.0).unsqueeze(1)
    yt = torch.from_numpy(y)
    x_tr, y_tr, x_va, y_va = xt[n_val:], yt[n_val:], xt[:n_val], yt[:n_val]

    model = BlockClassifierCNN()
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.CrossEntropyLoss()
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(len(x_tr))
        tot = 0.0
        for i in range(0, len(x_tr), batch_size):
            idx = perm[i:i + batch_size]
            opt.zero_grad()
            loss = loss_fn(model(x_tr[idx]), y_tr[idx])
            loss.backward()
            opt.step()
            tot += loss.item() * len(idx)
        model.eval()
        with torch.no_grad():
            acc = (model(x_va).argmax(1) == y_va).float().mean().item()
        log.info("epoch %d/%d loss=%.4f val_acc=%.3f", ep + 1, epochs, tot / len(x_tr), acc)
    model.eval()
    return model


# --------------------------------------------------------------------------- #
# 3. ONNX export + runtime
# --------------------------------------------------------------------------- #
def export_to_onnx(model, export_path: str = DEFAULT_MODEL_PATH) -> str:
    torch, _ = _torch()
    Path(export_path).parent.mkdir(parents=True, exist_ok=True)
    model.eval()
    dummy = torch.zeros(1, 1, BLOCK_SIZE)
    torch.onnx.export(model, dummy, export_path, input_names=["blocks"], output_names=["logits"],
                      dynamic_axes={"blocks": {0: "batch"}, "logits": {0: "batch"}},
                      opset_version=17, dynamo=False)
    log.info("exported %s (%d KB)", export_path, os.path.getsize(export_path) // 1024)
    return export_path


class FastBlockTriage:
    """ORT runtime with heuristic bypass and pre-allocated batch buffers."""

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH, batch_size: int = 512,
                 intra_op_threads: int = 4):
        import onnxruntime as ort
        _boost_process_priority()
        so = ort.SessionOptions()
        so.intra_op_num_threads = intra_op_threads
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        so.log_severity_level = 3
        self.providers = get_optimal_execution_providers()
        self.session = ort.InferenceSession(model_path, so, providers=self.providers)
        self.input_name = self.session.get_inputs()[0].name
        self.batch_size = batch_size
        # Pre-allocated buffers: float input for ORT, int label / float conf outputs.
        self._fbuf = np.empty((batch_size, 1, BLOCK_SIZE), dtype=np.float32)
        self._labels = np.empty(batch_size, dtype=np.int64)
        self._conf = np.empty(batch_size, dtype=np.float32)
        self.bypassed = 0
        self.inferred = 0

    def predict_blocks(self, u8: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """u8: (B, 4096) uint8, B <= batch_size. Returns (label_idx[B], confidence[B]) views."""
        b = len(u8)
        ent, zf = _batch_stats(u8)
        bypass = (ent < ENTROPY_BYPASS) | (zf > ZERO_FRAC_BYPASS)
        labels, conf = self._labels[:b], self._conf[:b]
        labels[bypass] = NOISE_IDX
        conf[bypass] = 1.0
        run = ~bypass
        n_run = int(run.sum())
        self.bypassed += b - n_run
        self.inferred += n_run
        if n_run:
            fb = self._fbuf[:n_run]
            np.divide(u8[run], 255.0, out=fb[:, 0, :], dtype=np.float32)
            logits = self.session.run(None, {self.input_name: fb})[0]
            logits -= logits.max(axis=1, keepdims=True)
            np.exp(logits, out=logits)
            logits /= logits.sum(axis=1, keepdims=True)
            labels[run] = logits.argmax(axis=1)
            conf[run] = logits.max(axis=1)
        return labels, conf

    def predict_block(self, block: bytes) -> Tuple[str, float]:
        if calculate_shannon_entropy(block) < ENTROPY_BYPASS or block.count(0) > ZERO_FRAC_BYPASS * len(block):
            self.bypassed += 1
            return "NOISE_EMPTY", 1.0
        u8 = np.frombuffer(block.ljust(BLOCK_SIZE, b"\0")[:BLOCK_SIZE], np.uint8)[None]
        labels, conf = self.predict_blocks(u8)
        return CLASSES[int(labels[0])], float(conf[0])

    def scan(self, data: np.ndarray | bytes) -> tuple[np.ndarray, np.ndarray]:
        """Triage a whole image (bytes, flat uint8, or (N, 4096) uint8). Returns (labels, conf) per block.

        A (N, 4096) uint8 array is consumed in place; anything else is blockified once (one copy)."""
        if isinstance(data, np.ndarray) and data.ndim == 2 and data.shape[1] == BLOCK_SIZE and data.dtype == np.uint8:
            u8 = data
        else:
            u8 = SyntheticFragmentCorpus.blockify(data if isinstance(data, bytes) else data.tobytes())
        out_l = np.empty(len(u8), np.int64)
        out_c = np.empty(len(u8), np.float32)
        for i in range(0, len(u8), self.batch_size):
            l, c = self.predict_blocks(u8[i:i + self.batch_size])
            out_l[i:i + len(l)] = l
            out_c[i:i + len(c)] = c
        return out_l, out_c


# --------------------------------------------------------------------------- #
# Self-check + benchmark: python -m engine.triage_scorer
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import psutil

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    proc = psutil.Process()

    # stats
    assert calculate_shannon_entropy(b"\0" * 4096) == 0.0
    assert abs(calculate_shannon_entropy(bytes(range(256)) * 16) - 8.0) < 1e-9
    assert abs(calculate_byte_frequency(b"ab").sum() - 1.0) < 1e-12

    # train + export
    corpus = SyntheticFragmentCorpus(seed=7)
    if not os.path.exists(DEFAULT_MODEL_PATH):
        model = train_model(corpus, epochs=5)
        export_to_onnx(model)

    triage = FastBlockTriage()
    print("providers:", triage.providers)
    assert triage.predict_block(b"\0" * 4096) == ("NOISE_EMPTY", 1.0)
    lbl, cf = triage.predict_block(_rand_text(corpus.rng, 4096))
    print("text block ->", lbl, round(cf, 3))
    assert lbl in CLASSES and 0.0 <= cf <= 1.0

    # 100 MB benchmark: realistic mix (~25% zero/slack, rest live data)
    n_blocks = 25_000
    x, y = build_labeled_blocks(corpus, n_per_class=n_blocks // 4)
    x = np.ascontiguousarray(x[:n_blocks])
    assert x.nbytes == n_blocks * BLOCK_SIZE
    rss_before = proc.memory_info().rss
    triage.predict_blocks(x[:triage.batch_size])  # warm-up
    t0 = time.perf_counter()
    labels, conf = triage.scan(x)
    dt = time.perf_counter() - t0
    rss_after = proc.memory_info().rss
    mbps = x.nbytes / dt / 1e6
    acc = (labels == y[:n_blocks]).mean()
    print(f"blocks={n_blocks} bytes={x.nbytes / 1e6:.0f}MB time={dt:.3f}s throughput={mbps:.1f} MB/s")
    print(f"bypassed={triage.bypassed} inferred={triage.inferred} label_acc={acc:.3f}")
    print(f"rss_before={rss_before / 2**20:.1f}MiB rss_after={rss_after / 2**20:.1f}MiB "
          f"delta={(rss_after - rss_before) / 2**20:+.1f}MiB "
          f"prealloc_buffers={(triage._fbuf.nbytes + triage._labels.nbytes + triage._conf.nbytes) / 2**20:.1f}MiB")
    # Steady state: a second full pass must not grow RSS (ORT arena + our buffers are reused).
    triage.scan(x)
    rss_second = proc.memory_info().rss
    print(f"second pass rss_delta={(rss_second - rss_after) / 2**20:+.1f}MiB (arena steady state)")
    assert mbps >= 100, f"throughput {mbps:.1f} MB/s < 100 MB/s"
    assert rss_second - rss_after < 16 * 2**20, "memory grows across passes"
    print("OK")

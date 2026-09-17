"""FR1.5 / FR2.4: model explainability for the forensic pipeline.

FR1.5 – SHAP-style block attribution via occlusion saliency on the ONNX
         block classifier.  Sliding a zero-window over the 4096-byte input
         and measuring the logit drop for the predicted class gives a
         gradient-free attribution map without backprop through ONNX.

FR2.4 – Reassembly rationale: per-chain edge costs, total residuals, and
         runner-up alternate costs extracted from the affinity matrix so the
         analyst can audit *why* the solver chose each link.

Heavy dependencies (onnxruntime, numpy) are used directly; torch is never
imported.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

from engine.pretrain_utils import BLOCK_SIZE, get_optimal_execution_providers
from engine.triage_scorer import CLASSES, DEFAULT_MODEL_PATH

if TYPE_CHECKING:
    from engine.graph_reassembly import ResolveResult

log = logging.getLogger(__name__)

# -- ONNX session cache --------------------------------------------------- #
_SESSION_CACHE: dict[str, object] = {}


def _get_session(model_path: str):
    """Return a cached ``ort.InferenceSession`` for *model_path*."""
    if model_path not in _SESSION_CACHE:
        import onnxruntime as ort

        so = ort.SessionOptions()
        so.intra_op_num_threads = 2
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        so.log_severity_level = 3
        providers = get_optimal_execution_providers()
        _SESSION_CACHE[model_path] = ort.InferenceSession(
            model_path, so, providers=providers,
        )
    return _SESSION_CACHE[model_path]


# ═══════════════════════════════════════════════════════════════════════════
# FR1.5: occlusion-based block attribution
# ═══════════════════════════════════════════════════════════════════════════

def _run_logits(session, blocks_f32: np.ndarray) -> np.ndarray:
    """Run the block classifier and return raw logits ``(B, n_classes)``."""
    return session.run(None, {"blocks": blocks_f32})[0]


def generate_block_attributions(
    block_data: bytes,
    model_path: str = DEFAULT_MODEL_PATH,
    stride: int = 64,
) -> list[float]:
    """Occlusion saliency for a single 4096-byte block.

    The block is divided into ``BLOCK_SIZE // stride`` segments.  For each
    segment the bytes are zeroed and the logit for the predicted class is
    re-evaluated.  The attribution of segment *k* is the drop in logit
    relative to the unperturbed prediction, normalised to [0, 1].

    Parameters
    ----------
    block_data:
        Raw bytes of the block (padded / truncated to ``BLOCK_SIZE``).
    model_path:
        Path to the ONNX block classifier.
    stride:
        Segment size in bytes; ``BLOCK_SIZE`` must be divisible by it.

    Returns
    -------
    list[float]
        One attribution score per segment, in [0, 1].
    """
    assert BLOCK_SIZE % stride == 0, f"BLOCK_SIZE ({BLOCK_SIZE}) not divisible by stride ({stride})"
    n_segments = BLOCK_SIZE // stride

    # Prepare the baseline input (B=1, 1, BLOCK_SIZE) float32 in [0, 1].
    raw = (block_data.ljust(BLOCK_SIZE, b"\0"))[:BLOCK_SIZE]
    base = np.frombuffer(raw, dtype=np.uint8).astype(np.float32) / 255.0
    base_input = base.reshape(1, 1, BLOCK_SIZE)

    session = _get_session(model_path)
    base_logits = _run_logits(session, base_input)[0]          # (n_classes,)
    pred_cls = int(base_logits.argmax())
    base_score = float(base_logits[pred_cls])

    # Build all occluded variants at once -> single batched ORT call.
    occluded = np.tile(base, (n_segments, 1))                   # (S, BLOCK_SIZE)
    for k in range(n_segments):
        occluded[k, k * stride:(k + 1) * stride] = 0.0
    occluded_input = occluded.reshape(n_segments, 1, BLOCK_SIZE).astype(np.float32)

    occ_logits = _run_logits(session, occluded_input)           # (S, n_classes)
    drops = base_score - occ_logits[:, pred_cls]                # positive -> important

    # Normalise to [0, 1].
    d_min, d_max = float(drops.min()), float(drops.max())
    if d_max - d_min < 1e-12:
        return [0.0] * n_segments
    attr = ((drops - d_min) / (d_max - d_min)).tolist()
    return attr


def batch_block_attributions(
    blocks_u8: np.ndarray,
    model_path: str = DEFAULT_MODEL_PATH,
    stride: int = 64,
) -> np.ndarray:
    """Efficient batch occlusion attribution for multiple blocks.

    Parameters
    ----------
    blocks_u8:
        ``(N, BLOCK_SIZE)`` uint8 array of raw blocks.
    model_path:
        ONNX model path.
    stride:
        Segment size in bytes.

    Returns
    -------
    np.ndarray
        ``(N, n_segments)`` float32 attribution scores, each row in [0, 1].
    """
    assert BLOCK_SIZE % stride == 0
    n_segments = BLOCK_SIZE // stride
    n_blocks = len(blocks_u8)

    session = _get_session(model_path)

    # Baseline logits for all blocks.
    base_f32 = blocks_u8.astype(np.float32).reshape(n_blocks, 1, BLOCK_SIZE) / 255.0
    base_logits = _run_logits(session, base_f32)                # (N, C)
    pred_cls = base_logits.argmax(axis=1)                       # (N,)
    base_scores = base_logits[np.arange(n_blocks), pred_cls]    # (N,)

    result = np.empty((n_blocks, n_segments), dtype=np.float32)

    for bi in range(n_blocks):
        row = base_f32[bi, 0, :]                                # (BLOCK_SIZE,)
        occluded = np.tile(row, (n_segments, 1))                # (S, BLOCK_SIZE)
        for k in range(n_segments):
            occluded[k, k * stride:(k + 1) * stride] = 0.0
        occ_input = occluded.reshape(n_segments, 1, BLOCK_SIZE).astype(np.float32)
        occ_logits = _run_logits(session, occ_input)            # (S, C)
        drops = base_scores[bi] - occ_logits[:, pred_cls[bi]]
        d_min, d_max = drops.min(), drops.max()
        if d_max - d_min < 1e-12:
            result[bi] = 0.0
        else:
            result[bi] = (drops - d_min) / (d_max - d_min)

    return result


# ═══════════════════════════════════════════════════════════════════════════
# FR2.4: reassembly rationale
# ═══════════════════════════════════════════════════════════════════════════

def extract_reassembly_rationale(
    resolve_result: ResolveResult,
    fragments: list[bytes],
) -> dict:
    """Build a human-readable rationale dict from a ``ResolveResult``.

    For every chain the solver produced, we report:

    * ``chain_order``      - fragment indices in reassembled order
    * ``edge_costs``       - the assignment cost of each consecutive link
    * ``total_residual``   - sum of edge costs (lower is better)
    * ``alternate_costs``  - for each edge i->j, the cost of the *runner-up*
      successor (the next-best column in the affinity row), so the analyst
      can gauge how decisive each link was.

    Parameters
    ----------
    resolve_result:
        Output of ``GlobalFragmentResolver.resolve()``.
    fragments:
        The same fragment list passed to the resolver.

    Returns
    -------
    dict
        ``{"chains": [<chain_rationale>, ...], "n_singletons": int}``
    """
    aff = resolve_result.affinity
    chain_rationales: list[dict] = []

    for chain in resolve_result.chains:
        order = chain.order
        edge_costs = chain.edge_costs
        total_residual = float(sum(edge_costs))

        alternates: list[float | None] = []
        for idx in range(len(order) - 1):
            src = order[idx]
            dst = order[idx + 1]
            if aff.size == 0:
                alternates.append(None)
                continue
            # Affinity row for src; mask self and the chosen dest.
            row = aff[src].copy()
            row[src] = -np.inf       # exclude self
            row[dst] = -np.inf       # exclude chosen successor
            if np.all(np.isinf(row)):
                alternates.append(None)
            else:
                runner_up_idx = int(row.argmax())
                alternates.append(float(1.0 - row[runner_up_idx]))  # cost

        chain_rationales.append({
            "chain_order": list(order),
            "edge_costs": [float(c) for c in edge_costs],
            "total_residual": total_residual,
            "alternate_costs": alternates,
        })

    return {
        "chains": chain_rationales,
        "n_singletons": len(resolve_result.singletons),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Self-check: python -m engine.explainability
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import os
    from dataclasses import dataclass, field

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    # ------------------------------------------------------------------ #
    # Guard: need the ONNX model for attribution tests
    # ------------------------------------------------------------------ #
    if not os.path.exists(DEFAULT_MODEL_PATH):
        print(f"SKIP attribution tests (model not found at {DEFAULT_MODEL_PATH})")
        _skip_attr = True
    else:
        _skip_attr = False

    # ------------------------------------------------------------------ #
    # 1. Block attributions (single + batch)
    # ------------------------------------------------------------------ #
    if not _skip_attr:
        from engine.pretrain_utils import _rand_text

        rng = np.random.default_rng(42)

        # Text block
        text_block = _rand_text(rng, BLOCK_SIZE)
        attr_text = generate_block_attributions(text_block)
        assert len(attr_text) == BLOCK_SIZE // 64, f"wrong length {len(attr_text)}"
        assert not all(v == 0.0 for v in attr_text), "text attributions all zero"
        assert 0.0 <= min(attr_text) and max(attr_text) <= 1.0 + 1e-9
        print(f"text attr: min={min(attr_text):.4f} max={max(attr_text):.4f} "
              f"segments={len(attr_text)}")

        # Noise block
        noise_block = bytes(rng.integers(0, 256, BLOCK_SIZE, dtype=np.uint8))
        attr_noise = generate_block_attributions(noise_block)
        assert len(attr_noise) == BLOCK_SIZE // 64
        print(f"noise attr: min={min(attr_noise):.4f} max={max(attr_noise):.4f}")

        # Batch version
        u8 = np.stack([
            np.frombuffer(text_block, np.uint8),
            np.frombuffer(noise_block, np.uint8),
        ])
        batch_attr = batch_block_attributions(u8)
        assert batch_attr.shape == (2, BLOCK_SIZE // 64)
        assert batch_attr.dtype == np.float32
        # Should be close to the single-block results.
        np.testing.assert_allclose(batch_attr[0], attr_text, atol=1e-5)
        np.testing.assert_allclose(batch_attr[1], attr_noise, atol=1e-5)
        print("batch attributions match single-block results")
    else:
        print("(attribution tests skipped)")

    # ------------------------------------------------------------------ #
    # 2. Reassembly rationale with a mock ResolveResult
    # ------------------------------------------------------------------ #
    @dataclass
    class _MockChain:
        order: list[int]
        edge_costs: list[float]

    @dataclass
    class _MockResolveResult:
        chains: list[_MockChain]
        affinity: np.ndarray
        singletons: list[int] = field(default_factory=list)

    aff = np.array([
        [0.0, 0.9, 0.3, 0.1],
        [0.2, 0.0, 0.8, 0.4],
        [0.1, 0.3, 0.0, 0.7],
        [0.5, 0.1, 0.2, 0.0],
    ])
    mock = _MockResolveResult(
        chains=[
            _MockChain(order=[0, 1, 2, 3], edge_costs=[0.1, 0.2, 0.3]),
        ],
        affinity=aff,
        singletons=[],
    )
    frags = [b"\x00" * BLOCK_SIZE] * 4

    rationale = extract_reassembly_rationale(mock, frags)
    assert "chains" in rationale and "n_singletons" in rationale
    c0 = rationale["chains"][0]
    assert c0["chain_order"] == [0, 1, 2, 3]
    assert c0["edge_costs"] == [0.1, 0.2, 0.3]
    assert abs(c0["total_residual"] - 0.6) < 1e-9
    assert len(c0["alternate_costs"]) == 3
    # alternate for edge 0->1: row 0 with 1 masked -> best is col 2 (aff=0.3), cost=0.7
    assert c0["alternate_costs"][0] is not None
    assert abs(c0["alternate_costs"][0] - 0.7) < 1e-9, c0["alternate_costs"][0]
    print(f"rationale: {rationale}")

    print("OK explainability")

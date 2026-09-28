"""Fit S = w1.C_hf + w2.C_struct + w3.(1-d_ent) + w4.C_sem against MEASURED fidelity.

The shipped weights (0.30/0.30/0.15/0.25) were set by intuition. This harvests every
candidate the pipeline can produce across the benchmark scenarios, pairs each with its
true fidelity (which needs ground truth, so it is only available offline), and reports
how well each component actually predicts fidelity.
"""
from __future__ import annotations

import itertools
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "bench"))

import matrix as M                                          # noqa: E402
from fidelity import score as fscore                        # noqa: E402
from engine.signature_carver import carve                   # noqa: E402
from engine.graph_reassembly import validate_carve, GlobalFragmentResolver  # noqa: E402
from engine.carver_ml import SiameseAdjacency               # noqa: E402
from engine.report_gen import ForensicReliabilityScorer     # noqa: E402

SCEN = ["clean-deletion", "quick-format", "fragmented", "partial-overwrite", "damaged-sectors"]


def harvest() -> tuple[np.ndarray, np.ndarray, list]:
    """-> (features Nx4, true_fidelity N, meta)"""
    sia = SiameseAdjacency()
    scorer = ForensicReliabilityScorer()
    X, y, meta = [], [], []
    for sc in SCEN:
        for seed in (1234, 77, 2026, 31337, 8, 555, 90210, 4242):
            rng = np.random.default_rng(seed)
            img, truth = M.build(sc, rng)
            cands = []          # (mime, data, kwargs for scorer)
            for th in (0.0, 0.30):
                res = carve(img, min_continuity=th)
                valid, orph = validate_carve(img, res, min_struct=0.85)
                for s in res.streams:
                    if not s.closed or s.mime not in truth:
                        continue
                    cands.append((s.mime, s.assemble(img), {}))
                cand_blk = [b for b in orph if img[b].any()][:200]
                if cand_blk:
                    ob = [img[b].tobytes() for b in cand_blk]
                    rr = GlobalFragmentResolver(siamese=sia).resolve(ob, mime=None)
                    for ch in rr.chains:
                        if not ch.mime or ch.mime not in truth:
                            continue
                        d = ch.assemble(ob)
                        if len(d) < 64:
                            continue
                        cands.append((ch.mime, d, dict(fragments=ob, chain_order=ch.order,
                                                       chain_residual=ch.residual, siamese=sia)))
            seen = set()
            for mime, data, kw in cands:
                h = hash(data)
                if h in seen:
                    continue
                seen.add(h)
                b = scorer.score(data=data, mime=mime, **kw)
                X.append([b.C_hf, b.C_struct, 1.0 - b.delta_ent, b.C_sem])
                y.append(fscore(data, truth[mime], mime).overall)
                meta.append(((sc, seed), mime, len(data), len(truth[mime])))
    return np.array(X, float), np.array(y, float), meta


def fit_simplex(X: np.ndarray, y: np.ndarray, step: float = 0.05) -> tuple[tuple, float]:
    """Grid search over the weight simplex (weights must be >=0 and sum to 1)."""
    best, best_err = None, 1e9
    grid = np.arange(0.0, 1.0 + 1e-9, step)
    for w1 in grid:
        for w2 in grid[grid <= 1.0 - w1 + 1e-9]:
            for w3 in grid[grid <= 1.0 - w1 - w2 + 1e-9]:
                w4 = 1.0 - w1 - w2 - w3
                if w4 < -1e-9:
                    continue
                w = np.array([w1, w2, w3, max(0.0, w4)])
                err = float(np.mean((X @ w - y) ** 2))
                if err < best_err:
                    best_err, best = err, tuple(round(float(v), 3) for v in w)
    return best, best_err


def rank_quality(X: np.ndarray, y: np.ndarray, meta: list, w: np.ndarray) -> float:
    """Fraction of (scenario, mime) groups where argmax(S) is also argmax(true fidelity)."""
    groups: dict = {}
    for i, (sc, mime, _, _) in enumerate(meta):
        groups.setdefault((sc, mime), []).append(i)
    hit = 0
    for _, idx in groups.items():
        s = X[idx] @ w
        hit += int(y[idx][int(np.argmax(s))] >= y[idx].max() - 1e-9)
    return hit / max(1, len(groups))


if __name__ == "__main__":
    X, y, meta = harvest()
    names = ["C_hf", "C_struct", "1-d_ent", "C_sem"]
    print(f"harvested {len(y)} candidates across {len(SCEN)} scenarios x 3 seeds\n")

    print("per-component correlation with TRUE fidelity:")
    for k, n in enumerate(names):
        col = X[:, k]
        r = 0.0 if col.std() < 1e-12 else float(np.corrcoef(col, y)[0, 1])
        print(f"  {n:<10} r={r:+.3f}  mean={col.mean():.3f} std={col.std():.3f}")

    shipped = np.array([0.30, 0.30, 0.15, 0.25])
    mse_fit = np.array(fit_simplex(X, y)[0])

    # Rank accuracy is the objective that actually matters: S is used to CHOOSE between
    # candidate recoveries, so being right about the ordering beats being close in
    # absolute value. Fitting MSE was measured to *lower* rank accuracy (71.4% -> 64.3%).
    best_w, best_r = None, -1.0
    g = np.arange(0.0, 1.0 + 1e-9, 0.05)
    for w1 in g:
        for w2 in g[g <= 1.0 - w1 + 1e-9]:
            for w3 in g[g <= 1.0 - w1 - w2 + 1e-9]:
                w = np.array([w1, w2, w3, max(0.0, 1.0 - w1 - w2 - w3)])
                r = rank_quality(X, y, meta, w)
                if r > best_r or (r == best_r and best_w is not None and w[3] < best_w[3]):
                    best_r, best_w = r, w
    ngroups = len({(m[0], m[1]) for m in meta})
    print(f"\n{ngroups} (scenario, mime) groups to rank\n")
    print(f"{'weights':<15}{'w1 C_hf':>9}{'w2 C_str':>9}{'w3 ent':>9}{'w4 C_sem':>10}"
          f"{'MSE':>9}{'rank-acc':>10}")
    for lbl, w in [("shipped", shipped), ("MSE-fitted", mse_fit), ("rank-fitted", best_w),
                   ("C_struct only", np.array([0., 1., 0., 0.])),
                   ("hf+struct", np.array([0.35, 0.65, 0., 0.]))]:
        print(f"{lbl:<15}{w[0]:>9.3f}{w[1]:>9.3f}{w[2]:>9.3f}{w[3]:>10.3f}"
              f"{float(np.mean((X@w-y)**2)):>9.4f}{rank_quality(X,y,meta,w):>10.1%}")

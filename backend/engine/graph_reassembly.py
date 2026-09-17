"""Phase 2 (FR2.3): global fragment ordering via the Hungarian algorithm.

Affinity  A_ij = alpha * SHT_ij + beta * Siamese_ij   (P that j follows i)
Cost      C_ij = 1 - A_ij
Each block picks at most one successor and one predecessor: a linear assignment
over an augmented 2N x 2N matrix where a dummy "no successor"/"no predecessor"
slot costs `tau`. Cycles left by the assignment are cut at their weakest edge.
Output is *only* an ordering of the input fragments; bytes are never altered.
Every chain carries its assignment residual as the FR2.4 explanation.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linear_sum_assignment

from engine.carver_ml import (SiameseAdjacency, build_pool_context, sht_pair_affinity,
                              validate_structural_coherence)
from engine.signature_carver import SIGNATURES, CarveResult, Stream, detect_header

log = logging.getLogger(__name__)

MAX_POOL = 500  # blocks per Hungarian solve; 500^2 float64 affinity = 2 MB, 2N x 2N cost = 8 MB


@dataclass
class Chain:
    order: list[int]                   # fragment indices, head -> tail
    mime: str | None
    edge_costs: list[float]            # C_ij of each consecutive link (FR2.4 explanation)
    cut_cycle: bool = False            # True if this chain came from breaking a cycle

    @property
    def residual(self) -> float:
        return float(sum(self.edge_costs))

    def assemble(self, fragments: list[bytes]) -> bytes:
        return b"".join(fragments[i] for i in self.order)


@dataclass
class ResolveResult:
    chains: list[Chain]
    affinity: np.ndarray
    singletons: list[int] = field(default_factory=list)


def validate_carve(image: np.ndarray, cr: CarveResult, min_struct: float = 0.9
                   ) -> tuple[list[Stream], list[int]]:
    """FR2.0 -> FR2.1 hand-off: keep closed streams whose C_struct >= min_struct; demote the
    blocks of every other stream to the orphan pool. Returns (valid_streams, orphan_indices)."""
    valid, orphans = [], set(cr.orphans)
    for s in cr.streams:
        if s.closed and validate_structural_coherence(s.assemble(image), s.mime) >= min_struct:
            valid.append(s)
        else:
            orphans.update(s.blocks)
    return valid, sorted(orphans)


class GlobalFragmentResolver:
    def __init__(self, alpha: float = 0.5, beta: float = 0.5, tau: float = 0.55,
                 siamese: SiameseAdjacency | None = None, max_pool: int = MAX_POOL,
                 prune_above: int = 64, top_k: int = 24):
        """tau: cost of leaving a block without successor/predecessor. A link is only
        taken when C_ij < tau, i.e. A_ij > 1 - tau.

        prune_above/top_k: above `prune_above` fragments the SHT is only evaluated on the
        `top_k` Siamese candidates per row. SHT costs ~250us/pair in pure Python, so a full
        500x500 solve would be ~60s; pruning makes it ~6s. Needs a Siamese model.
        """
        assert abs(alpha + beta - 1.0) < 1e-9
        self.alpha, self.beta, self.tau, self.max_pool = alpha, beta, tau, max_pool
        self.prune_above, self.top_k = prune_above, top_k
        self.siamese = siamese

    # -- affinity ------------------------------------------------------------ #
    def affinity_matrix(self, fragments: list[bytes], mime: str | None = None) -> np.ndarray:
        n = len(fragments)
        ctx = build_pool_context(fragments)
        sia = self.siamese.affinity_matrix(fragments).astype(np.float64) if self.siamese else None

        if sia is not None and n > self.prune_above:
            keep = np.zeros((n, n), bool)
            k = min(self.top_k, n - 1)
            rows = np.arange(n)[:, None]
            keep[rows, np.argpartition(-sia, k - 1, axis=1)[:, :k]] = True   # top-k successors
            keep[np.argpartition(-sia, k - 1, axis=0)[:k, :], np.arange(n)] = True  # and predecessors
            np.fill_diagonal(keep, False)
        else:
            keep = ~np.eye(n, dtype=bool)

        sht = np.zeros((n, n), np.float64)
        for i, j in zip(*np.nonzero(keep)):
            sht[i, j] = sht_pair_affinity(fragments[i], fragments[j], mime, ctx)
        if sia is None or self.beta == 0:
            return sht
        return self.alpha * sht + self.beta * sia

    # -- assignment ---------------------------------------------------------- #
    def _assign(self, aff: np.ndarray, heads: set[int], tails: set[int]) -> np.ndarray:
        """Returns succ[i] = j or -1, via Hungarian on the augmented matrix."""
        n = len(aff)
        big = 10.0
        cost = 1.0 - aff
        np.fill_diagonal(cost, big)
        for h in heads:      # a file start has no predecessor
            cost[:, h] = big
        for t in tails:      # a file end has no successor
            cost[t, :] = big
        aug = np.full((2 * n, 2 * n), big)
        aug[:n, :n] = cost
        aug[:n, n:] = big
        aug[n:, :n] = big
        np.fill_diagonal(aug[:n, n:], self.tau)  # i -> "no successor"
        np.fill_diagonal(aug[n:, :n], self.tau)  # "no predecessor" -> j
        aug[n:, n:] = 0.0                        # dummy-dummy pairs are free
        rows, cols = linear_sum_assignment(aug)
        succ = np.full(n, -1, dtype=np.int64)
        for r, c in zip(rows, cols):
            if r < n and c < n:
                succ[r] = c
        return succ

    def _chains(self, succ: np.ndarray, aff: np.ndarray, fragments: list[bytes]) -> list[Chain]:
        n = len(succ)
        pred = np.full(n, -1, dtype=np.int64)
        for i, j in enumerate(succ):
            if j >= 0:
                pred[j] = i
        seen = np.zeros(n, dtype=bool)
        chains: list[Chain] = []

        def walk(start: int, cut: bool) -> None:
            order, costs, k = [start], [], start
            seen[start] = True
            while succ[k] >= 0 and not seen[succ[k]]:
                costs.append(1.0 - float(aff[k, succ[k]]))
                k = succ[k]
                seen[k] = True
                order.append(k)
            chains.append(Chain(order, detect_header(fragments[order[0]]), costs, cut))

        for i in range(n):
            if pred[i] < 0 and not seen[i]:
                walk(i, cut=False)
        for i in range(n):  # leftovers are pure cycles: cut the weakest link, then walk
            if not seen[i]:
                cyc, k = [], i
                while not (k in cyc):
                    cyc.append(k)
                    k = succ[k]
                worst = max(cyc, key=lambda a: 1.0 - aff[a, succ[a]])
                walk(int(succ[worst]), cut=True)
                succ[worst] = -1
                chains[-1].edge_costs = chains[-1].edge_costs  # already excludes the cut edge
        return chains

    # -- public -------------------------------------------------------------- #
    def resolve(self, fragments: list[bytes], mime: str | None = None) -> ResolveResult:
        """Order a pool of orphan fragments. Pools over `max_pool` are solved in slices.

        ponytail: slicing a >500 pool loses cross-slice links; upgrade path is
        coarse pre-clustering by triage class before slicing.
        """
        if len(fragments) > self.max_pool:
            out = ResolveResult([], np.zeros((0, 0)))
            for s in range(0, len(fragments), self.max_pool):
                sub = self.resolve(fragments[s:s + self.max_pool], mime)
                for c in sub.chains:
                    c.order = [s + i for i in c.order]
                out.chains += sub.chains
                out.singletons += [s + i for i in sub.singletons]
            return out

        aff = self.affinity_matrix(fragments, mime)
        heads = {i for i, f in enumerate(fragments) if detect_header(f)}
        tails = {i for i, f in enumerate(fragments)
                 if any(f.rstrip(b"\0").endswith(foot) for _, foot in SIGNATURES.values())}
        succ = self._assign(aff, heads, tails)
        chains = self._chains(succ, aff, fragments)
        chains.sort(key=lambda c: (-len(c.order), c.residual))
        singles = [c.order[0] for c in chains if len(c.order) == 1]
        return ResolveResult([c for c in chains if len(c.order) > 1], aff, singles)


if __name__ == "__main__":
    from engine.pretrain_utils import SyntheticFragmentCorpus, _make_zip

    rng = np.random.default_rng(9)
    z = _make_zip(rng, 10 * 4096 - 100)
    blocks = [b.tobytes() for b in SyntheticFragmentCorpus.blockify(z)]
    perm = rng.permutation(len(blocks))
    frags = [blocks[i] for i in perm]
    res = GlobalFragmentResolver(alpha=1.0, beta=0.0).resolve(frags, "application/zip")
    best = res.chains[0]
    recovered = [int(perm[i]) for i in best.order]
    print("zip recovered order:", recovered, f"residual={best.residual:.3f}")
    assert recovered == list(range(len(blocks))), recovered
    assert best.assemble(frags)[:len(z)] == z
    print("OK graph_reassembly (SHT-only, synthetic zip)")

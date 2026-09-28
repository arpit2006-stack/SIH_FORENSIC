"""P1-2: A/B - Hungarian GLOBAL assignment vs NAIVE greedy pairwise argmax, same affinity matrix."""
import sys, time, io; sys.path.insert(0, r"A:\SIH\SIH_FORENSIC\backend")
import numpy as np
from engine.graph_reassembly import GlobalFragmentResolver, Chain
from engine.pretrain_utils import SyntheticFragmentCorpus, _make_zip
from engine.signature_carver import detect_header, SIGNATURES

def greedy_succ(aff, heads, tails, tau):
    """NAIVE BASELINE: each fragment takes its best-scoring unused successor, in descending
    confidence order. Pairwise only - no global optimality, no one-to-one guarantee upfront."""
    n = len(aff); cost = 1.0 - aff.copy(); np.fill_diagonal(cost, 9e9)
    for h in heads: cost[:, h] = 9e9
    for t in tails: cost[t, :] = 9e9
    succ = np.full(n, -1, np.int64); used_c = set(); used_r = set()
    pairs = sorted(((cost[i,j], i, j) for i in range(n) for j in range(n) if i != j))
    for c, i, j in pairs:
        if c >= tau or i in used_r or j in used_c: continue
        succ[i] = j; used_r.add(i); used_c.add(j)
    return succ

rng = np.random.default_rng(11)
R = GlobalFragmentResolver(alpha=1.0, beta=0.0)   # SHT-only so the A/B isolates the ASSIGNMENT step
trials = 12
hu_exact = gr_exact = 0
hu_kendall = []; gr_kendall = []
t_aff = t_hu = t_gr = 0.0

def frag_acc(order, perm, n):
    """fraction of consecutive TRUE adjacencies the chain reproduced"""
    true_next = {i: i+1 for i in range(n-1)}
    got = 0
    for a, b in zip(order, order[1:]):
        if true_next.get(int(perm[a]), -2) == int(perm[b]): got += 1
    return got / max(1, n-1)

for t in range(trials):
    z = _make_zip(rng, (6 + t % 6) * 4096 - 137)
    blocks = [b.tobytes() for b in SyntheticFragmentCorpus.blockify(z)]
    n = len(blocks)
    perm = rng.permutation(n)
    frags = [blocks[i] for i in perm]
    heads = {i for i,f in enumerate(frags) if detect_header(f)}
    tails = {i for i,f in enumerate(frags) if any(f.rstrip(b"\0").endswith(ft) for _,ft in SIGNATURES.values())}

    s=time.perf_counter(); aff = R.affinity_matrix(frags, "application/zip"); t_aff += time.perf_counter()-s

    s=time.perf_counter(); hs = R._assign(aff, heads, tails); t_hu += time.perf_counter()-s
    s=time.perf_counter(); gs = greedy_succ(aff, heads, tails, R.tau); t_gr += time.perf_counter()-s

    for succ, exact_c, accl in ((hs,'hu',hu_kendall), (gs,'gr',gr_kendall)):
        ch = R._chains(succ.copy(), aff, frags)
        ch = [c for c in ch if c.mime and len(c.order) > 1]
        if not ch: accl.append(0.0); continue
        best = max(ch, key=lambda c: len(c.order))
        rec = [int(perm[i]) for i in best.order]
        accl.append(frag_acc(best.order, perm, n))
        if rec == list(range(n)):
            if exact_c=='hu': hu_exact += 1
            else: gr_exact += 1

print(f"trials={trials}  (SHT-only affinity, identical matrix fed to both solvers)")
print(f"  HUNGARIAN (global): exact full-order recovery {hu_exact}/{trials}"
      f"   mean true-adjacency accuracy {np.mean(hu_kendall):.3f}")
print(f"  GREEDY   (pairwise): exact full-order recovery {gr_exact}/{trials}"
      f"   mean true-adjacency accuracy {np.mean(gr_kendall):.3f}")
print(f"  DELTA: {hu_exact-gr_exact} more exact recoveries, "
      f"{np.mean(hu_kendall)-np.mean(gr_kendall):+.3f} adjacency accuracy")
print(f"\nCPU latency (P1-6), total over {trials} solves:")
print(f"  affinity matrix build (SHT, pure python): {t_aff:.3f}s  ({t_aff/trials*1000:.1f} ms/solve)")
print(f"  Hungarian linear_sum_assignment        : {t_hu:.4f}s ({t_hu/trials*1000:.2f} ms/solve)")
print(f"  greedy baseline                        : {t_gr:.4f}s ({t_gr/trials*1000:.2f} ms/solve)")

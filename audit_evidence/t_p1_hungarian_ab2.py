"""P1-2b: harder A/B - multi-file interleaved pools, 3 solvers on the SAME affinity matrix."""
import sys, time; sys.path.insert(0, r"A:\SIH\SIH_FORENSIC\backend")
import numpy as np
from engine.graph_reassembly import GlobalFragmentResolver
from engine.pretrain_utils import SyntheticFragmentCorpus, _make_zip
from engine.signature_carver import detect_header, SIGNATURES

def argmax_succ(aff, heads, tails, tau):
    "TRULY NAIVE: every row takes its own argmax. No exclusivity at all."
    n=len(aff); c=1.0-aff.copy(); np.fill_diagonal(c,9e9)
    for h in heads: c[:,h]=9e9
    for t in tails: c[t,:]=9e9
    s=np.full(n,-1,np.int64)
    for i in range(n):
        j=int(np.argmin(c[i]))
        if c[i,j]<tau: s[i]=j
    return s

def greedy_succ(aff, heads, tails, tau):
    "GREEDY MATCHING: confidence-sorted, one-to-one enforced. Stronger pairwise baseline."
    n=len(aff); c=1.0-aff.copy(); np.fill_diagonal(c,9e9)
    for h in heads: c[:,h]=9e9
    for t in tails: c[t,:]=9e9
    s=np.full(n,-1,np.int64); ur=set(); uc=set()
    for cost,i,j in sorted((c[i,j],i,j) for i in range(n) for j in range(n) if i!=j):
        if cost>=tau or i in ur or j in uc: continue
        s[i]=j; ur.add(i); uc.add(j)
    return s

rng=np.random.default_rng(23)
R=GlobalFragmentResolver(alpha=1.0,beta=0.0)
NFILES=4; TRIALS=8
stats={k:{'adj':[],'t':0.0} for k in ('hungarian','greedy','argmax')}
for t in range(TRIALS):
    # build NFILES zips, blockify, pool them all together and shuffle
    pool=[]; truth={}   # frag_idx -> (file_id, seq)
    for fid in range(NFILES):
        z=_make_zip(rng,(5+rng.integers(0,6))*4096-91)
        blks=[b.tobytes() for b in SyntheticFragmentCorpus.blockify(z)]
        for si,b in enumerate(blks):
            truth[len(pool)]=(fid,si); pool.append(b)
    order=rng.permutation(len(pool))
    frags=[pool[i] for i in order]
    tr={new:truth[int(old)] for new,old in enumerate(order)}
    n=len(frags)
    heads={i for i,f in enumerate(frags) if detect_header(f)}
    tails={i for i,f in enumerate(frags) if any(f.rstrip(b"\0").endswith(ft) for _,ft in SIGNATURES.values())}
    aff=R.affinity_matrix(frags,"application/zip")
    total_true=sum(1 for v in tr.values() if (v[0],v[1]+1) in set(tr.values()))
    for name,fn in (('hungarian',lambda:R._assign(aff,heads,tails)),
                    ('greedy',lambda:greedy_succ(aff,heads,tails,R.tau)),
                    ('argmax',lambda:argmax_succ(aff,heads,tails,R.tau))):
        s0=time.perf_counter(); succ=fn(); stats[name]['t']+=time.perf_counter()-s0
        correct=sum(1 for i,j in enumerate(succ) if j>=0 and tr[i][0]==tr[int(j)][0] and tr[int(j)][1]==tr[i][1]+1)
        proposed=int((succ>=0).sum())
        # precision of proposed adjacencies
        stats[name]['adj'].append((correct, proposed, total_true))

print(f"pool = {NFILES} interleaved ZIPs, ~{n} fragments, {TRIALS} trials, identical affinity matrix\n")
print(f"{'solver':<11}{'correct links':>14}{'proposed':>10}{'true links':>12}{'precision':>11}{'recall':>9}{'ms/solve':>10}")
for k,v in stats.items():
    c=sum(a for a,_,_ in v['adj']); p=sum(b for _,b,_ in v['adj']); tt=sum(c2 for _,_,c2 in v['adj'])
    print(f"{k:<11}{c:>14}{p:>10}{tt:>12}{c/max(1,p):>11.3f}{c/max(1,tt):>9.3f}{v['t']/TRIALS*1000:>10.2f}")

import sys, time; sys.path.insert(0, r"A:\SIH\SIH_FORENSIC\backend")
import numpy as np
print("="*70); print("P1-4: deterministic gate routing on LLM/regex disagreement"); print("="*70)
from engine.llm_triage import triage_artifact, DeterministicPatternFilter
class StubLLM:
    def __init__(self, cat): self.cat=cat
    def classify(self, text): return {"category":self.cat,"priority":"P1_CRITICAL","plain_english_summary":"stub"}
class DeadLLM:
    def classify(self, text): raise FileNotFoundError("no gguf on this host")
txt = "Cardholder Ravi Kumar card 4111111111111111 exp 09/29 PAN ABCDE1234F"
f = DeterministicPatternFilter()
base = f.scan(txt)
print("deterministic baseline category:", base.baseline_category, "hits:", base.filter_hits[:4])
for name, llm in (("AGREEING LLM", StubLLM(base.baseline_category)),
                  ("DISAGREEING LLM", StubLLM("LOW_PRIORITY_GENERAL")),
                  ("UNAVAILABLE LLM", DeadLLM())):
    r = triage_artifact(txt, det_filter=f, llm=llm)
    print(f"  {name:<17} -> category={r['category']:<26} agreement={r['agreement']:<16} priority={r['priority']}")
r = triage_artifact("just a grocery list, milk and eggs", det_filter=f, llm=StubLLM("FINANCIAL_PII"))
print(f"  {'NO-HIT + LLM says PII':<17} -> category={r['category']:<26} agreement={r['agreement']}  (LLM never consulted)")

print(); print("="*70); print("P1-3: occlusion-attribution FAITHFULNESS test"); print("="*70)
from engine.explainability import generate_block_attributions, _get_session, _run_logits, DEFAULT_MODEL_PATH
from engine.pretrain_utils import BLOCK_SIZE
rng=np.random.default_rng(5)
import io
from PIL import Image
a=np.zeros((256,256,3),np.uint8)
for _ in range(30):
    x,y,w,h=rng.integers(0,240,4); a[y:y+h,x:x+w]=rng.integers(0,255,3)
b=io.BytesIO(); Image.fromarray(a).save(b,"JPEG",quality=90); blk=b.getvalue()[:BLOCK_SIZE]
STRIDE=64
attr=generate_block_attributions(blk, stride=STRIDE)
sess=_get_session(DEFAULT_MODEL_PATH)
base_in=(np.frombuffer(blk.ljust(BLOCK_SIZE,b"\0")[:BLOCK_SIZE],np.uint8).astype(np.float32)/255.0)
bl=_run_logits(sess,base_in.reshape(1,1,BLOCK_SIZE))[0]; pc=int(bl.argmax()); bs=float(bl[pc])
order=np.argsort(attr)[::-1]
def perturb_drop(segs):
    x=base_in.copy()
    for k in segs: x[k*STRIDE:(k+1)*STRIDE]=rng.random(STRIDE).astype(np.float32)
    return bs-float(_run_logits(sess,x.reshape(1,1,BLOCK_SIZE))[0][pc])
K=6
top=[int(i) for i in order[:K]]; bot=[int(i) for i in order[-K:]]
rand=[int(i) for i in rng.choice(len(attr),K,replace=False)]
dt,db,dr=perturb_drop(top),perturb_drop(bot),perturb_drop(rand)
print(f"  predicted class {pc}, base logit {bs:.4f}, {len(attr)} segments of {STRIDE}B")
print(f"  logit drop, randomising TOP-{K} attributed segments   : {dt:+.4f}")
print(f"  logit drop, randomising BOTTOM-{K} attributed segments: {db:+.4f}")
print(f"  logit drop, randomising {K} RANDOM segments           : {dr:+.4f}")
print(f"  VERDICT: {'FAITHFUL (top >> bottom)' if dt>db and dt>0 else 'DECORATIVE - perturbing important regions does not move the output'}")
print(f"  NOTE: method is occlusion saliency, NOT SHAP and NOT Grad-CAM (see explainability.py:3)")

print(); print("="*70); print("P1-6: CPU-only inference latency, measured"); print("="*70)
from engine.triage_scorer import FastBlockTriage
from engine.carver_ml import SiameseAdjacency
img=np.frombuffer(b"".join([blk.ljust(BLOCK_SIZE,b"\0")]*256),np.uint8).reshape(-1,BLOCK_SIZE)
t=FastBlockTriage(); t.scan(img[:8])
s0=time.perf_counter(); t.scan(img); d=time.perf_counter()-s0
print(f"  1D-CNN block triage : {d*1000:7.1f} ms for 256 blocks (1 MiB) = {d/256*1e6:6.1f} us/block  -> {1/(d/256)/1024*4096/1e6:.1f} MB/s")
sia=SiameseAdjacency(); frags=[img[i].tobytes() for i in range(32)]
sia.affinity_matrix(frags[:4])
s0=time.perf_counter(); sia.affinity_matrix(frags); d2=time.perf_counter()-s0
print(f"  Siamese adjacency   : {d2*1000:7.1f} ms for 32x32 pairs = {d2/(32*32)*1e6:6.1f} us/pair")
s0=time.perf_counter(); generate_block_attributions(blk, stride=64); d3=time.perf_counter()-s0
print(f"  occlusion attribution: {d3*1000:7.1f} ms per block (64 forward passes)")

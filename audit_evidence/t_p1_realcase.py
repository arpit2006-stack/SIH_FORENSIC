"""P1-1: real damaged_drive.raw case + A/B vs a NAIVE linear signature carver."""
import sys, hashlib, io; sys.path.insert(0, r"A:\SIH\SIH_FORENSIC\backend")
import numpy as np
from PIL import Image
from engine.pretrain_utils import BLOCK_SIZE
from engine.signature_carver import carve
from engine.graph_reassembly import validate_carve, GlobalFragmentResolver
from engine.carver_ml import SiameseAdjacency
from engine.api import verify_carved_file
from engine.report_gen import ForensicReliabilityScorer

raw = open(r"A:\SIH\SIH_FORENSIC\backend\demo_data\damaged_drive.raw","rb").read()
gt  = open(r"A:\SIH\SIH_FORENSIC\backend\demo_data\ground_truth\evidence_document.pdf","rb").read()
gt_sha = hashlib.sha256(gt).hexdigest()
print(f"image {len(raw)}B = {len(raw)//BLOCK_SIZE} blocks; ground-truth PDF {len(gt)}B sha256={gt_sha[:16]}")
img = np.frombuffer(raw[:len(raw)//BLOCK_SIZE*BLOCK_SIZE], np.uint8).reshape(-1, BLOCK_SIZE)

# ---------- BASELINE: naive linear carver (PhotoRec/foremost model) ----------
SIGS = {"image/jpeg":(b"\xff\xd8\xff", b"\xff\xd9"), "application/pdf":(b"%PDF-", b"%%EOF"),
        "application/zip":(b"PK\x03\x04", b"PK\x05\x06")}
print("\n--- BASELINE: naive linear header->footer carver ---")
naive=[]
for mime,(hdr,ftr) in SIGS.items():
    pos=0
    while True:
        h=raw.find(hdr,pos)
        if h<0: break
        f=raw.find(ftr,h+len(hdr))
        if f<0: pos=h+1; continue
        data=raw[h:f+len(ftr)]
        ok,why=verify_carved_file(data,mime)
        sha=hashlib.sha256(data).hexdigest()
        print(f"  {mime:<16} {len(data):>7}B openable={str(ok):<5} exact-match-GT={sha==gt_sha}  ({why[:34]})")
        naive.append((mime,ok,sha==gt_sha)); pos=f+len(ftr)
print(f"  baseline: {sum(1 for _,ok,_ in naive if ok)} openable, {sum(1 for _,_,e in naive if e)} byte-exact vs ground truth")

# ---------- FORENSIWIPE PIPELINE ----------
print("\n--- FORENSIWIPE: signature carve + coherence gate + Hungarian reassembly ---")
scorer=ForensicReliabilityScorer()
res=carve(img); valid,orphans=validate_carve(img,res,min_struct=0.85)
print(f"  carve: {len(res.streams)} streams -> {len(valid)} pass coherence gate, {len(orphans)} orphans")
emitted=[]
for s in valid:
    d=s.assemble(img); ok,why=verify_carved_file(d,s.mime); sc=scorer.score(data=d,mime=s.mime)
    if ok and sc.S>=0.65 and s.mime!="application/octet-stream":
        sha=hashlib.sha256(d).hexdigest()
        emitted.append((s.mime,len(d),sha,sha==gt_sha))
        print(f"  [straight] {s.mime:<16} {len(d):>7}B S={sc.S:.3f} exact-match-GT={sha==gt_sha}")
sia=SiameseAdjacency()
cand=[b for b in orphans if img[b].any()][:200]
if cand:
    ob=[img[b].tobytes() for b in cand]
    rr=GlobalFragmentResolver(siamese=sia).resolve(ob,mime=None)
    for ch in rr.chains:
        if not ch.mime or ch.mime=="application/octet-stream": continue
        d=ch.assemble(ob)
        if not d.strip(b"\x00") or len(d)<64: continue
        ok,why=verify_carved_file(d,ch.mime)
        sc=scorer.score(data=d,mime=ch.mime,fragments=ob,chain_order=ch.order,chain_residual=ch.residual,siamese=sia)
        if ok and sc.S>=0.65:
            sha=hashlib.sha256(d).hexdigest()
            emitted.append((ch.mime,len(d),sha,sha==gt_sha))
            print(f"  [reassem]  {ch.mime:<16} {len(d):>7}B S={sc.S:.3f} blocks={len(ch.order)} exact-match-GT={sha==gt_sha}")
        else:
            print(f"  [rejected] {ch.mime:<16} {len(d):>7}B S={sc.S:.3f} openable={ok} ({why[:30]})")
print(f"\n  RESULT: forensiwipe emitted {len(emitted)} certified files; "
      f"{sum(1 for *_,e in emitted if e)} byte-identical to the ground-truth PDF")
print(f"  README/case-study claim: '100% of fragmented artifacts reassembled', 'PhotoRec 0% usable'")

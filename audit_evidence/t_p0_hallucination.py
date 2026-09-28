"""P0-6: anti-hallucination. Feed images with (A) an unrecoverable gap and
(B) two interleaved source JPEGs, and see what the pipeline certifies."""
import sys, io, hashlib, os, shutil, json
sys.path.insert(0, r"A:\SIH\SIH_FORENSIC\backend")
import numpy as np
from PIL import Image
from engine.pretrain_utils import BLOCK_SIZE
from engine.signature_carver import carve
from engine.graph_reassembly import validate_carve
from engine.api import verify_carved_file
from engine.report_gen import ForensicReliabilityScorer

rng = np.random.default_rng(7)

def make_jpeg(seed, size=(320,320)):
    a = np.zeros((size[1],size[0],3), np.uint8)
    r = np.random.default_rng(seed)
    for _ in range(40):
        x,y,w,h = r.integers(0,300,4)
        a[y:y+h, x:x+w] = r.integers(0,255,3)
    buf = io.BytesIO(); Image.fromarray(a).save(buf,"JPEG",quality=92)
    return buf.getvalue()

def to_blocks(b):
    n=(len(b)+BLOCK_SIZE-1)//BLOCK_SIZE
    return [b[i*BLOCK_SIZE:(i+1)*BLOCK_SIZE].ljust(BLOCK_SIZE,b"\x00") for i in range(n)]

j1, j2 = make_jpeg(1), make_jpeg(2)
b1, b2 = to_blocks(j1), to_blocks(j2)
print(f"source jpeg1 {len(j1)}B / {len(b1)} blocks   jpeg2 {len(j2)}B / {len(b2)} blocks")
print(f"  jpeg1 sha256 {hashlib.sha256(j1).hexdigest()[:16]}")

# ---------- SCENARIO A: unrecoverable gap (middle blocks destroyed) ----------
gA = list(b1)
hole = slice(len(b1)//3, len(b1)//3+3)
destroyed = gA[hole]
gA[hole] = [bytes(rng.integers(0,256,BLOCK_SIZE,dtype=np.uint8)) for _ in range(3)]
imgA = np.frombuffer(b"".join([b"\x00"*BLOCK_SIZE]*4 + gA + [b"\x00"*BLOCK_SIZE]*4), np.uint8).reshape(-1,BLOCK_SIZE)

# ---------- SCENARIO B: two JPEGs interleaved, headers present ----------
inter=[]
for i in range(max(len(b1),len(b2))):
    if i < len(b1): inter.append(b1[i])
    if i < len(b2): inter.append(b2[i])
imgB = np.frombuffer(b"".join([b"\x00"*BLOCK_SIZE]*4 + inter + [b"\x00"*BLOCK_SIZE]*4), np.uint8).reshape(-1,BLOCK_SIZE)

scorer = ForensicReliabilityScorer()
for name, img, truth in (("A: JPEG with 3 destroyed middle blocks", imgA, {hashlib.sha256(j1).hexdigest()}),
                         ("B: two JPEGs block-interleaved",         imgB, {hashlib.sha256(j1).hexdigest(), hashlib.sha256(j2).hexdigest()})):
    print(f"\n===== SCENARIO {name} =====")
    res = carve(img)
    valid, orphans = validate_carve(img, res, min_struct=0.85)
    print(f"  carve -> {len(res.streams)} raw streams; after coherence gate: {len(valid)} valid, {len(orphans)} orphans")
    emitted=0
    for s in valid:
        raw = s.assemble(img)
        ok, why = verify_carved_file(raw, s.mime)
        sc = scorer.score(data=raw, mime=s.mime)
        gate = ok and sc.S >= 0.65 and s.mime != "application/octet-stream"
        h = hashlib.sha256(raw).hexdigest()
        exact = h in truth
        if gate: emitted+=1
        print(f"   stream mime={s.mime} bytes={len(raw)} openable={ok}({why[:30]}) S={sc.S:.3f} "
              f"EMITTED={gate} byte-identical-to-a-real-source={exact}")
        if gate and not exact:
            print(f"     ^^ EMITTED AS 'OPEN_VERIFIED' BUT NOT BYTE-IDENTICAL TO ANY REAL SOURCE FILE")
    print(f"  files the pipeline would write & certify: {emitted}")

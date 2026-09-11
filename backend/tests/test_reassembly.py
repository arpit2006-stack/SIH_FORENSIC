"""Node 03 verification: real JPEG + real PDF, each split into 10 disjoint 4KB fragments,
shuffled, pooled together (20 orphans), and reordered by GlobalFragmentResolver.

Run: python -m tests.test_reassembly
"""
from __future__ import annotations

import io
import logging

import numpy as np
from PIL import Image

from engine.carver_ml import SiameseAdjacency, ensure_siamese_model, validate_structural_coherence
from engine.graph_reassembly import GlobalFragmentResolver, validate_carve
from engine.pretrain_utils import BLOCK_SIZE, SyntheticFragmentCorpus
from engine.signature_carver import carve

N_FRAGS = 10
TARGET = N_FRAGS * BLOCK_SIZE


def make_jpeg(rng: np.random.Generator) -> bytes:
    """Real baseline JPEG with restart markers, sized to fill exactly 10 blocks (last one padded)."""
    for side in range(96, 2048, 16):
        img = Image.fromarray(rng.integers(0, 256, (side, side, 3), dtype=np.uint8))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85, restart_marker_blocks=4)
        d = buf.getvalue()
        if TARGET - BLOCK_SIZE < len(d) <= TARGET:
            return d
    raise RuntimeError("could not size jpeg")


def make_pdf(rng: np.random.Generator) -> bytes:
    """Real PDF: sequential objects, correct xref offsets, startxref, %%EOF. ~10 blocks."""
    import zlib
    objs: list[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [] /Count 0 >>"]
    words = [b"forensic", b"evidence", b"ledger", b"transfer", b"account", b"2026", b"INR", b"invoice"]
    while True:
        body = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
        offsets = []
        for i, o in enumerate(objs, start=1):
            offsets.append(len(body))
            body += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
        xref_at = len(body)
        body += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
        body += b"".join(f"{off:010d} 00000 n \n".encode() for off in offsets)
        body += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n").encode()
        if TARGET - BLOCK_SIZE < len(body) <= TARGET:
            return body
        if len(body) > TARGET:
            objs.pop()
            objs.append(b"<< /Type /Annot >>")
            continue
        text = b" ".join(words[k] for k in rng.integers(0, len(words), 120))
        if rng.random() < 0.5:
            stream = zlib.compress(text)
            objs.append(f"<< /Length {len(stream)} /Filter /FlateDecode >>\nstream\n".encode() + stream + b"\nendstream")
        else:
            objs.append(b"<< /Type /Text /Contents (" + text + b") >>")


def split_shuffled(files: list[bytes], rng: np.random.Generator):
    frags, truth = [], []
    for fid, f in enumerate(files):
        blocks = SyntheticFragmentCorpus.blockify(f)
        assert len(blocks) == N_FRAGS, (fid, len(blocks))
        for k, b in enumerate(blocks):
            frags.append(b.tobytes())
            truth.append((fid, k))
    perm = rng.permutation(len(frags))
    return [frags[i] for i in perm], [truth[i] for i in perm]


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    rng = np.random.default_rng(2026)
    jpeg, pdf = make_jpeg(rng), make_pdf(rng)
    print(f"fixtures: jpeg={len(jpeg)}B pdf={len(pdf)}B  ({N_FRAGS} blocks each)")

    # FR2.1 sanity on real files: valid high, structurally broken low.
    for name, d, mime in (("jpeg", jpeg, "image/jpeg"), ("pdf", pdf, "application/pdf")):
        blocks = SyntheticFragmentCorpus.blockify(d)
        shuffled = b"".join(blocks[i].tobytes() for i in [0, 5, 3, 8, 1, 9, 2, 7, 4, 6])
        ok, bad = validate_structural_coherence(d, mime), validate_structural_coherence(shuffled, mime)
        print(f"  C_struct {name}: valid={ok:.3f} shuffled={bad:.3f}")
        assert ok > 0.9 > bad, (name, ok, bad)

    # FR2.0 -> FR2.1: in a shuffled image any stream the signature carver closes is wrong;
    # C_struct validation must demote every block to the orphan pool.
    frags, truth = split_shuffled([jpeg, pdf], rng)
    image = np.stack([np.frombuffer(f, np.uint8) for f in frags])
    cr = carve(image)
    valid, orphans = validate_carve(image, cr)
    assert not valid and orphans == list(range(2 * N_FRAGS)), (valid, orphans)
    print(f"  signature carver: {len(cr.header_blocks)} headers, {len(cr.footer_blocks)} footers, "
          f"{sum(s.closed for s in cr.streams)} closed streams rejected by C_struct, "
          f"{len(orphans)} orphans handed to the resolver")

    # FR2.2 + FR2.3: mixed pool of 20 orphans -> two chains
    ensure_siamese_model()
    sia = SiameseAdjacency()
    resolver = GlobalFragmentResolver(alpha=0.7, beta=0.3, siamese=sia)
    res = resolver.resolve(frags)
    assert len(res.chains) >= 2, [c.order for c in res.chains]
    recovered = {}
    for c in res.chains[:2]:
        seq = [truth[i] for i in c.order]
        fid = seq[0][0]
        print(f"  chain mime={c.mime} len={len(seq)} residual={c.residual:.3f} order={[k for _, k in seq]}")
        assert all(f == fid for f, _ in seq), "chain mixes files"
        assert [k for _, k in seq] == list(range(N_FRAGS)), "wrong block order"
        recovered[fid] = c.assemble(frags)
    assert recovered[0][:len(jpeg)] == jpeg and recovered[1][:len(pdf)] == pdf
    assert Image.open(io.BytesIO(recovered[0][:len(jpeg)])).size[0] > 0  # decodes
    # Output bytes are a permutation of input bytes: nothing synthesised.
    assert sorted(b"".join(recovered.values())) == sorted(b"".join(frags))
    print("  reassembled JPEG re-decodes; output bytes are a permutation of input bytes")

    # Not seed luck: repeat on fresh fixtures.
    wins = 0
    for seed in (1, 7, 42, 99, 555, 888, 31337):
        r2 = np.random.default_rng(seed)
        fs, tr = split_shuffled([make_jpeg(r2), make_pdf(r2)], r2)
        perfect = sum(1 for c in resolver.resolve(fs).chains
                      if len(c.order) == N_FRAGS
                      and [tr[i] for i in c.order] == [(tr[c.order[0]][0], k) for k in range(N_FRAGS)])
        wins += perfect == 2
    print(f"  seed sweep: {wins}/7 additional seeds reconstructed both files exactly")
    assert wins == 7

    # Pool cap + pruning: a 500-block pool must solve without an O(N^2) SHT sweep, and a
    # pool larger than the cap must be sliced rather than allocated whole.
    import time
    pool500 = [f for _ in range(25) for f in frags]
    assert len(pool500) == 500
    t0 = time.perf_counter()
    res500 = GlobalFragmentResolver(alpha=0.7, beta=0.3, siamese=sia, top_k=16).resolve(pool500)
    print(f"  500-block pool solved in {time.perf_counter() - t0:.1f}s -> {len(res500.chains)} chains, "
          f"affinity {res500.affinity.nbytes / 2**20:.1f}MiB")
    assert res500.affinity.shape == (500, 500)
    sliced = GlobalFragmentResolver(alpha=1.0, beta=0.0, max_pool=20).resolve(frags * 3)
    assert all(i < 60 for c in sliced.chains for i in c.order)
    print(f"  pool cap: 60 fragments sliced at 20 -> {len(sliced.chains)} chains, indices remapped")

    # mmap hygiene: the map is closed on exit and the file is immediately re-openable/removable.
    import os
    import tempfile
    from engine.signature_carver import open_image_blocks
    path = os.path.join(tempfile.gettempdir(), "forensiwipe_mmap_probe.bin")
    with open(path, "wb") as fh:
        fh.write(b"".join(frags))
    with open_image_blocks(path) as img:
        assert img.shape == (2 * N_FRAGS, BLOCK_SIZE)
        leaked = img[0]                 # indexing yields a copy, so this cannot pin the map
        assert img.batch(0, 4).shape == (4, BLOCK_SIZE)
        from_disk = carve(img.batch(0, len(img)))
        assert [s.blocks for s in from_disk.streams] == [s.blocks for s in cr.streams]
    assert bytes(leaked) == frags[0]    # still readable after close: it was never a view
    os.remove(path)                     # would raise WinError 32 if the mmap leaked
    print("  mmap released cleanly; image file removable straight after the context exits")
    print("OK: JPEG and PDF fully reordered from a mixed 20-fragment pool; bytes are source-only")


if __name__ == "__main__":
    main()

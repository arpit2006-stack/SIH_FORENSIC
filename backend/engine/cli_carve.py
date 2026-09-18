"""Command-Line Forensic Carving Tool (PS Req 3).

Executes non-invasive forensic carving over physical drives (\\\\.\\D:),
raw disk images (.dd/.raw), or synthetic fragmented test corpuses.

Features:
- Magic-byte header/trailer deterministic carving (FR2.0)
- Hungarian Algorithm + SHT Adjacency fragment reassembly (FR2.2)
- Evidential reliability scoring (FR2.4)
- Section 63 BSA Digital Evidence SHA-256 chain of custody logging
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import numpy as np

from engine.signature_carver import BLOCK_SIZE, carve, detect_header, find_footer
from engine.graph_reassembly import GlobalFragmentResolver
from engine.report_gen import ForensicReliabilityScorer
from engine.pretrain_utils import SyntheticFragmentCorpus, _make_jpeg, _make_pdf, _make_zip


def create_synthetic_corpus() -> tuple[np.ndarray, dict[str, bytes]]:
    """Creates a controlled benchmark with contiguous and fragmented files."""
    rng = np.random.default_rng(42)
    f_jpg = _make_jpeg(rng, 4 * BLOCK_SIZE)
    f_pdf = _make_pdf(rng, 5 * BLOCK_SIZE)
    f_zip = _make_zip(rng, 3 * BLOCK_SIZE)

    b_jpg = SyntheticFragmentCorpus.blockify(f_jpg)
    b_pdf = SyntheticFragmentCorpus.blockify(f_pdf)
    b_zip = SyntheticFragmentCorpus.blockify(f_zip)

    # Interleave PDF and JPEG to test Hungarian graph reassembly
    # Block 0: Empty padding
    # Blocks 1-2: JPEG head
    # Blocks 3-4: PDF head
    # Blocks 5-6: JPEG tail
    # Blocks 7-9: PDF tail
    # Blocks 10-12: Contiguous ZIP
    image_blocks = [
        np.zeros((1, BLOCK_SIZE), dtype=np.uint8),
        b_jpg[:2],
        b_pdf[:2],
        b_jpg[2:],
        b_pdf[2:],
        b_zip,
        np.zeros((2, BLOCK_SIZE), dtype=np.uint8),
    ]
    image = np.concatenate(image_blocks, axis=0)
    return image, {"jpeg": f_jpg, "pdf": f_pdf, "zip": f_zip}


def carve_target(
    target: str,
    max_blocks: int = 10000,
    output_dir: str = "./carved_output",
    deep_ml: bool = True,
    case_id: str = "CAS-CARVE-01",
    investigator: str = "OFFICER-01",
) -> int:
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    print("=" * 68)
    print(" FORENSIWIPE ADVANCED CARVING & FRAGMENT REASSEMBLY ENGINE")
    print(f" Case ID:       {case_id}")
    print(f" Examiner:      {investigator}")
    print(f" Target Source: {target}")
    print("=" * 68)

    t0 = time.time()
    image: np.ndarray

    if target.upper() == "DEMO" or target == "":
        print("\n[+] Mode: Controlled Synthetic Benchmark (Fragmented Interleaved Corpus)")
        image, ground_truth = create_synthetic_corpus()
        print(f"    Loaded {len(image)} blocks ({len(image) * BLOCK_SIZE:,} bytes)")
    elif os.path.isfile(target):
        print(f"\n[+] Ingesting raw image file: {target}")
        raw = Path(target).read_bytes()
        n = min(len(raw) // BLOCK_SIZE, max_blocks)
        image = np.frombuffer(raw[: n * BLOCK_SIZE], dtype=np.uint8).reshape(n, BLOCK_SIZE)
        print(f"    Ingested {n} blocks ({n * BLOCK_SIZE:,} bytes)")
    else:
        # Physical drive or volume device (e.g. \\.\D:)
        print(f"\n[+] Ingesting raw sector stream from device: {target}")
        print(f"    Reading up to {max_blocks:,} blocks ({max_blocks * BLOCK_SIZE / (1024*1024):.1f} MB)...")
        blocks_list = []
        try:
            with open(target, "rb") as dev:
                for idx in range(max_blocks):
                    chunk = dev.read(BLOCK_SIZE)
                    if not chunk or len(chunk) < BLOCK_SIZE:
                        break
                    blocks_list.append(np.frombuffer(chunk, dtype=np.uint8))
                    if (idx + 1) % 5000 == 0:
                        mb = (idx + 1) * BLOCK_SIZE / (1024 * 1024)
                        print(f"    ... ingested {idx + 1:,} blocks ({mb:.1f} MB)", end="\r")
            if len(blocks_list) >= 5000:
                print()  # Newline after progress
        except PermissionError:
            print(f"\n[!] PERMISSION DENIED accessing {target}.")
            print("    Please run PowerShell / Terminal as Administrator to access raw devices.")
            return 1
        except Exception as err:
            print(f"\n[!] Error reading from device {target}: {err}")
            return 1

        if not blocks_list:
            print("\n[!] No data could be read from target.")
            return 1

        image = np.stack(blocks_list)
        print(f"    Successfully ingested {len(image)} blocks ({len(image) * BLOCK_SIZE:,} bytes)")

    # Phase 2: Deterministic Signature Carving
    print("\n[*] Phase 2: Scanning magic bytes (Headers & Trailers)...")
    carve_res = carve(image)
    print(f"    Straight streams found:   {len(carve_res.streams)}")
    print(f"    Candidate orphan blocks:  {len(carve_res.orphans)}")

    recovered: list[dict] = []
    scorer = ForensicReliabilityScorer()
    file_counter = 1

    # Extract straight streams
    for s in carve_res.streams:
        data = s.assemble(image)
        sha = hashlib.sha256(data).hexdigest()
        score = scorer.score(data=data, mime=s.mime)

        ext = s.mime.split("/")[-1]
        if ext == "jpeg":
            ext = "jpg"
        fname = f"carved_{file_counter:03d}_{s.blocks[0]:05d}.{ext}"
        save_file = out_path / fname
        save_file.write_bytes(data)

        recovered.append({
            "id": f"REC-{file_counter:03d}",
            "filename": fname,
            "mime": s.mime,
            "blocks": len(s.blocks),
            "size_bytes": len(data),
            "start_block": s.blocks[0],
            "start_offset": s.blocks[0] * BLOCK_SIZE,
            "reliability_score": round(score.S, 3),
            "sha256": sha,
            "type": "CONTIGUOUS",
        })
        file_counter += 1

    # Phase 3: Hungarian Graph Reassembly for Orphans
    if deep_ml and carve_res.orphans:
        print("\n[*] Phase 3: Running Hungarian Graph Reassembly on orphan blocks...")
        try:
            resolver = GlobalFragmentResolver()
            orphan_bytes = [image[b].tobytes() for b in carve_res.orphans]
            res_result = resolver.resolve(orphan_bytes, mime=None)
            print(f"    Reassembled {len(res_result.chains)} fragmented file chains.")

            for chain in res_result.chains:
                data = chain.assemble(orphan_bytes)
                # Skip pure unwritten null blocks (all zeros)
                if not data.strip(b"\x00"):
                    continue

                sha = hashlib.sha256(data).hexdigest()
                mime = chain.mime or "application/octet-stream"
                score = scorer.score(data=data, mime=mime)

                ext = mime.split("/")[-1]
                if ext == "jpeg":
                    ext = "jpg"
                fname = f"reassembled_{file_counter:03d}_{carve_res.orphans[chain.order[0]]:05d}.{ext}"
                save_file = out_path / fname
                save_file.write_bytes(data)

                recovered.append({
                    "id": f"REC-{file_counter:03d}",
                    "filename": fname,
                    "mime": mime,
                    "blocks": len(chain.order),
                    "size_bytes": len(data),
                    "start_block": carve_res.orphans[chain.order[0]],
                    "start_offset": carve_res.orphans[chain.order[0]] * BLOCK_SIZE,
                    "reliability_score": round(score.S, 3),
                    "sha256": sha,
                    "type": "REASSEMBLED (HUNGARIAN)",
                })
                file_counter += 1
        except Exception as err:
            print(f"    [!] Reassembly notice: {err}")

    elapsed = time.time() - t0

    # Summary table
    print("\n" + "=" * 80)
    print(f"{'ID':<9} {'TYPE':<22} {'MIME':<18} {'SIZE':<10} {'SCORE':<7} {'START OFFSET'}")
    print("-" * 80)
    for r in recovered:
        print(f"{r['id']:<9} {r['type']:<22} {r['mime']:<18} {r['size_bytes']:<10} {r['reliability_score']:<7} {r['start_offset']:,} B")
    print("=" * 80)

    # Section 63 BSA Chain of Custody Log
    cert_path = out_path / "section_63_bsa_audit.json"
    audit_record = {
        "court_certification": "Section 63 Bharatiya Sakshya Adhiniyam, 2023",
        "case_id": case_id,
        "investigator": investigator,
        "target_media": target,
        "blocks_analyzed": len(image),
        "total_bytes_analyzed": len(image) * BLOCK_SIZE,
        "files_recovered_count": len(recovered),
        "execution_duration_sec": round(elapsed, 2),
        "recovered_evidence": recovered,
        "custody_hash": hashlib.sha256(json.dumps(recovered, sort_keys=True).encode()).hexdigest(),
    }
    cert_path.write_text(json.dumps(audit_record, indent=2))

    print(f"\n[+] Carving Complete in {elapsed:.2f}s!")
    print(f"[+] Total Files Recovered: {len(recovered)}")
    print(f"[+] Extracted files saved to: {out_path.resolve()}")
    print(f"[+] Section 63 BSA Evidence Log: {cert_path.resolve()}\n")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ForensiWipe — Deep Forensic Carving & Reassembly CLI"
    )
    parser.add_argument(
        "--target",
        default="DEMO",
        help="Target drive (e.g. \\\\.\\D:), raw image file, or DEMO for synthetic benchmark (default: DEMO)",
    )
    parser.add_argument(
        "--blocks",
        type=int,
        default=5000,
        help="Number of 4KB blocks to analyze from drive (default: 5000 = ~20 MB)",
    )
    parser.add_argument(
        "--output-dir",
        default="./carved_evidence",
        help="Directory where recovered files and certificates will be saved",
    )
    parser.add_argument(
        "--case-id",
        default="CAS-2026-SEAGATE",
        help="Forensic Case Identifier",
    )
    parser.add_argument(
        "--no-ml",
        action="store_true",
        help="Disable Hungarian graph reassembly on fragments",
    )

    args = parser.parse_args()
    return carve_target(
        target=args.target,
        max_blocks=args.blocks,
        output_dir=args.output_dir,
        deep_ml=not args.no_ml,
        case_id=args.case_id,
    )


if __name__ == "__main__":
    sys.exit(main())

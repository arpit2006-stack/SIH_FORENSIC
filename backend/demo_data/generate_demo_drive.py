"""Generates a realistic corrupted forensic disk image for ForensiWipe end-to-end demo.

Creates:
1. damaged_drive.raw (160KB forensic bitstream disk image)
   - Fragmented JPEG (split across sectors 2 and 6)
   - Fragmented PDF (split across sectors 4 and 8)
   - Contiguous ZIP archive (sectors 9-11)
   - Unallocated slack with sensitive PII / credential leaks (sector 5)
   - Wipable orphan sectors (sectors 12-19)
2. ground_truth/ folder with original reference files for automated verification
"""

import io
import os
import sys
import zipfile
from pathlib import Path
import numpy as np
from PIL import Image

BLOCK_SIZE = 4096


def generate_valid_jpeg() -> bytes:
    """Creates a real, 100% valid JPEG image that passes PIL pixel decoding."""
    img = Image.new("RGB", (320, 240), color=(30, 80, 160))
    buf = io.BytesIO()
    # High quality to ensure it spans across multiple 4KB blocks
    img.save(buf, format="JPEG", quality=95)
    raw = buf.getvalue()
    # Pad to at least 2 blocks so fragmentation can be demonstrated
    if len(raw) < BLOCK_SIZE * 2:
        # Create larger image
        img = Image.new("RGB", (640, 480), color=(40, 100, 200))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        raw = buf.getvalue()
    return raw


def generate_valid_pdf() -> bytes:
    """Creates a valid PDF document with realistic text content."""
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length 180 >>\nstream\n"
        b"BT /F1 18 Tf 50 700 Td (FORENSIWIPE DIGITAL EVIDENCE RECORD - CASE #2026-904) Tj ET\n"
        b"BT /F1 12 Tf 50 660 Td (SUSPECT FINANCIAL DISCLOSURE - CONFIDENTIAL CBI/NIA PROBE) Tj ET\n"
        b"endstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    )
    # Ensure it spans multiple blocks by adding metadata padding
    padding = b"6 0 obj\n<< /Note (" + (b"CLASSIFIED EVIDENCE RECORD " * 200) + b") >>\nendobj\n"
    trailer = (
        b"xref\n0 7\n"
        b"0000000000 65535 f \n"
        b"0000000010 00000 n \n"
        b"0000000060 00000 n \n"
        b"0000000120 00000 n \n"
        b"0000000230 00000 n \n"
        b"0000000460 00000 n \n"
        b"0000000540 00000 n \n"
        b"trailer\n<< /Size 7 /Root 1 0 R >>\nstartxref\n5800\n%%EOF\n"
    )
    return pdf_content + padding + trailer


def generate_valid_zip() -> bytes:
    """Creates a valid ZIP archive containing evidence documents."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("case_manifest.txt", "CASE: CAS-2026-904\nTARGET: Hawala Ledger Exfiltration\nTIMESTAMP: 2026-09-25T14:30:00Z\n")
        zf.writestr("accounts.csv", "ID,NAME,ACCOUNT,IFSC,AMOUNT\n1,R. Sharma,40992384910,SBIN0001234,4500000\n2,V. Gupta,50293819203,HDFC0000456,12000000\n")
    return buf.getvalue()


def blockify(data: bytes) -> list[bytes]:
    """Splits bytes into 4096-byte blocks, zero-padding the last block."""
    blocks = []
    for i in range(0, len(data), BLOCK_SIZE):
        chunk = data[i : i + BLOCK_SIZE]
        if len(chunk) < BLOCK_SIZE:
            chunk = chunk + b"\x00" * (BLOCK_SIZE - len(chunk))
        blocks.append(chunk)
    return blocks


def create_demo_corpus(base_dir: str | Path | None = None) -> tuple[Path, Path]:
    if base_dir is None:
        base_dir = Path(__file__).resolve().parent
    else:
        base_dir = Path(base_dir)

    ground_truth_dir = base_dir / "ground_truth"
    ground_truth_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate pristine ground truth files
    jpeg_data = generate_valid_jpeg()
    pdf_data = generate_valid_pdf()
    zip_data = generate_valid_zip()

    (ground_truth_dir / "evidence_photo.jpg").write_bytes(jpeg_data)
    (ground_truth_dir / "evidence_document.pdf").write_bytes(pdf_data)
    (ground_truth_dir / "evidence_records.zip").write_bytes(zip_data)

    jpeg_blocks = blockify(jpeg_data)
    pdf_blocks = blockify(pdf_data)
    zip_blocks = blockify(zip_data)

    # 2. Build 60-block (240KB) damaged disk image
    total_blocks = 60
    disk_blocks = [b"\x00" * BLOCK_SIZE for _ in range(total_blocks)]

    # Sector 0: Corrupted partition table header simulation
    mbr = bytearray(BLOCK_SIZE)
    mbr[0:4] = b"\xEB\x58\x90\x00"
    mbr[510:512] = b"\x55\xAA"
    disk_blocks[0] = bytes(mbr)

    # Sector 1: File system slack (wiped)
    disk_blocks[1] = b"\x00" * BLOCK_SIZE

    # PDF Head -> Sector 4
    disk_blocks[4] = pdf_blocks[0]

    # Sector 8: Unallocated slack with sensitive plain text leak
    leak = (
        b"CONFIDENTIAL INTELLIGENCE DOSSIER - OPERATION TRIDENT\n"
        b"PRIMARY TARGET PAN: ABCDE1234F | AADHAAR: 9821 4452 1109\n"
        b"SETTLEMENT ACCOUNT IFSC: SBIN0001234 | UPI: target99@okaxis\n"
        b"TRANSACTION LEDGER: TXN99420489 - DEBIT INR 85,00,000 APPROVED.\n"
    )
    disk_blocks[8] = leak.ljust(BLOCK_SIZE, b"\x00")

    # PDF Continuation/Tail -> Sector 12 (FRAGMENTED from Sector 4 across 7 sectors)
    if len(pdf_blocks) > 1:
        disk_blocks[12] = pdf_blocks[1]

    # JPEG Head -> Sector 16
    disk_blocks[16] = jpeg_blocks[0]

    # Sector 18: Random high-entropy orphan sector
    rng = np.random.default_rng(1337)
    disk_blocks[18] = rng.integers(0, 256, BLOCK_SIZE, dtype=np.uint8).tobytes()

    # JPEG Continuation/Tail -> Sector 22 (FRAGMENTED from Sector 16 across 5 sectors)
    if len(jpeg_blocks) > 1:
        disk_blocks[22] = jpeg_blocks[1]

    # Contiguous ZIP -> Sectors 28, 29, 30
    for idx, zb in enumerate(zip_blocks[:3]):
        disk_blocks[28 + idx] = zb

    # Sectors 36 to 50: Sensitive obsolete residual evidence to be purged
    for s in range(36, 51):
        disk_blocks[s] = (f"OBSOLETE RESIDUAL CONTAMINATED SECTOR #{s:03d} - PURGE REQUIRED ".encode("utf-8") * 60)[:BLOCK_SIZE]


    # Write out raw image
    raw_img_path = base_dir / "damaged_drive.raw"
    with open(raw_img_path, "wb") as f:
        for blk in disk_blocks:
            f.write(blk)

    print(f"[+] Demo damaged drive image created: {raw_img_path} ({len(disk_blocks) * BLOCK_SIZE} bytes, {total_blocks} sectors)")
    print(f"[+] Ground truth files stored in: {ground_truth_dir}")
    return raw_img_path, ground_truth_dir


if __name__ == "__main__":
    create_demo_corpus()

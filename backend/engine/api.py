"""REST API Router for Advanced File Carving and Reconstruction (PS Req 3).

Exposes RESTful endpoints for:
- POST /api/carving/start         : Start carving job on physical drive / disk image / demo target
- GET  /api/carving/:id/status    : Retrieve live scanning telemetry and progress
- GET  /api/carving/:id/results   : Retrieve carved streams, MIME types, and reliability score S
- GET  /api/carving/:id/report    : Retrieve Section 63 BSA legal certificate
- POST /api/carving/demo-setup    : Create an offline synthetic forensic drive image for testing
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import time
import uuid
import urllib.parse
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from engine.pretrain_utils import BLOCK_SIZE
from engine.triage_scorer import FastBlockTriage, NOISE_IDX
from engine.signature_carver import carve, Stream
from engine.graph_reassembly import GlobalFragmentResolver, validate_carve
from engine.report_gen import (
    ForensicReliabilityScorer,
    CertificateData,
    BSASection63CertificateGenerator,
    ScoreBreakdown,
)


def verify_carved_file(data: bytes, mime: str) -> tuple[bool, str]:
    """Forensic verification gate ensuring carved bytes constitute an openable, uncorrupted file."""
    if not data or len(data) < 32:
        return False, "Insufficient data length"
    try:
        if mime == "image/jpeg":
            if not data.startswith(b"\xff\xd8"):
                return False, "Missing JPEG SOI marker"
            # 1. Structural marker check
            with Image.open(io.BytesIO(data)) as im:
                im.verify()
            # 2. Decompression check (verifies entropy-coded raster data without broken stream error)
            with Image.open(io.BytesIO(data)) as im:
                im.load()
            return True, "Valid JPEG image structure"

        elif mime == "application/zip":
            if not data.startswith(b"PK\x03\x04"):
                return False, "Missing PK\\x03\\x04 ZIP header"
            with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
                info_list = zf.infolist()
                if len(info_list) == 0:
                    return False, "Empty or partial ZIP archive (no member files)"
                bad_crc = zf.testzip()
                if bad_crc is not None:
                    return False, f"ZIP CRC checksum mismatch on {bad_crc}"
            return True, "Valid ZIP archive structure"

        elif mime == "application/pdf":
            if not data.startswith(b"%PDF-"):
                return False, "Missing %PDF header"
            # Terminal %%EOF trailer check within the last 1024 bytes of trimmed data
            eof_pos = data.rfind(b"%%EOF")
            if eof_pos < 0 or (len(data) - eof_pos) > 1024:
                return False, "Missing or misplaced terminal %%EOF trailer"
            # Essential cross-reference and catalog checks
            if b"xref" not in data and b"/XRef" not in data:
                return False, "Missing PDF cross-reference table/stream"
            if b"/Root" not in data and b"/Catalog" not in data:
                return False, "Missing PDF document catalog dictionary"
            return True, "Valid PDF document structure"

        # Explicitly reject unverified/unsupported binary streams
        return False, f"Unverified format: {mime} is not a certified target MIME type"

    except Exception as err:
        return False, f"Structure validation error: {err}"


@dataclass
class CarvedFileSummary:
    file_id: str
    mime: str
    block_count: int
    size_bytes: int
    is_closed: bool
    reliability_score: float
    score_breakdown: dict[str, float]
    triage_priority: str
    sha256: str
    offset_bytes: int
    filename: str = ""
    saved_path: str = ""
    is_verified: bool = True
    validation_status: str = "OPEN_VERIFIED"


@dataclass
class CarvingJob:
    job_id: str
    case_id: str
    investigator: str
    target_path: str
    status: str  # QUEUED, SCANNING, REASSEMBLING, COMPLETED, FAILED
    progress_percent: int
    total_blocks: int
    blocks_scanned: int
    orphans_count: int
    files_recovered: list[CarvedFileSummary] = field(default_factory=list)
    certificate_id: str | None = None
    certificate_pdf_path: str | None = None
    output_dir: str | None = None
    source_description: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


class CarvingApiRouter:
    """Dispatches Carving, ML Reassembly, and Evidence Certification API requests."""

    def __init__(self):
        self.jobs: dict[str, CarvingJob] = {}
        self.scorer = ForensicReliabilityScorer()
        self._triage: FastBlockTriage | None = None

    def _get_triage(self) -> FastBlockTriage:
        if self._triage is None:
            self._triage = FastBlockTriage()
        return self._triage

    def _create_synthetic_forensic_image(self) -> np.ndarray:
        """Create an in-memory 100-block synthetic disk image with fragmented JPEG and PDF."""
        rng = np.random.default_rng(42)
        total_blocks = 60
        image = np.zeros((total_blocks, BLOCK_SIZE), dtype=np.uint8)

        # 1. Create a continuous JPEG
        try:
            img = Image.fromarray(rng.integers(0, 256, (128, 128, 3), dtype=np.uint8))
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=75)
            jpeg_bytes = buf.getvalue()
            n_blks = (len(jpeg_bytes) + BLOCK_SIZE - 1) // BLOCK_SIZE
            for i in range(n_blks):
                chunk = jpeg_bytes[i * BLOCK_SIZE : (i + 1) * BLOCK_SIZE]
                image[5 + i, : len(chunk)] = np.frombuffer(chunk, dtype=np.uint8)
        except Exception:
            pass

        # 2. Create a fragmented PDF (Header at block 12, Body at block 25, Trailer at block 30)
        try:
            from engine.pretrain_utils import _make_pdf
            pdf_bytes = _make_pdf(rng, 10_000)
            n_pdf = (len(pdf_bytes) + BLOCK_SIZE - 1) // BLOCK_SIZE
            pdf_blks = [pdf_bytes[i * BLOCK_SIZE : (i + 1) * BLOCK_SIZE] for i in range(n_pdf)]
            if n_pdf >= 3:
                image[12, : len(pdf_blks[0])] = np.frombuffer(pdf_blks[0], dtype=np.uint8)
                image[25, : len(pdf_blks[1])] = np.frombuffer(pdf_blks[1], dtype=np.uint8)
                image[30, : len(pdf_blks[2])] = np.frombuffer(pdf_blks[2], dtype=np.uint8)
            elif n_pdf == 2:
                image[12, : len(pdf_blks[0])] = np.frombuffer(pdf_blks[0], dtype=np.uint8)
                image[30, : len(pdf_blks[1])] = np.frombuffer(pdf_blks[1], dtype=np.uint8)
        except Exception:
            pass

        return image

    def _ingest_target_blocks(self, target_path: str, max_blocks: int = 100000) -> tuple[np.ndarray, str]:
        """Ingests raw blocks from a file, physical drive (\\\\.\\PhysicalDriveX), or volume (\\\\.\\D:)."""
        if not target_path or target_path.upper() == "DEMO":
            return self._create_synthetic_forensic_image(), "Synthetic Benchmark Target"

        # 1. Regular forensic file image on disk (e.g. .raw, .dd, .img)
        if os.path.isfile(target_path):
            try:
                blocks = []
                with open(target_path, "rb") as f:
                    for _ in range(max_blocks):
                        chunk = f.read(BLOCK_SIZE)
                        if not chunk or len(chunk) < BLOCK_SIZE:
                            break
                        blocks.append(np.frombuffer(chunk, dtype=np.uint8))
                if blocks:
                    return np.stack(blocks), f"File Image: {target_path}"
            except Exception:
                pass

        # 2. Build candidate access paths for physical disks or volumes
        candidates: list[str] = [target_path]

        # If given drive letter like 'D:' or 'D:\', convert to raw volume device '\\.\D:'
        m = re.match(r"^([A-Za-z]):", target_path)
        if m:
            candidates.insert(0, rf"\\.\{m.group(1).upper()}:")

        # If given PhysicalDrive path like '\\.\PhysicalDrive1', query PowerShell for its drive letters
        # Windows requires Administrator for \\.\PhysicalDriveX but allows unprivileged read on \\.\D:
        if "PhysicalDrive" in target_path:
            num_match = re.search(r"PhysicalDrive(\d+)", target_path)
            if num_match:
                disk_num = num_match.group(1)
                try:
                    cmd = ["powershell.exe", "-NoProfile", "-Command", f"Get-Partition -DiskNumber {disk_num} | Select-Object -ExpandProperty DriveLetter"]
                    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=False)
                    if proc.returncode == 0 and proc.stdout.strip():
                        for ltr in proc.stdout.strip().splitlines():
                            ltr = ltr.strip()
                            if ltr:
                                candidates.append(rf"\\.\{ltr.upper()}:")
                except Exception:
                    pass

        # 3. Attempt reading blocks from candidates
        for p in candidates:
            try:
                blocks = []
                with open(p, "rb") as dev:
                    for idx in range(max_blocks):
                        chunk = dev.read(BLOCK_SIZE)
                        if not chunk or len(chunk) < BLOCK_SIZE:
                            break
                        blocks.append(np.frombuffer(chunk, dtype=np.uint8))
                if blocks:
                    return np.stack(blocks), f"Live Media Stream: {p}"
            except (PermissionError, OSError, Exception):
                continue

        # Fallback to synthetic if inaccessible
        return self._create_synthetic_forensic_image(), "Synthetic Fallback (Device Inaccessible)"

    def start_job(
        self,
        target_path: str,
        case_id: str = "CAS-DEFAULT",
        investigator: str = "INVESTIGATOR-01",
        deep_ml: bool = True,
        max_blocks: int = 100000,
    ) -> CarvingJob:
        job_id = f"CRV-{uuid.uuid4().hex[:8].upper()}"
        job = CarvingJob(
            job_id=job_id,
            case_id=case_id,
            investigator=investigator,
            target_path=target_path,
            status="SCANNING",
            progress_percent=10,
            total_blocks=60,
            blocks_scanned=0,
            orphans_count=0,
        )
        self.jobs[job_id] = job

        # Load blocks from physical drive, volume device, raw image, or demo benchmark
        image, source_desc = self._ingest_target_blocks(target_path, max_blocks=max_blocks)
        job.source_description = source_desc

        job.total_blocks = len(image)
        job.blocks_scanned = len(image)
        job.progress_percent = 50

        # Destination folder for extracted artifacts (A:\SIH\SIH_FORENSIC\recovered_evidence)
        project_root = Path(__file__).resolve().parents[2]
        out_dir = project_root / "recovered_evidence"
        out_dir.mkdir(parents=True, exist_ok=True)
        job.output_dir = str(out_dir.resolve())

        # Phase 1: Fast Block-Level Triage (1D-CNN) to screen noise & unallocated blocks
        noise_mask = None
        try:
            triage = self._get_triage()
            labels, _ = triage.scan(image)
            noise_mask = (labels == NOISE_IDX)
        except Exception:
            pass

        # Run Phase 2 Deterministic Signature Carving (FR2.0) with noise filtering
        carve_res = carve(image, noise_mask=noise_mask)

        # FR2.0 -> FR2.1 Structural Coherence Validation Gate
        valid_streams, orphan_indices = validate_carve(image, carve_res, min_struct=0.85)
        carve_res.streams = valid_streams
        carve_res.orphans = orphan_indices
        job.orphans_count = len(carve_res.orphans)

        recovered_files: list[CarvedFileSummary] = []
        file_idx = 1

        # Process and save verified straight streams
        for stream in carve_res.streams:
            raw_data = stream.assemble(image)
            if not raw_data.strip(b"\x00") or len(raw_data) < 32:
                continue

            is_valid, reason = verify_carved_file(raw_data, stream.mime)
            score_res: ScoreBreakdown = self.scorer.score(data=raw_data, mime=stream.mime)

            # Strict Rejection Gate: Discard unopenable, corrupted, or low-confidence files
            if not is_valid or score_res.S < 0.65 or stream.mime == "application/octet-stream":
                continue

            sha = hashlib.sha256(raw_data).hexdigest()
            prio = "HIGH" if score_res.S >= 0.75 else "MEDIUM"

            ext = stream.mime.split("/")[-1]
            if ext == "jpeg":
                ext = "jpg"
            fname = f"carved_{file_idx:03d}_{stream.blocks[0]:06d}.{ext}"
            saved_file = out_dir / fname
            saved_file.write_bytes(raw_data)

            start_offset = (stream.blocks[0] * BLOCK_SIZE + stream.header_offset) if stream.blocks else 0
            recovered_files.append(
                CarvedFileSummary(
                    file_id=f"REC-{file_idx:03d}",
                    mime=stream.mime,
                    block_count=len(stream.blocks),
                    size_bytes=len(raw_data),
                    is_closed=stream.closed,
                    reliability_score=round(score_res.S, 3),
                    score_breakdown={
                        "C_hf": round(score_res.C_hf, 3),
                        "C_struct": round(score_res.C_struct, 3),
                        "delta_ent": round(score_res.delta_ent, 3),
                        "C_sem": round(score_res.C_sem, 3),
                    },
                    triage_priority=prio,
                    sha256=sha,
                    offset_bytes=start_offset,
                    filename=fname,
                    saved_path=str(saved_file.resolve()),
                    is_verified=True,
                    validation_status="OPEN_VERIFIED",
                )
            )
            file_idx += 1

        # Reassemble fragmented orphans if any (capped to candidate non-empty blocks to prevent hang)
        if deep_ml and carve_res.orphans:
            job.status = "REASSEMBLING"
            job.progress_percent = 80
            try:
                resolver = GlobalFragmentResolver()
                candidate_orphans = [b for b in carve_res.orphans if image[b].any()][:200]
                if candidate_orphans:
                    orphan_bytes: list[bytes] = [image[blk].tobytes() for blk in candidate_orphans]
                    resolve_result = resolver.resolve(orphan_bytes, mime=None)
                    for chain in resolve_result.chains:
                        # Skip headless chains or octet-stream
                        if not chain.mime or chain.mime == "application/octet-stream":
                            continue

                        raw_data = chain.assemble(orphan_bytes)
                        if not raw_data.strip(b"\x00") or len(raw_data) < 64:
                            continue

                        is_valid, reason = verify_carved_file(raw_data, chain.mime)
                        score_res = self.scorer.score(data=raw_data, mime=chain.mime)

                        # Strict Rejection Gate: Discard unopenable or low-confidence reassembled files
                        if not is_valid or score_res.S < 0.65:
                            continue

                        sha = hashlib.sha256(raw_data).hexdigest()
                        mime_str = chain.mime
                        ext = mime_str.split("/")[-1]
                        if ext == "jpeg":
                            ext = "jpg"
                        start_blk = candidate_orphans[chain.order[0]] if chain.order else 0
                        fname = f"reassembled_{file_idx:03d}_{start_blk:06d}.{ext}"
                        saved_file = out_dir / fname
                        saved_file.write_bytes(raw_data)

                        recovered_files.append(
                            CarvedFileSummary(
                                file_id=f"REC-{file_idx:03d}",
                                mime=mime_str,
                                block_count=len(chain.order),
                                size_bytes=len(raw_data),
                                is_closed=not chain.cut_cycle,
                                reliability_score=round(score_res.S, 3),
                                score_breakdown={
                                    "C_hf": round(score_res.C_hf, 3),
                                    "C_struct": round(score_res.C_struct, 3),
                                    "delta_ent": round(score_res.delta_ent, 3),
                                    "C_sem": round(score_res.C_sem, 3),
                                },
                                triage_priority="HIGH" if score_res.S >= 0.75 else "MEDIUM",
                                sha256=sha,
                                offset_bytes=start_blk * BLOCK_SIZE,
                                filename=fname,
                                saved_path=str(saved_file.resolve()),
                                is_verified=True,
                                validation_status="OPEN_VERIFIED",
                            )
                        )
                        file_idx += 1
            except Exception as err:
                job.error = f"Reassembly warning: {err}"

        job.files_recovered = recovered_files
        job.status = "COMPLETED"
        job.progress_percent = 100
        job.certificate_id = f"BSA63-{job_id}"

        # Write Section 63 BSA Chain of Custody Audit Log
        try:
            audit_file = out_dir / "section_63_bsa_audit.json"
            audit_record = {
                "court_certification": "Section 63 Bharatiya Sakshya Adhiniyam, 2023",
                "case_id": case_id,
                "investigator": investigator,
                "target_media": target_path,
                "source_description": source_desc,
                "blocks_analyzed": len(image),
                "total_bytes_analyzed": len(image) * BLOCK_SIZE,
                "files_recovered_count": len(recovered_files),
                "recovered_evidence": [asdict(f) for f in recovered_files],
                "custody_hash": hashlib.sha256(json.dumps([asdict(f) for f in recovered_files], sort_keys=True).encode()).hexdigest(),
            }
            audit_file.write_text(json.dumps(audit_record, indent=2))
        except Exception:
            pass

        return job

    def handle_request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        parsed = urllib.parse.urlparse(path)
        clean_path = parsed.path.rstrip("/")

        try:
            # 1. POST /api/carving/start
            if method == "POST" and clean_path == "/api/carving/start":
                data = body or {}
                target = data.get("targetPath", "DEMO")
                case_id = data.get("caseId", "CAS-2026-904")
                investigator = data.get("investigator", "Officer In-Charge")
                deep_ml = bool(data.get("deepMl", True))
                max_blocks = int(data.get("maxBlocks", 100000))

                job = self.start_job(
                    target_path=target,
                    case_id=case_id,
                    investigator=investigator,
                    deep_ml=deep_ml,
                    max_blocks=max_blocks,
                )
                return 200, {
                    "status": "SUCCESS",
                    "jobId": job.job_id,
                    "job": asdict(job),
                }

            # 2. GET /api/carving/:id/status
            if method == "GET" and clean_path.startswith("/api/carving/") and clean_path.endswith("/status"):
                parts = clean_path.split("/")
                job_id = parts[3]
                job = self.jobs.get(job_id)
                if not job:
                    return 404, {"status": "ERROR", "code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found"}
                return 200, {
                    "status": "SUCCESS",
                    "jobId": job.job_id,
                    "status": job.status,
                    "progress": job.progress_percent,
                    "blocksScanned": job.blocks_scanned,
                    "totalBlocks": job.total_blocks,
                    "orphansCount": job.orphans_count,
                    "filesFound": len(job.files_recovered),
                }

            # 3. GET /api/carving/:id/results
            if method == "GET" and clean_path.startswith("/api/carving/") and clean_path.endswith("/results"):
                parts = clean_path.split("/")
                job_id = parts[3]
                job = self.jobs.get(job_id)
                if not job:
                    return 404, {"status": "ERROR", "code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found"}
                return 200, {
                    "status": "SUCCESS",
                    "jobId": job.job_id,
                    "files": [asdict(f) for f in job.files_recovered],
                    "totalRecovered": len(job.files_recovered),
                    "outputDir": job.output_dir,
                    "sourceDescription": job.source_description,
                    "certificateId": job.certificate_id,
                }

            # 4. GET /api/carving/:id/certificate
            if method == "GET" and clean_path.startswith("/api/carving/") and clean_path.endswith("/certificate"):
                parts = clean_path.split("/")
                job_id = parts[3]
                job = self.jobs.get(job_id)
                if not job:
                    return 404, {"status": "ERROR", "code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found"}
                return 200, {
                    "status": "SUCCESS",
                    "certificateId": job.certificate_id,
                    "legalStandard": "Section 63(4), Bharatiya Sakshya Adhiniyam, 2023",
                    "caseId": job.case_id,
                    "investigator": job.investigator,
                    "timestamp": job.created_at,
                    "artifactsCertified": len(job.files_recovered),
                    "algorithmDetails": {
                        "formula": "S = w1·C_hf + w2·C_struct + w3·(1 - Δ_ent) + w4·C_sem",
                        "classifier": "1D-CNN Block Classifier (ONNX quantized)",
                        "reassembly": "Maximum Weight Matching via Hungarian Algorithm",
                    },
                }

            return 404, {"status": "ERROR", "message": f"Route not found: {method} {clean_path}"}

        except Exception as exc:
            return 500, {
                "status": "ERROR",
                "code": "CARVING_EXCEPTION",
                "message": str(exc),
            }

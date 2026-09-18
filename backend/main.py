"""Forensiwipe Unified Forensic Daemon (Air-Gapped Workstation IPC Server).

Binds strictly to local loopback (127.0.0.1:8000).
Provides unified REST dispatching for:
1. PS Req 1: Drive Discovery & Hardware Sanitization (NIST 800-88 / IEEE 2883-2022)
2. PS Req 2: Targeted File & Folder Sanitization (Slack space & metadata scrubbing)
3. PS Req 3: Advanced Signature & Deep ML File Carving (SHT & Hungarian Graph Reassembly)
4. Legal Compliance: Section 63 BSA Digital Certificates & SHA-256 HMAC Audit Log
"""

from __future__ import annotations

import json
import sys
import os
import urllib.parse
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

# Ensure backend directory is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from sanitization.api import SanitizationApiRouter
from sanitization.file_eraser import SecureFileEraser
from engine.api import CarvingApiRouter


class UnifiedForensicHandler(BaseHTTPRequestHandler):
    """Central HTTP handler routing all forensic workstation requests."""

    sanitization_router = SanitizationApiRouter()
    carving_router = CarvingApiRouter()
    file_eraser = SecureFileEraser()

    def _send_json(self, status: int, data: dict[str, Any]) -> None:
        raw = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        clean_path = parsed.path.rstrip("/")

        # 1. Health check
        if clean_path == "/api/health":
            self._send_json(200, {
                "status": "ONLINE",
                "system": "Forensiwipe Air-Gapped Workstation",
                "loopbackOnly": True,
                "version": "1.0.0-SIH2026",
            })
            return

        # 2. System Overview (matches Slide 6 telemetry)
        if clean_path == "/api/overview":
            is_valid, err = self.sanitization_router.service.audit.verify_chain_integrity()
            devices = self.sanitization_router.service.list_devices(include_mock=True)
            self._send_json(200, {
                "status": "SUCCESS",
                "systemSafety": "SAFE MODE",
                "safeModeDescription": "Demonstration Safe Mode - Loopback disk images writable",
                "auditIntegrity": "HASH CHAIN VERIFIED" if is_valid else "CORRUPTED",
                "chainValid": is_valid,
                "latestHash": self.sanitization_router.service.audit.latest_hash,
                "devicesDetected": len(devices),
                "activeOperations": 0,
            })
            return

        # 3. Carving route dispatch & Evidence download
        if clean_path.startswith("/api/carving/download"):
            query = urllib.parse.parse_qs(parsed.query)
            filename = query.get("file", [""])[0]
            if not filename and clean_path != "/api/carving/download":
                filename = clean_path.split("/")[-1]
            out_dir = (Path(BASE_DIR).parent / "recovered_evidence").resolve()
            target_file = (out_dir / filename).resolve()
            if filename and target_file.is_file() and str(target_file).startswith(str(out_dir)):
                file_bytes = target_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                self.send_header("Content-Length", str(len(file_bytes)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(file_bytes)
                return
            else:
                self._send_json(404, {"status": "ERROR", "message": f"Artifact '{filename}' not found in recovered evidence"})
                return

        if clean_path.startswith("/api/carving"):
            status, resp = self.carving_router.handle_request("GET", self.path)
            self._send_json(status, resp)
            return

        # 4. Sanitization route dispatch (devices, plan, status, proof, etc.)
        status, resp = self.sanitization_router.handle_request("GET", self.path)
        self._send_json(status, resp)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        clean_path = parsed.path.rstrip("/")

        length = int(self.headers.get("Content-Length", 0))
        body = {}
        if length > 0:
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception:
                body = {}

        # 1. Targeted File Eraser (PS Req 2)
        if clean_path == "/api/filesanitize/execute":
            target = body.get("targetPath")
            passes = int(body.get("passes", 3))
            operator_id = body.get("operatorId", "OFFICER-01")
            case_id = body.get("caseId", "CAS-2026-904")
            wipe_slack = bool(body.get("wipeSlack", True))

            if not target:
                self._send_json(400, {"status": "ERROR", "message": "targetPath is required"})
                return

            try:
                # If target is mock/demo, create a temporary file to wipe cleanly
                if target.startswith("MOCK:") or target.startswith("/mock/"):
                    import tempfile
                    from pathlib import Path
                    with tempfile.NamedTemporaryFile(delete=False) as tf:
                        tf.write(b"SAMPLE CONFIDENTIAL CONTAMINATED DATA TO PURGE " * 20)
                        mock_file = tf.name
                    res = self.file_eraser.sanitize_file(
                        mock_file,
                        passes=passes,
                        operator_id=operator_id,
                        case_id=case_id,
                        wipe_slack=wipe_slack,
                        delete_after=True,
                    )
                    res.target_path = target  # preserve display name
                else:
                    res = self.file_eraser.sanitize_file(
                        target,
                        passes=passes,
                        operator_id=operator_id,
                        case_id=case_id,
                        wipe_slack=wipe_slack,
                        delete_after=False,
                    )
                self._send_json(200, {"status": "SUCCESS", "result": res.to_dict()})
                return
            except Exception as err:
                self._send_json(500, {"status": "ERROR", "message": str(err)})
                return

        # 2. Carving route dispatch
        if clean_path.startswith("/api/carving"):
            status, resp = self.carving_router.handle_request("POST", self.path, body)
            self._send_json(status, resp)
            return

        # 3. Sanitization route dispatch
        status, resp = self.sanitization_router.handle_request("POST", self.path, body)
        self._send_json(status, resp)


def run_server(port: int = 8000, host: str = "127.0.0.1") -> None:
    print(f"===========================================================")
    print(f" FORENSIWIPE AIR-GAPPED WORKSTATION DAEMON")
    print(f" Bound strictly to loopback: http://{host}:{port}")
    print(f" NIST SP 800-88 / IEEE 2883 Sanitizer & ML Carving Engine")
    print(f" Section 63 BSA Digital Evidence Compliance: ACTIVE")
    print(f"===========================================================")
    server = HTTPServer((host, port), UnifiedForensicHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping forensic daemon...")
        server.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Forensiwipe Air-Gapped Workstation Daemon")
    parser.add_argument("--port", type=int, default=8000, help="Local port (default: 8000)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Loopback host (default: 127.0.0.1)")
    args = parser.parse_args()
    run_server(port=args.port, host=args.host)

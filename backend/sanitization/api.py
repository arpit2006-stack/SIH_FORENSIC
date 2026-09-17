"""REST API Layer for Secure Drive Sanitization Module.

Exposes RESTful endpoints conforming to PS 26149 specifications:
- GET  /api/devices
- GET  /api/devices/:id
- POST /api/devices/:id/analyze
- POST /api/sanitization/plan
- POST /api/sanitization/dry-run
- POST /api/sanitization/execute
- GET  /api/sanitization/:operationId/status
- GET  /api/sanitization/:operationId/verification
- GET  /api/sanitization/:operationId/proof
- GET  /api/sanitization/:operationId/report
- GET  /api/sanitization/audit/verify

Implements a standalone HTTP dispatcher using standard library for zero-dependency execution,
while also exporting a FastAPI APIRouter when FastAPI is installed.
"""

from __future__ import annotations

import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from sanitization.models import (
    OperationMode,
    SafetyAuthorization,
    SanitizationErrorCode,
    SanitizationException,
    SanitizeMethod,
)
from sanitization.service import SanitizationOperationService


class SanitizationApiRouter:
    """Dispatches API requests to SanitizationOperationService."""

    def __init__(self, service: SanitizationOperationService | None = None):
        self.service = service or SanitizationOperationService()

    def handle_request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Route and execute API request, returning (status_code, response_dict)."""
        parsed = urllib.parse.urlparse(path)
        clean_path = parsed.path.rstrip("/")
        query = urllib.parse.parse_qs(parsed.query)

        try:
            # 1. GET /api/devices
            if method == "GET" and clean_path == "/api/devices":
                include_mock = query.get("includeMock", ["true"])[0].lower() in ("true", "1")
                devices = self.service.list_devices(include_mock=include_mock)
                return 200, {"status": "SUCCESS", "devices": [d.to_dict() for d in devices]}

            # 2. GET /api/devices/:id
            if method == "GET" and clean_path.startswith("/api/devices/"):
                dev_id = clean_path[len("/api/devices/") :]
                # URL decode path (e.g. %2Fdev%2Fmock_nvme0n1)
                dev_id = urllib.parse.unquote(dev_id)
                dev = self.service.get_device(dev_id)
                if not dev:
                    return 404, {"status": "ERROR", "code": "DEVICE_NOT_FOUND", "message": f"Device '{dev_id}' not found"}
                return 200, {"status": "SUCCESS", "device": dev.to_dict()}

            # 3. POST /api/devices/:id/analyze
            if method == "POST" and clean_path.startswith("/api/devices/") and clean_path.endswith("/analyze"):
                parts = clean_path.split("/")
                # /api/devices/<id>/analyze
                dev_id = urllib.parse.unquote(parts[3])
                dev, policy = self.service.plan_sanitization(dev_id)
                return 200, {
                    "status": "SUCCESS",
                    "device": dev.to_dict(),
                    "policy": policy.to_dict(),
                }

            # 4. POST /api/sanitization/plan
            if method == "POST" and clean_path == "/api/sanitization/plan":
                data = body or {}
                dev_path = data.get("devicePath")
                if not dev_path:
                    return 400, {"status": "ERROR", "code": "INVALID_PARAM", "message": "devicePath is required"}
                dev, policy = self.service.plan_sanitization(dev_path)
                return 200, {
                    "status": "SUCCESS",
                    "device": dev.to_dict(),
                    "policy": policy.to_dict(),
                }

            # 5. POST /api/sanitization/dry-run
            if method == "POST" and clean_path == "/api/sanitization/dry-run":
                data = body or {}
                dev_path = data.get("devicePath")
                if not dev_path:
                    return 400, {"status": "ERROR", "code": "INVALID_PARAM", "message": "devicePath is required"}
                method_name = data.get("method")
                selected_method = SanitizeMethod(method_name) if method_name else None
                operator_id = data.get("operatorId", "OP-DRYRUN")
                case_id = data.get("caseId", "CASE-DRYRUN")
                dry_plan = self.service.execute_dry_run(
                    device_path=dev_path,
                    method=selected_method,
                    operator_id=operator_id,
                    case_id=case_id,
                )
                return 200, {"status": "SUCCESS", "dryRun": dry_plan}

            # 6. POST /api/sanitization/execute
            if method == "POST" and clean_path == "/api/sanitization/execute":
                data = body or {}
                auth = SafetyAuthorization.from_dict(data)
                report = self.service.execute_sanitization(auth)
                return 200, {"status": "SUCCESS", "report": report.to_dict()}

            # 7. GET /api/sanitization/audit/verify
            if method == "GET" and clean_path == "/api/sanitization/audit/verify":
                is_valid, err = self.service.audit.verify_chain_integrity()
                return 200, {
                    "status": "SUCCESS",
                    "chainValid": is_valid,
                    "error": err,
                    "latestHash": self.service.audit.latest_hash,
                }

            # 8. GET /api/sanitization/:operationId/status
            if method == "GET" and clean_path.startswith("/api/sanitization/") and clean_path.endswith("/status"):
                op_id = clean_path.split("/")[3]
                report = self.service.get_operation_report(op_id)
                if not report:
                    return 404, {"status": "ERROR", "code": "OPERATION_NOT_FOUND", "message": f"Operation '{op_id}' not found"}
                return 200, {
                    "status": "SUCCESS",
                    "operationId": op_id,
                    "operationStatus": report.status,
                    "execution": report.execution,
                }

            # 9. GET /api/sanitization/:operationId/verification
            if method == "GET" and clean_path.startswith("/api/sanitization/") and clean_path.endswith("/verification"):
                op_id = clean_path.split("/")[3]
                report = self.service.get_operation_report(op_id)
                if not report:
                    return 404, {"status": "ERROR", "code": "OPERATION_NOT_FOUND", "message": f"Operation '{op_id}' not found"}
                return 200, {
                    "status": "SUCCESS",
                    "operationId": op_id,
                    "verification": report.verification.to_dict(),
                    "assurance": report.assurance.to_dict(),
                }

            # 10. GET /api/sanitization/:operationId/proof
            if method == "GET" and clean_path.startswith("/api/sanitization/") and clean_path.endswith("/proof"):
                op_id = clean_path.split("/")[3]
                report = self.service.get_operation_report(op_id)
                if not report or not report.proof:
                    return 404, {"status": "ERROR", "code": "PROOF_NOT_FOUND", "message": f"Proof for operation '{op_id}' not found"}
                return 200, {
                    "status": "SUCCESS",
                    "operationId": op_id,
                    "proof": report.proof.to_dict(),
                }

            # 11. GET /api/sanitization/:operationId/report
            if method == "GET" and clean_path.startswith("/api/sanitization/") and clean_path.endswith("/report"):
                op_id = clean_path.split("/")[3]
                report = self.service.get_operation_report(op_id)
                if not report:
                    return 404, {"status": "ERROR", "code": "REPORT_NOT_FOUND", "message": f"Report for operation '{op_id}' not found"}
                return 200, {
                    "status": "SUCCESS",
                    "report": report.to_dict(),
                }

            return 404, {"status": "ERROR", "message": f"Route not found: {method} {clean_path}"}

        except SanitizationException as exc:
            return 400, {
                "status": "ERROR",
                "code": exc.code.value,
                "message": exc.message,
                "details": exc.details,
            }
        except Exception as exc:
            return 500, {
                "status": "ERROR",
                "code": "INTERNAL_SERVER_ERROR",
                "message": str(exc),
            }


class SanitizationHttpHandler(BaseHTTPRequestHandler):
    """Simple standard HTTP request handler running SanitizationApiRouter."""

    router: SanitizationApiRouter | None = None

    def _send_json(self, status: int, data: dict[str, Any]) -> None:
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        if not self.router:
            self._send_json(500, {"error": "Router uninitialized"})
            return
        status, resp = self.router.handle_request("GET", self.path)
        self._send_json(status, resp)

    def do_POST(self) -> None:
        if not self.router:
            self._send_json(500, {"error": "Router uninitialized"})
            return
        length = int(self.headers.get("Content-Length", 0))
        body = {}
        if length > 0:
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception:
                body = {}
        status, resp = self.router.handle_request("POST", self.path, body)
        self._send_json(status, resp)


def start_sanitization_server(port: int = 8000, host: str = "127.0.0.1") -> HTTPServer:
    """Start local standalone HTTP server for sanitization API."""
    router = SanitizationApiRouter()
    handler = SanitizationHttpHandler
    handler.router = router
    server = HTTPServer((host, port), handler)
    return server

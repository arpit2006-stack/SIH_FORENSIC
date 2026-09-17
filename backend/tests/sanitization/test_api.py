"""Unit tests for SanitizationApiRouter."""

from unittest import TestCase

from sanitization.api import SanitizationApiRouter
from sanitization.models import (
    OperationMode,
    SafetyAuthorization,
    SanitizeMethod,
)


class TestSanitizationApiRouter(TestCase):
    def setUp(self):
        self.router = SanitizationApiRouter()

    def test_get_devices(self):
        code, resp = self.router.handle_request("GET", "/api/devices")
        self.assertEqual(code, 200)
        self.assertEqual(resp["status"], "SUCCESS")
        self.assertGreater(len(resp["devices"]), 0)

    def test_get_single_device(self):
        code, resp = self.router.handle_request("GET", "/api/devices/%2Fdev%2Fmock_nvme0n1")
        self.assertEqual(code, 200)
        self.assertEqual(resp["device"]["devicePath"], "/dev/mock_nvme0n1")

    def test_post_plan(self):
        code, resp = self.router.handle_request("POST", "/api/sanitization/plan", {"devicePath": "/dev/mock_nvme0n1"})
        self.assertEqual(code, 200)
        self.assertEqual(resp["policy"]["recommendedMethod"], "CRYPTO_ERASE")

    def test_post_dry_run(self):
        code, resp = self.router.handle_request(
            "POST",
            "/api/sanitization/dry-run",
            {"devicePath": "/dev/mock_nvme0n1", "method": "CRYPTO_ERASE"},
        )
        self.assertEqual(code, 200)
        self.assertEqual(resp["dryRun"]["mode"], "DRY_RUN")
        self.assertFalse(resp["dryRun"]["executed"])

    def test_post_execute_and_query_endpoints(self):
        auth_payload = {
            "operatorId": "OP-API-TEST",
            "caseId": "CASE-API-TEST",
            "reason": "Court Order Verification",
            "devicePath": "/dev/mock_nvme0n1",
            "modelConfirmation": "Samsung SSD 980 PRO 1TB (MOCK)",
            "serialConfirmation": "S5GXNF0R876543",
            "selectedMethod": "CRYPTO_ERASE",
            "explicitDestructiveConfirmation": True,
            "executionMode": "REAL_EXECUTION",
        }

        code, resp = self.router.handle_request("POST", "/api/sanitization/execute", auth_payload)
        self.assertEqual(code, 200)
        report = resp["report"]
        op_id = report["operationId"]
        self.assertEqual(report["status"], "COMPLETED")

        # Query GET /api/sanitization/:id/status
        code_s, resp_s = self.router.handle_request("GET", f"/api/sanitization/{op_id}/status")
        self.assertEqual(code_s, 200)
        self.assertEqual(resp_s["operationStatus"], "COMPLETED")

        # Query GET /api/sanitization/:id/verification
        code_v, resp_v = self.router.handle_request("GET", f"/api/sanitization/{op_id}/verification")
        self.assertEqual(code_v, 200)
        self.assertEqual(resp_v["verification"]["status"], "VERIFIED")

        # Query GET /api/sanitization/:id/proof
        code_p, resp_p = self.router.handle_request("GET", f"/api/sanitization/{op_id}/proof")
        self.assertEqual(code_p, 200)
        self.assertIsNotNone(resp_p["proof"]["proofHash"])

        # Query GET /api/sanitization/:id/report
        code_r, resp_r = self.router.handle_request("GET", f"/api/sanitization/{op_id}/report")
        self.assertEqual(code_r, 200)
        self.assertEqual(resp_r["report"]["operationId"], op_id)

    def test_verify_audit_chain(self):
        code, resp = self.router.handle_request("GET", "/api/sanitization/audit/verify")
        self.assertEqual(code, 200)
        self.assertTrue(resp["chainValid"])

"""Integration and end-to-end tests for SanitizationOperationService."""

from unittest import TestCase

from sanitization.adapters.mock import MockSanitizationAdapter
from sanitization.audit import SanitizationAuditLogger
from sanitization.discovery import DeviceDiscoveryManager
from sanitization.models import (
    OperationMode,
    SafetyAuthorization,
    SanitizationErrorCode,
    SanitizationException,
    SanitizeMethod,
    VerificationStatus,
)
from sanitization.service import SanitizationOperationService


class TestSanitizationOperationService(TestCase):
    def setUp(self):
        self.mock_adapter = MockSanitizationAdapter()
        self.discovery = DeviceDiscoveryManager(mock_adapter=self.mock_adapter, enable_mock_devices=True)
        self.audit = SanitizationAuditLogger()
        self.service = SanitizationOperationService(
            discovery_manager=self.discovery,
            mock_adapter=self.mock_adapter,
            audit_logger=self.audit,
        )

    def test_list_devices(self):
        devices = self.service.list_devices(include_mock=True)
        self.assertGreater(len(devices), 0)
        # Check that devices have capabilities populated
        mock_dev = next(d for d in devices if d.device_path == "/dev/mock_nvme0n1")
        self.assertIsNotNone(mock_dev.sanitize_capabilities)

    def test_plan_sanitization(self):
        dev, policy = self.service.plan_sanitization("/dev/mock_nvme0n1")
        self.assertEqual(dev.device_path, "/dev/mock_nvme0n1")
        self.assertEqual(policy.recommended_method, SanitizeMethod.CRYPTO_ERASE)
        self.assertEqual(policy.assurance.value, "HIGH")

    def test_dry_run_execution(self):
        plan = self.service.execute_dry_run("/dev/mock_nvme0n1")
        self.assertEqual(plan["mode"], "DRY_RUN")
        self.assertFalse(plan["executed"])
        self.assertTrue(plan["destructive"])
        self.assertIn("nvme sanitize", plan["command"])
        self.assertIn("operationId", plan)

        # Confirm audit event was recorded
        events = self.service.audit.get_events_for_operation(plan["operationId"])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "DRY_RUN_EXECUTED")

    def test_real_execution_end_to_end(self):
        dev = self.service.get_device("/dev/mock_nvme0n1")
        auth = SafetyAuthorization(
            operator_id="OP-FORENSIC-01",
            case_id="CASE-2026-SIH",
            reason="Court ordered hardware purge",
            device_path=dev.device_path,
            model_confirmation=dev.model,
            serial_confirmation=dev.serial,
            selected_method=SanitizeMethod.CRYPTO_ERASE,
            explicit_destructive_confirmation=True,
            execution_mode=OperationMode.REAL_EXECUTION,
        )

        report = self.service.execute_sanitization(auth)
        self.assertEqual(report.status, "COMPLETED")
        self.assertEqual(report.verification.status, VerificationStatus.VERIFIED)
        self.assertIsNotNone(report.proof)
        self.assertEqual(len(report.proof.proof_hash), 64)
        self.assertGreaterEqual(report.assurance.score, 90)

        # Check that audit chain is intact
        valid, err = self.service.audit.verify_chain_integrity()
        self.assertTrue(valid)

    def test_real_execution_blocked_on_system_disk(self):
        sys_dev = self.service.get_device("/dev/mock_system_nvme0n1")
        auth = SafetyAuthorization(
            operator_id="OP-01",
            case_id="CASE-01",
            reason="Testing safety",
            device_path=sys_dev.device_path,
            model_confirmation=sys_dev.model,
            serial_confirmation=sys_dev.serial,
            selected_method=SanitizeMethod.CRYPTO_ERASE,
            explicit_destructive_confirmation=True,
            execution_mode=OperationMode.REAL_EXECUTION,
        )

        with self.assertRaises(SanitizationException) as ctx:
            self.service.execute_sanitization(auth)
        self.assertEqual(ctx.exception.code, SanitizationErrorCode.DEVICE_IS_SYSTEM_DISK)

    def test_real_execution_unverified_handling(self):
        unverif_dev = self.service.get_device("/dev/mock_unverified_nvme3n1")
        auth = SafetyAuthorization(
            operator_id="OP-01",
            case_id="CASE-01",
            reason="Unverified test",
            device_path=unverif_dev.device_path,
            model_confirmation=unverif_dev.model,
            serial_confirmation=unverif_dev.serial,
            selected_method=SanitizeMethod.CRYPTO_ERASE,
            explicit_destructive_confirmation=True,
            execution_mode=OperationMode.REAL_EXECUTION,
        )

        report = self.service.execute_sanitization(auth)
        self.assertEqual(report.status, "SANITIZATION_NOT_VERIFIED")
        self.assertEqual(report.verification.status, VerificationStatus.NOT_VERIFIED)
        self.assertGreater(len(report.missing_evidence), 0)
        self.assertIn("physical destruction", report.recommendation.lower())

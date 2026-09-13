"""Unit tests for Mock NVMe Device and Mock Sanitization Adapter."""

from unittest import TestCase

from sanitization.adapters.mock import MockNVMeDevice, MockSanitizationAdapter
from sanitization.models import (
    SafetyAuthorization,
    SanitizationErrorCode,
    SanitizationException,
    SanitizeMethod,
)


class TestMockDevice(TestCase):
    def setUp(self):
        self.adapter = MockSanitizationAdapter()

    def test_default_devices_registered(self):
        devices = self.adapter.list_devices()
        paths = [d.device_path for d in devices]
        self.assertIn("/dev/mock_nvme0n1", paths)
        self.assertIn(r"\\.\PhysicalDrive9", paths)
        self.assertIn("/dev/disk2", paths)
        self.assertIn("/dev/mock_system_nvme0n1", paths)

    def test_mock_device_capabilities(self):
        dev = self.adapter.get_device("/dev/mock_nvme0n1")
        self.assertIsNotNone(dev)
        info = dev.to_device_info()
        self.assertIsNotNone(info.sanitize_capabilities)
        self.assertTrue(info.sanitize_capabilities.crypto_erase_supported)
        self.assertTrue(info.sanitize_capabilities.block_erase_supported)
        self.assertTrue(info.sanitize_capabilities.overwrite_supported)

    def test_dry_run_plan_generation(self):
        info = self.adapter.get_device("/dev/mock_nvme0n1").to_device_info()
        plan = self.adapter.generate_plan(info, SanitizeMethod.CRYPTO_ERASE)
        self.assertEqual(plan["mode"], "DRY_RUN")
        self.assertEqual(plan["method"], "CRYPTO_ERASE")
        self.assertIn("nvme sanitize", plan["command"])
        self.assertFalse(plan["executed"])
        self.assertGreater(len(plan["verificationPlan"]), 0)

    def test_successful_sanitize_execution_and_status(self):
        info = self.adapter.get_device("/dev/mock_nvme0n1").to_device_info()
        auth = SafetyAuthorization(
            operator_id="OP-001",
            case_id="CASE-2026-99",
            reason="Court Ordered Forensic Sanitization",
            device_path="/dev/mock_nvme0n1",
            model_confirmation=info.model,
            serial_confirmation=info.serial,
            selected_method=SanitizeMethod.CRYPTO_ERASE,
            explicit_destructive_confirmation=True,
        )

        res = self.adapter.execute_sanitize(info, SanitizeMethod.CRYPTO_ERASE, auth)
        self.assertEqual(res["status"], "SUCCESS")

        # Check status log
        status = self.adapter.get_sanitize_status(info)
        self.assertTrue(status["completed"])
        self.assertTrue(status["success"])
        self.assertEqual(status["sstat"], "0x101")  # Crypto erase success

        # Check block sampling
        samples = self.adapter.sample_blocks(info, num_samples=5)
        self.assertEqual(len(samples), 5)
        for s in samples:
            self.assertTrue(s["isZeroed"])
            self.assertEqual(s["entropy"], 0.0)

    def test_not_verified_device_behavior(self):
        info = self.adapter.get_device("/dev/mock_unverified_nvme3n1").to_device_info()
        auth = SafetyAuthorization(
            operator_id="OP-001",
            case_id="CASE-2026-99",
            reason="Court Ordered Forensic Sanitization",
            device_path=info.device_path,
            model_confirmation=info.model,
            serial_confirmation=info.serial,
            selected_method=SanitizeMethod.CRYPTO_ERASE,
            explicit_destructive_confirmation=True,
        )

        res = self.adapter.execute_sanitize(info, SanitizeMethod.CRYPTO_ERASE, auth)
        self.assertEqual(res["status"], "SUCCESS")

        # But block sampling reveals remnant data!
        samples = self.adapter.sample_blocks(info, num_samples=5)
        self.assertEqual(len(samples), 5)
        for s in samples:
            self.assertFalse(s["isZeroed"])
            self.assertGreater(s["entropy"], 7.0)

    def test_failed_device_behavior(self):
        info = self.adapter.get_device("/dev/mock_fail_nvme4n1").to_device_info()
        auth = SafetyAuthorization(
            operator_id="OP-001",
            case_id="CASE-2026-99",
            reason="Court Ordered Forensic Sanitization",
            device_path=info.device_path,
            model_confirmation=info.model,
            serial_confirmation=info.serial,
            selected_method=SanitizeMethod.CRYPTO_ERASE,
            explicit_destructive_confirmation=True,
        )

        with self.assertRaises(SanitizationException) as ctx:
            self.adapter.execute_sanitize(info, SanitizeMethod.CRYPTO_ERASE, auth)
        self.assertEqual(ctx.exception.code, SanitizationErrorCode.EXECUTION_FAILED)

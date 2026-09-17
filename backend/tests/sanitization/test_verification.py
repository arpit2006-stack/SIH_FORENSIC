"""Unit tests for ErasureVerificationEngine."""

from unittest import TestCase

from sanitization.adapters.mock import MockNVMeDevice, MockSanitizationAdapter
from sanitization.models import (
    DeviceInfo,
    SanitizeMethod,
    StorageType,
    VerificationStatus,
)
from sanitization.verification import ErasureVerificationEngine


class TestErasureVerificationEngine(TestCase):
    def setUp(self):
        self.adapter = MockSanitizationAdapter()

    def test_verified_when_all_checks_pass(self):
        dev = self.adapter.get_device("/dev/mock_nvme0n1").to_device_info()
        exec_res = {"status": "SUCCESS"}
        # Execute mock sanitize to put mock device in completed state
        self.adapter.get_device("/dev/mock_nvme0n1").execute_sanitize(SanitizeMethod.CRYPTO_ERASE)

        verif_res, missing, rec = ErasureVerificationEngine.verify_erasure(
            device=dev,
            re_discovered=dev,
            method=SanitizeMethod.CRYPTO_ERASE,
            execution_result=exec_res,
            adapter=self.adapter,
        )

        self.assertEqual(verif_res.status, VerificationStatus.VERIFIED)
        self.assertEqual(len(missing), 0)
        self.assertIn("verified", rec.lower())
        self.assertEqual(verif_res.controller_status_code, "0x101")
        for check in verif_res.checks:
            self.assertTrue(check.passed)

    def test_not_verified_when_block_sampling_detects_residual_data(self):
        # Device in NOT_VERIFIED mode
        dev = self.adapter.get_device("/dev/mock_unverified_nvme3n1").to_device_info()
        exec_res = {"status": "SUCCESS"}
        self.adapter.get_device("/dev/mock_unverified_nvme3n1").execute_sanitize(SanitizeMethod.CRYPTO_ERASE)

        verif_res, missing, rec = ErasureVerificationEngine.verify_erasure(
            device=dev,
            re_discovered=dev,
            method=SanitizeMethod.CRYPTO_ERASE,
            execution_result=exec_res,
            adapter=self.adapter,
        )

        self.assertEqual(verif_res.status, VerificationStatus.NOT_VERIFIED)
        self.assertGreater(len(missing), 0)
        self.assertTrue(any("residual" in m.lower() for m in missing))
        self.assertIn("physical destruction", rec.lower())

    def test_failed_when_controller_reports_error(self):
        dev = self.adapter.get_device("/dev/mock_fail_nvme4n1").to_device_info()
        exec_res = {"status": "FAILED"}
        # Force device state to FAILED
        self.adapter.get_device("/dev/mock_fail_nvme4n1").current_state = "FAILED"

        verif_res, missing, rec = ErasureVerificationEngine.verify_erasure(
            device=dev,
            re_discovered=dev,
            method=SanitizeMethod.CRYPTO_ERASE,
            execution_result=exec_res,
            adapter=self.adapter,
        )

        self.assertEqual(verif_res.status, VerificationStatus.FAILED)
        self.assertEqual(verif_res.controller_status_code, "0x100")
        self.assertIn("failed", verif_res.details.lower())

    def test_identity_mismatch_triggers_not_verified(self):
        dev = self.adapter.get_device("/dev/mock_nvme0n1").to_device_info()
        self.adapter.get_device("/dev/mock_nvme0n1").execute_sanitize(SanitizeMethod.CRYPTO_ERASE)
        exec_res = {"status": "SUCCESS"}

        # Simulate swapped device post sanitization
        swapped = DeviceInfo(
            device_path=dev.device_path,
            serial="DIFFERENT_SERIAL_888",
            model=dev.model,
            capacity_bytes=dev.capacity_bytes,
        )

        verif_res, missing, rec = ErasureVerificationEngine.verify_erasure(
            device=dev,
            re_discovered=swapped,
            method=SanitizeMethod.CRYPTO_ERASE,
            execution_result=exec_res,
            adapter=self.adapter,
        )

        self.assertEqual(verif_res.status, VerificationStatus.NOT_VERIFIED)
        self.assertTrue(any("identity" in m.lower() for m in missing))

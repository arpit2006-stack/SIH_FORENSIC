"""Tests for PrivilegeManager and Anti-Drive-Swap Target Revalidation."""

import unittest
from unittest import TestCase

from sanitization.adapters.mock import MockSanitizationAdapter
from sanitization.discovery import DeviceDiscoveryManager
from sanitization.models import (
    DeviceInfo,
    OperationMode,
    SafetyAuthorization,
    SanitizationErrorCode,
    SanitizationException,
    SanitizeMethod,
    StorageType,
)
from sanitization.privilege import OperationType, PrivilegeManager, PrivilegeState
from sanitization.service import SanitizationOperationService


class TestPrivilegeAndTargetRevalidation(TestCase):
    def setUp(self):
        self.mock_adapter = MockSanitizationAdapter()
        self.discovery = DeviceDiscoveryManager(mock_adapter=self.mock_adapter, enable_mock_devices=True)
        self.service = SanitizationOperationService(
            discovery_manager=self.discovery,
            mock_adapter=self.mock_adapter,
        )

    def test_privilege_state_detection(self):
        state = PrivilegeManager.get_current_privilege_state()
        self.assertIn(state, list(PrivilegeState))

    def test_privilege_check_non_destructive(self):
        # Non-destructive ops require no elevated tokens
        self.assertTrue(PrivilegeManager.check_operation_requirement(OperationType.DISCOVERY))
        self.assertTrue(PrivilegeManager.check_operation_requirement(OperationType.IMAGE_CARVE))
        self.assertTrue(PrivilegeManager.check_operation_requirement(OperationType.FILE_SCRUB))
        self.assertTrue(PrivilegeManager.check_operation_requirement(OperationType.DRY_RUN))

    def test_privilege_check_mock_bypass(self):
        # Mock operations bypass physical elevation requirements safely
        self.assertTrue(PrivilegeManager.check_operation_requirement(OperationType.PHYSICAL_OVERWRITE, is_mock=True))
        self.assertTrue(PrivilegeManager.check_operation_requirement(OperationType.FIRMWARE_SANITIZE, is_mock=True))

    def test_revalidate_target_success(self):
        ok, msg, dev = self.discovery.revalidate_target(
            "/dev/mock_nvme0n1",
            expected_serial="S5GXNF0R876543",
        )
        self.assertTrue(ok)
        self.assertIsNotNone(dev)
        self.assertEqual(dev.serial, "S5GXNF0R876543")

    def test_revalidate_target_serial_mismatch_aborts(self):
        ok, msg, dev = self.discovery.revalidate_target(
            "/dev/mock_nvme0n1",
            expected_serial="WRONG_SERIAL_123",
        )
        self.assertFalse(ok)
        self.assertIn("Serial mismatch", msg)

    def test_revalidate_target_missing_device_aborts(self):
        ok, msg, dev = self.discovery.revalidate_target(
            "/dev/nonexistent_drive_x",
            expected_serial="ANY",
        )
        self.assertFalse(ok)
        self.assertIn("not found", msg.lower())

    def test_execute_sanitization_aborts_on_revalidation_mismatch(self):
        dev = self.service.get_device("/dev/mock_nvme0n1")
        auth = SafetyAuthorization(
            operator_id="OP-TEST",
            case_id="CASE-TEST",
            reason="Testing anti-drive-swap guard",
            device_path=dev.device_path,
            model_confirmation=dev.model,
            serial_confirmation="HOTSWAPPED_SERIAL_999",  # mismatched serial
            selected_method=SanitizeMethod.CRYPTO_ERASE,
            explicit_destructive_confirmation=True,
            execution_mode=OperationMode.REAL_EXECUTION,
        )

        with self.assertRaises(SanitizationException) as ctx:
            self.service.execute_sanitization(auth)
        self.assertEqual(ctx.exception.code, SanitizationErrorCode.DEVICE_IDENTITY_MISMATCH)


if __name__ == "__main__":
    unittest.main()

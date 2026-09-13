"""Unit tests for SafetyGate."""

from unittest import TestCase

from sanitization.models import (
    DeviceInfo,
    OperationMode,
    SafetyAuthorization,
    SanitizationErrorCode,
    SanitizationException,
    SanitizeMethod,
    StorageType,
)
from sanitization.safety import SafetyGate


class TestSafetyGate(TestCase):
    def setUp(self):
        self.device = DeviceInfo(
            device_path="/dev/mock_nvme0n1",
            controller_path="/dev/mock_nvme0",
            storage_type=StorageType.NVME_SSD,
            model="Samsung SSD 980 PRO 1TB (MOCK)",
            serial="S5GXNF0R876543",
            capacity_bytes=1000204886016,
            system_disk=False,
            mounted=False,
        )

    def test_valid_authorization_passes(self):
        auth = SafetyAuthorization(
            operator_id="OP-001",
            case_id="CASE-SIH-2026",
            reason="Forensic sanitization pursuant to court order",
            device_path="/dev/mock_nvme0n1",
            model_confirmation="Samsung SSD 980 PRO 1TB (MOCK)",
            serial_confirmation="S5GXNF0R876543",
            selected_method=SanitizeMethod.CRYPTO_ERASE,
            explicit_destructive_confirmation=True,
            execution_mode=OperationMode.REAL_EXECUTION,
        )
        # Should not raise
        SafetyGate.validate_authorization(auth, self.device)

    def test_missing_operator_id_fails(self):
        auth = SafetyAuthorization(
            operator_id="",
            case_id="CASE-SIH-2026",
            reason="Test",
            device_path="/dev/mock_nvme0n1",
            model_confirmation="Samsung SSD 980 PRO 1TB (MOCK)",
            serial_confirmation="S5GXNF0R876543",
            selected_method=SanitizeMethod.CRYPTO_ERASE,
            explicit_destructive_confirmation=True,
        )
        with self.assertRaises(SanitizationException) as ctx:
            SafetyGate.validate_authorization(auth, self.device)
        self.assertEqual(ctx.exception.code, SanitizationErrorCode.AUTHORIZATION_REQUIRED)

    def test_wrong_serial_confirmation_fails(self):
        auth = SafetyAuthorization(
            operator_id="OP-001",
            case_id="CASE-SIH-2026",
            reason="Test",
            device_path="/dev/mock_nvme0n1",
            model_confirmation="Samsung SSD 980 PRO 1TB (MOCK)",
            serial_confirmation="WRONG_SERIAL_123",
            selected_method=SanitizeMethod.CRYPTO_ERASE,
            explicit_destructive_confirmation=True,
        )
        with self.assertRaises(SanitizationException) as ctx:
            SafetyGate.validate_authorization(auth, self.device)
        self.assertEqual(ctx.exception.code, SanitizationErrorCode.DEVICE_IDENTITY_MISMATCH)

    def test_system_disk_blocks_execution(self):
        sys_dev = DeviceInfo(
            device_path="/dev/nvme0n1",
            model="Samsung SSD 980 PRO 1TB (MOCK)",
            serial="S5GXNF0R876543",
            system_disk=True,
            mounted=True,
            mount_points=["/"],
        )
        auth = SafetyAuthorization(
            operator_id="OP-001",
            case_id="CASE-SIH-2026",
            reason="Test",
            device_path="/dev/nvme0n1",
            model_confirmation="Samsung SSD 980 PRO 1TB (MOCK)",
            serial_confirmation="S5GXNF0R876543",
            selected_method=SanitizeMethod.CRYPTO_ERASE,
            explicit_destructive_confirmation=True,
        )
        with self.assertRaises(SanitizationException) as ctx:
            SafetyGate.validate_authorization(auth, sys_dev)
        self.assertEqual(ctx.exception.code, SanitizationErrorCode.DEVICE_IS_SYSTEM_DISK)

    def test_mounted_device_blocks_execution(self):
        mounted_dev = DeviceInfo(
            device_path="/dev/mock_nvme0n1",
            model="Samsung SSD 980 PRO 1TB (MOCK)",
            serial="S5GXNF0R876543",
            system_disk=False,
            mounted=True,
            mount_points=["/mnt/data"],
        )
        auth = SafetyAuthorization(
            operator_id="OP-001",
            case_id="CASE-SIH-2026",
            reason="Test",
            device_path="/dev/mock_nvme0n1",
            model_confirmation="Samsung SSD 980 PRO 1TB (MOCK)",
            serial_confirmation="S5GXNF0R876543",
            selected_method=SanitizeMethod.CRYPTO_ERASE,
            explicit_destructive_confirmation=True,
        )
        with self.assertRaises(SanitizationException) as ctx:
            SafetyGate.validate_authorization(auth, mounted_dev)
        self.assertEqual(ctx.exception.code, SanitizationErrorCode.DEVICE_MOUNTED)

    def test_missing_destructive_confirmation_fails_real_execution(self):
        auth = SafetyAuthorization(
            operator_id="OP-001",
            case_id="CASE-SIH-2026",
            reason="Test",
            device_path="/dev/mock_nvme0n1",
            model_confirmation="Samsung SSD 980 PRO 1TB (MOCK)",
            serial_confirmation="S5GXNF0R876543",
            selected_method=SanitizeMethod.CRYPTO_ERASE,
            explicit_destructive_confirmation=False,  # NOT confirmed!
            execution_mode=OperationMode.REAL_EXECUTION,
        )
        with self.assertRaises(SanitizationException) as ctx:
            SafetyGate.validate_authorization(auth, self.device)
        self.assertEqual(ctx.exception.code, SanitizationErrorCode.DESTRUCTIVE_CONFIRMATION_MISSING)

    def test_pre_execution_integrity_detects_swapped_drive(self):
        swapped_dev = DeviceInfo(
            device_path="/dev/mock_nvme0n1",
            model="Samsung SSD 980 PRO 1TB (MOCK)",
            serial="SWAPPED_SERIAL_999",
            capacity_bytes=1000204886016,
        )
        with self.assertRaises(SanitizationException) as ctx:
            SafetyGate.verify_pre_execution_integrity(self.device, swapped_dev)
        self.assertEqual(ctx.exception.code, SanitizationErrorCode.DEVICE_IDENTITY_MISMATCH)

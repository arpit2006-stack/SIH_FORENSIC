"""Unit tests for SanitizationAuditLogger."""

from unittest import TestCase

from sanitization.audit import GENESIS_HASH, SanitizationAuditLogger
from sanitization.models import DeviceInfo, SanitizeEventType, StorageType


class TestSanitizationAuditLogger(TestCase):
    def setUp(self):
        self.logger = SanitizationAuditLogger()
        self.device = DeviceInfo(
            device_path="/dev/mock_nvme0n1",
            storage_type=StorageType.NVME_SSD,
            model="Samsung SSD 980 PRO 1TB",
            serial="S5GXNF0R876543",
        )

    def test_event_logging_and_hash_chaining(self):
        ev1 = self.logger.log_event(
            operation_id="op-1",
            case_id="case-1",
            operator_id="op-1",
            event_type=SanitizeEventType.DEVICE_DISCOVERED,
            device=self.device,
            result="SUCCESS",
        )
        self.assertEqual(ev1.previous_hash, GENESIS_HASH)
        self.assertNotEqual(ev1.event_hash, GENESIS_HASH)

        ev2 = self.logger.log_event(
            operation_id="op-1",
            case_id="case-1",
            operator_id="op-1",
            event_type=SanitizeEventType.SANITIZATION_PLANNED,
            device=self.device,
            result="SUCCESS",
        )
        self.assertEqual(ev2.previous_hash, ev1.event_hash)

        # Verify chain integrity
        valid, err = self.logger.verify_chain_integrity()
        self.assertTrue(valid)
        self.assertIsNone(err)

    def test_tamper_detection(self):
        self.logger.log_event(
            operation_id="op-1",
            case_id="case-1",
            operator_id="op-1",
            event_type=SanitizeEventType.DEVICE_DISCOVERED,
            device=self.device,
            result="SUCCESS",
        )
        self.logger.log_event(
            operation_id="op-1",
            case_id="case-1",
            operator_id="op-1",
            event_type=SanitizeEventType.SANITIZATION_STARTED,
            device=self.device,
            result="STARTED",
        )

        # Tamper with the first event result
        self.logger._events[0].result = "TAMPERED_RESULT"

        valid, err = self.logger.verify_chain_integrity()
        self.assertFalse(valid)
        self.assertIn("Tamper detected", err)

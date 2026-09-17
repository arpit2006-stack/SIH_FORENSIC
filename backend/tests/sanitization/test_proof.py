"""Unit tests for ErasureProofService."""

from unittest import TestCase

from sanitization.models import (
    DeviceInfo,
    SanitizeMethod,
    StorageType,
    VerificationCheck,
    VerificationResult,
    VerificationStatus,
)
from sanitization.proof import ErasureProofService


class TestErasureProofService(TestCase):
    def setUp(self):
        self.device = DeviceInfo(
            device_path="/dev/mock_nvme0n1",
            controller_path="/dev/mock_nvme0",
            storage_type=StorageType.NVME_SSD,
            vendor="Samsung",
            model="Samsung SSD 980 PRO 1TB (MOCK)",
            serial="S5GXNF0R876543",
            firmware="5B2QGXA7",
            capacity_bytes=1000204886016,
            interface="NVMe",
        )
        self.verif = VerificationResult(
            status=VerificationStatus.VERIFIED,
            checks=[
                VerificationCheck(check_name="Controller SSTAT", passed=True, details="0x101"),
                VerificationCheck(check_name="Block Sampling", passed=True, details="10 clean blocks"),
            ],
            controller_status_code="0x101",
            details="Verified clean",
        )

    def test_proof_generation_and_verification(self):
        prev_hash = "a" * 64
        proof = ErasureProofService.generate_proof(
            operation_id="op-12345",
            case_id="CASE-001",
            operator_id="OP-ADMIN",
            device=self.device,
            method=SanitizeMethod.CRYPTO_ERASE,
            requested_timestamp="2026-09-13T10:00:00Z",
            start_timestamp="2026-09-13T10:00:01Z",
            completion_timestamp="2026-09-13T10:00:05Z",
            controller_result={"sstat": "0x101", "success": True},
            verification_result=self.verif,
            warnings=[],
            previous_audit_hash=prev_hash,
        )

        self.assertIsNotNone(proof.proof_hash)
        self.assertEqual(len(proof.proof_hash), 64)
        self.assertEqual(proof.previous_audit_hash, prev_hash)

        # Verify hash integrity
        self.assertTrue(ErasureProofService.verify_proof_hash(proof))

    def test_proof_tamper_detection(self):
        prev_hash = "b" * 64
        proof = ErasureProofService.generate_proof(
            operation_id="op-12345",
            case_id="CASE-001",
            operator_id="OP-ADMIN",
            device=self.device,
            method=SanitizeMethod.CRYPTO_ERASE,
            requested_timestamp="2026-09-13T10:00:00Z",
            start_timestamp="2026-09-13T10:00:01Z",
            completion_timestamp="2026-09-13T10:00:05Z",
            controller_result={"sstat": "0x101"},
            verification_result=self.verif,
            warnings=[],
            previous_audit_hash=prev_hash,
        )

        # Altering capacity must invalidate hash
        proof.capacity = 500107862016
        self.assertFalse(ErasureProofService.verify_proof_hash(proof))

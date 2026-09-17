"""Unit tests for ForgeAssuranceService."""

from unittest import TestCase

from sanitization.assurance import ForgeAssuranceService
from sanitization.models import (
    DeviceInfo,
    SanitizeMethod,
    StorageType,
    VerificationResult,
    VerificationStatus,
)


class TestForgeAssuranceService(TestCase):
    def setUp(self):
        self.device = DeviceInfo(
            device_path="/dev/mock_nvme0n1",
            storage_type=StorageType.NVME_SSD,
            model="Samsung SSD 980 PRO 1TB",
            serial="S5GXNF0R876543",
            capacity_bytes=1000204886016,
        )

    def test_exemplary_score(self):
        verif = VerificationResult(status=VerificationStatus.VERIFIED)
        score = ForgeAssuranceService.calculate_score(
            device=self.device,
            method=SanitizeMethod.CRYPTO_ERASE,
            verification_result=verif,
            controller_result={"sstat": "0x101", "success": True, "completed": True},
            identity_consistent=True,
            audit_chain_valid=True,
        )

        # 30 (controller) + 25 (crypto) + 20 (verif) + 10 (id) + 10 (audit) = 95
        self.assertEqual(score.score, 95)
        self.assertEqual(score.max_score, 100)
        self.assertEqual(score.level, "EXEMPLARY")
        self.assertIn("controllerCompletion", score.factors)
        self.assertEqual(score.factors["controllerCompletion"].score, 30)

    def test_not_verified_score_penalty(self):
        verif = VerificationResult(status=VerificationStatus.NOT_VERIFIED)
        score = ForgeAssuranceService.calculate_score(
            device=self.device,
            method=SanitizeMethod.CRYPTO_ERASE,
            verification_result=verif,
            controller_result={"sstat": "0x101", "success": True, "completed": True},
            identity_consistent=True,
            audit_chain_valid=True,
        )

        # Verification check dropped from 20 to 5
        self.assertEqual(score.factors["verificationChecks"].score, 5)
        self.assertLess(score.score, 90)

    def test_failed_controller_insufficient_level(self):
        verif = VerificationResult(status=VerificationStatus.FAILED)
        score = ForgeAssuranceService.calculate_score(
            device=self.device,
            method=SanitizeMethod.OVERWRITE,
            verification_result=verif,
            controller_result={"sstat": "0x100", "success": False, "completed": False},
            identity_consistent=False,
            audit_chain_valid=False,
        )

        # Controller: 0, Method: 12, Verif: 0, ID: 0, Audit: 0 = 12
        self.assertEqual(score.score, 12)
        self.assertEqual(score.level, "INSUFFICIENT")

"""FORGE Erasure Assurance Score component.

Computes a deterministic, explainable 0-100 score across 5 objective forensic factors:
1. Controller Completion (30 pts)
2. Supported Sanitization Method (25 pts)
3. Independent Verification Checks (20 pts)
4. Device Identity Consistency (10 pts)
5. Audit Integrity (10 pts)

NOTE: This is an internal project metric for forensic triage and assurance;
it is not an official government NIST or IEEE certification.
"""

from __future__ import annotations

from typing import Any

from sanitization.models import (
    AssuranceFactor,
    DeviceInfo,
    ForgeAssuranceScore,
    SanitizeMethod,
    VerificationResult,
    VerificationStatus,
)


class ForgeAssuranceService:
    """Computes explainable FORGE Erasure Assurance Score."""

    @classmethod
    def calculate_score(
        cls,
        device: DeviceInfo,
        method: SanitizeMethod,
        verification_result: VerificationResult,
        controller_result: dict[str, Any],
        identity_consistent: bool,
        audit_chain_valid: bool,
    ) -> ForgeAssuranceScore:
        factors: dict[str, AssuranceFactor] = {}

        # Factor 1: Controller Completion (Max 30)
        sstat = str(controller_result.get("sstat", "0x000"))
        ctrl_success = bool(controller_result.get("success", False))
        ctrl_completed = bool(controller_result.get("completed", False))

        if ctrl_completed and ctrl_success and sstat in ("0x101", "0x102", "0x103"):
            f1_score = 30
            f1_desc = f"Hardware controller successfully confirmed operation completion with SSTAT code {sstat}."
        elif ctrl_completed and ctrl_success:
            f1_score = 22
            f1_desc = "Controller command finished successfully, status confirmed via device interface."
        elif controller_result.get("status") == "SUCCESS":
            f1_score = 15
            f1_desc = "Execution process exited with code 0; controller log verification not fully available."
        else:
            f1_score = 0
            f1_desc = f"Controller reported failure or incomplete status (SSTAT: {sstat})."

        factors["controllerCompletion"] = AssuranceFactor(
            name="Controller Completion",
            score=f1_score,
            max_score=30,
            description=f1_desc,
        )

        # Factor 2: Supported Sanitization Method (Max 25)
        if method in (SanitizeMethod.CRYPTO_ERASE, SanitizeMethod.ATA_ENHANCED_SECURITY_ERASE):
            f2_score = 25
            f2_desc = f"Method '{method.value}' provides firmware/crypto purge across accessible and overprovisioned cells."
        elif method in (SanitizeMethod.BLOCK_ERASE, SanitizeMethod.ATA_SECURITY_ERASE):
            f2_score = 20
            f2_desc = f"Method '{method.value}' executes electrical block purge across flash blocks."
        elif method == SanitizeMethod.OVERWRITE:
            f2_score = 12
            f2_desc = "Method 'OVERWRITE' writes test patterns; flash wear-leveling may retain hidden spare blocks."
        else:
            f2_score = 0
            f2_desc = f"Method '{method.value}' provides no certified sanitization assurance."

        factors["supportedMethod"] = AssuranceFactor(
            name="Supported Sanitization Method",
            score=f2_score,
            max_score=25,
            description=f2_desc,
        )

        # Factor 3: Independent Verification Checks (Max 20)
        if verification_result.status == VerificationStatus.VERIFIED:
            f3_score = 20
            f3_desc = "All sample block entropy checks and wipe patterns verified clean across LBA range."
        elif verification_result.status == VerificationStatus.NOT_VERIFIED:
            f3_score = 5
            f3_desc = "Independent block verification found unverified, dirty, or inaccessible sectors."
        else:
            f3_score = 0
            f3_desc = "Independent verification failed entirely."

        factors["verificationChecks"] = AssuranceFactor(
            name="Verification Checks",
            score=f3_score,
            max_score=20,
            description=f3_desc,
        )

        # Factor 4: Device Identity Consistency (Max 10)
        if identity_consistent:
            f4_score = 10
            f4_desc = "Device serial, model, capacity, and bus path remained strictly invariant pre- and post-sanitization."
        else:
            f4_score = 0
            f4_desc = "Device identity attributes changed during execution lifecycle (potential swap or re-enumeration)."

        factors["identityConsistency"] = AssuranceFactor(
            name="Device Identity Consistency",
            score=f4_score,
            max_score=10,
            description=f4_desc,
        )

        # Factor 5: Audit Chain Integrity (Max 10)
        if audit_chain_valid:
            f5_score = 10
            f5_desc = "Cryptographic audit event log is unbroken, timestamped, and linked via SHA-256 hash chaining."
        else:
            f5_score = 0
            f5_desc = "Audit event log could not be cryptographically validated."

        factors["auditIntegrity"] = AssuranceFactor(
            name="Audit Integrity",
            score=f5_score,
            max_score=10,
            description=f5_desc,
        )

        total_score = sum(f.score for f in factors.values())

        if total_score >= 90:
            level = "EXEMPLARY"
            rationale = "Full hardware controller purge, zero-entropy sample verification, and unbroken audit chain."
        elif total_score >= 75:
            level = "HIGH"
            rationale = "High-assurance hardware sanitization verified with minor non-critical caveats."
        elif total_score >= 50:
            level = "MODERATE"
            rationale = "Moderate assurance; sanitization executed but lacks complete hardware-level verification."
        else:
            level = "INSUFFICIENT"
            rationale = "Sanitization assurance is insufficient to certify data destruction. Manual destruction recommended."

        return ForgeAssuranceScore(
            score=total_score,
            max_score=100,
            level=level,
            factors=factors,
            rationale=rationale,
        )

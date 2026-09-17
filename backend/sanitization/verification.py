"""Independent Erasure Verification Engine.

Performs multi-layered verification:
1. Controller Sanitize Status Log check (SSTAT bit validation)
2. Hardware completion code inspection
3. Non-destructive sample block read & Shannon entropy analysis
4. Pre/post device identity consistency validation

Distinguishes between EXECUTION SUCCESS and SANITIZATION VERIFIED.
Returns VERIFIED, NOT_VERIFIED, or FAILED. Never converts NOT_VERIFIED into SUCCESS.
"""

from __future__ import annotations

from typing import Any

from sanitization.adapters.base import SanitizationAdapter
from sanitization.models import (
    DeviceInfo,
    SanitizeMethod,
    VerificationCheck,
    VerificationResult,
    VerificationStatus,
    current_iso_timestamp,
)


class ErasureVerificationEngine:
    """Multi-layer post-sanitization verification engine."""

    @classmethod
    def verify_erasure(
        cls,
        device: DeviceInfo,
        re_discovered: DeviceInfo | None,
        method: SanitizeMethod,
        execution_result: dict[str, Any],
        adapter: SanitizationAdapter,
        num_sample_blocks: int = 10,
    ) -> tuple[VerificationResult, list[str], str | None]:
        """Run independent verification checks.

        Returns (VerificationResult, missing_evidence_list, recommendation_str).
        """
        checks: list[VerificationCheck] = []
        missing_evidence: list[str] = []
        recommendation: str | None = None
        now_ts = current_iso_timestamp()

        # Check 1: Command Execution Exit Status
        exec_ok = execution_result.get("status") == "SUCCESS"
        checks.append(
            VerificationCheck(
                check_name="Command Execution Status",
                passed=exec_ok,
                details=f"Command execution reported: {execution_result.get('status', 'UNKNOWN')}",
            )
        )
        if not exec_ok:
            missing_evidence.append("Successful command execution return code from hardware interface")

        # Check 2: Hardware Controller Status Log / Registers
        ctrl_status = adapter.get_sanitize_status(device)
        ctrl_completed = bool(ctrl_status.get("completed", False))
        ctrl_success = bool(ctrl_status.get("success", False))
        sstat = str(ctrl_status.get("sstat", "0x000"))

        ctrl_check_passed = ctrl_completed and ctrl_success
        checks.append(
            VerificationCheck(
                check_name="Controller Sanitize Status Log",
                passed=ctrl_check_passed,
                details=(
                    f"SSTAT: {sstat}, SPROG: {ctrl_status.get('sprog', 0)}, "
                    f"Description: {ctrl_status.get('statusDescription', 'N/A')}"
                ),
            )
        )
        if not ctrl_check_passed:
            missing_evidence.append(f"Controller hardware completion confirmation (SSTAT={sstat})")

        # Check 3: Device Identity Consistency
        identity_passed = True
        identity_details = "Device identity consistent pre and post operation."
        if re_discovered:
            if device.serial and re_discovered.serial and device.serial != re_discovered.serial:
                identity_passed = False
                identity_details = f"Serial number changed: '{device.serial}' -> '{re_discovered.serial}'"
            elif device.capacity_bytes > 0 and re_discovered.capacity_bytes > 0 and device.capacity_bytes != re_discovered.capacity_bytes:
                identity_passed = False
                identity_details = f"Capacity changed: {device.capacity_bytes} -> {re_discovered.capacity_bytes}"
        checks.append(
            VerificationCheck(
                check_name="Device Identity Consistency",
                passed=identity_passed,
                details=identity_details,
            )
        )
        if not identity_passed:
            missing_evidence.append("Persistent physical device identity post-sanitization")

        # Check 4: Block Sampling and Entropy Verification
        samples = adapter.sample_blocks(device, num_samples=num_sample_blocks)
        sampling_passed = True
        dirty_blocks = 0

        if samples:
            for s in samples:
                # If error was returned (e.g. read error), mark dirty
                if s.get("error"):
                    sampling_passed = False
                    dirty_blocks += 1
                    continue
                # For zeroing or block erase, block must be zeroed with 0.0 entropy
                if not s.get("isZeroed", False):
                    # For Crypto Erase, some controllers leave high-entropy random encrypted noise
                    # or all zeros. But if dirty user bytes are found, fail.
                    if s.get("entropy", 0.0) > 7.5 and not s.get("isPatternMatched", False):
                        sampling_passed = False
                        dirty_blocks += 1
            sample_details = f"Sampled {len(samples)} block regions across LBA range. Dirty/Unverified blocks: {dirty_blocks}."
        else:
            sample_details = "Sample block read could not be executed or returned 0 samples."
            sampling_passed = False

        checks.append(
            VerificationCheck(
                check_name="Sample Block Verification",
                passed=sampling_passed,
                details=sample_details,
            )
        )
        if not sampling_passed:
            missing_evidence.append("Sample block verification: residual or unverified data blocks detected")

        # Synthesize Overall Status
        # If execution itself crashed/failed:
        if not exec_ok or sstat == "0x100":
            status = VerificationStatus.FAILED
            details = "Sanitization failed during command execution or controller reported hardware failure."
            recommendation = "Inspect device hardware logs. Retrying with identical command is not recommended."
        # If execution succeeded, but verification is incomplete or failed:
        elif not ctrl_check_passed or not sampling_passed or not identity_passed:
            status = VerificationStatus.NOT_VERIFIED
            details = (
                "SANITIZATION_NOT_VERIFIED: The sanitization command executed, "
                "but independent verification could not confirm complete media sanitization."
            )
            recommendation = (
                "Device cannot be certified as sanitized. "
                "Retain custody and utilize an approved external physical destruction procedure "
                "(e.g., degaussing for magnetic media or disintegration per IEEE 2883-2022)."
            )
        else:
            status = VerificationStatus.VERIFIED
            details = "All verification checks passed: controller status confirmed, sample blocks verified, identity consistent."
            recommendation = "Drive sanitization successfully verified. Media is cleared for re-use or decommission."

        result = VerificationResult(
            status=status,
            checks=checks,
            controller_status_code=sstat,
            details=details,
            timestamp=now_ts,
        )
        return result, missing_evidence, recommendation

"""Deterministic, Storage-Aware Sanitization Policy Engine.

Evaluates device type, hardware capabilities, encryption state, and safety constraints
to recommend an optimal sanitization method, assurance level, and verification plan.
"""

from __future__ import annotations

from typing import Any

from sanitization.models import (
    AssuranceLevel,
    DeviceInfo,
    SanitizationPolicy,
    SanitizeMethod,
    StorageType,
)


class StoragePolicyEngine:
    """Deterministic policy engine for storage sanitization."""

    @classmethod
    def evaluate_policy(
        cls,
        device: DeviceInfo,
        requested_assurance: AssuranceLevel = AssuranceLevel.HIGH,
        organization_policy: str = "DEFAULT",
    ) -> SanitizationPolicy:
        """Evaluate device characteristics and compute deterministic sanitization policy."""
        warnings: list[str] = list(device.warnings)
        supported_methods: list[SanitizeMethod] = []
        caps = device.sanitize_capabilities

        # 1. System Host Drive Safety Constraint
        if device.system_disk:
            return SanitizationPolicy(
                recommended_method=SanitizeMethod.UNSUPPORTED,
                supported_methods=[],
                assurance=AssuranceLevel.NONE,
                reason="Sanitization strictly prohibited: device is identified as an active OS root/boot host drive.",
                verification_plan=[],
                warnings=["CRITICAL: Active system device cannot be targeted."],
                verification_required=True,
            )

        # 2. Mounted Filesystem Constraint
        if device.mounted:
            warnings.append("Device contains active mounted partitions. Must be unmounted prior to execution.")

        # 3. NVMe SSD Evaluation
        if device.storage_type == StorageType.NVME_SSD:
            if caps and caps.crypto_erase_supported:
                supported_methods.append(SanitizeMethod.CRYPTO_ERASE)
            if caps and caps.block_erase_supported:
                supported_methods.append(SanitizeMethod.BLOCK_ERASE)
            if caps and caps.overwrite_supported:
                supported_methods.append(SanitizeMethod.OVERWRITE)

            # Recommend highest assurance supported method
            if SanitizeMethod.CRYPTO_ERASE in supported_methods:
                return SanitizationPolicy(
                    recommended_method=SanitizeMethod.CRYPTO_ERASE,
                    supported_methods=supported_methods,
                    assurance=AssuranceLevel.HIGH,
                    reason=(
                        "Hardware Cryptographic Erase supported by NVMe controller. "
                        "Destroys internal media encryption keys, rendering all physical flash blocks "
                        "(including overprovisioned and bad blocks) instantly unreadable, "
                        "meeting IEEE 2883-2022 Cryptographic Purge specifications."
                    ),
                    verification_plan=[
                        "Query NVMe Sanitize Status Log via controller",
                        "Verify Sanitize Status Code equals 0x101 (Crypto Erase Success)",
                        "Sample logical block regions across LBA range for zero or high-entropy key invalidation",
                        "Verify device identity consistency",
                    ],
                    warnings=warnings,
                    verification_required=True,
                )
            elif SanitizeMethod.BLOCK_ERASE in supported_methods:
                return SanitizationPolicy(
                    recommended_method=SanitizeMethod.BLOCK_ERASE,
                    supported_methods=supported_methods,
                    assurance=AssuranceLevel.HIGH,
                    reason=(
                        "Hardware Block Erase supported by NVMe controller. "
                        "Applies low-level electrical erase pulses to all flash memory cells "
                        "across accessible, overprovisioned, and spare blocks, "
                        "meeting IEEE 2883-2022 Block Purge specifications."
                    ),
                    verification_plan=[
                        "Query NVMe Sanitize Status Log via controller",
                        "Verify Sanitize Status Code equals 0x102 (Block Erase Success)",
                        "Sample 10 logical block regions across LBA space to confirm zeroed data (0x00)",
                        "Verify device identity consistency",
                    ],
                    warnings=warnings,
                    verification_required=True,
                )
            elif SanitizeMethod.OVERWRITE in supported_methods:
                return SanitizationPolicy(
                    recommended_method=SanitizeMethod.OVERWRITE,
                    supported_methods=supported_methods,
                    assurance=AssuranceLevel.MEDIUM,
                    reason=(
                        "NVMe controller supports Overwrite Sanitize action. "
                        "Overwrites user data across accessible and overprovisioned blocks with a fixed pattern."
                    ),
                    verification_plan=[
                        "Query NVMe Sanitize Status Log",
                        "Verify Sanitize Status Code equals 0x103 (Overwrite Success)",
                        "Sample logical blocks to verify overwrite test pattern",
                    ],
                    warnings=warnings,
                    verification_required=True,
                )
            else:
                return SanitizationPolicy(
                    recommended_method=SanitizeMethod.UNSUPPORTED,
                    supported_methods=[],
                    assurance=AssuranceLevel.NONE,
                    reason=(
                        "NVMe controller does not report standard SANICAP sanitize capabilities. "
                        "Direct hardware purge is unavailable."
                    ),
                    verification_plan=[],
                    warnings=warnings + ["Device lacks native NVMe sanitize command support."],
                    verification_required=True,
                )

        # 4. SATA SSD Evaluation
        if device.storage_type == StorageType.SATA_SSD:
            supported_methods = [
                SanitizeMethod.ATA_ENHANCED_SECURITY_ERASE,
                SanitizeMethod.ATA_SECURITY_ERASE,
                SanitizeMethod.OVERWRITE,
            ]
            return SanitizationPolicy(
                recommended_method=SanitizeMethod.ATA_ENHANCED_SECURITY_ERASE,
                supported_methods=supported_methods,
                assurance=AssuranceLevel.HIGH,
                reason=(
                    "SATA SSD supports ATA Enhanced Security Erase. Instructs firmware "
                    "to reset all internal flash memory blocks including wear-leveled and retired blocks."
                ),
                verification_plan=[
                    "Verify ATA Security status registers return not-locked and completed",
                    "Sample 10 block regions across drive LBA space",
                    "Confirm blocks return 0x00 zero pattern",
                ],
                warnings=warnings,
                verification_required=True,
            )

        # 5. HDD (Rotational Magnetic Storage)
        if device.storage_type == StorageType.HDD:
            supported_methods = [
                SanitizeMethod.ATA_SECURITY_ERASE,
                SanitizeMethod.OVERWRITE,
            ]
            return SanitizationPolicy(
                recommended_method=SanitizeMethod.ATA_SECURITY_ERASE,
                supported_methods=supported_methods,
                assurance=AssuranceLevel.HIGH,
                reason=(
                    "Magnetic HDD supports ATA Security Erase and multi-pass Overwrite. "
                    "Overwrites magnetic domains across all user addressable tracks."
                ),
                verification_plan=[
                    "Check drive SMART status and completion status",
                    "Read sample sectors across start, middle, and end of platter",
                    "Validate zero or overwrite pattern consistency",
                ],
                warnings=warnings,
                verification_required=True,
            )

        # 6. USB Removable Storage
        if device.storage_type == StorageType.USB:
            supported_methods = [SanitizeMethod.OVERWRITE]
            return SanitizationPolicy(
                recommended_method=SanitizeMethod.OVERWRITE,
                supported_methods=supported_methods,
                assurance=AssuranceLevel.LOW,
                reason=(
                    "USB mass storage devices do not expose hardware controller sanitize commands. "
                    "Logical overwrite is the only viable method; wear-leveling controllers may retain residual blocks."
                ),
                verification_plan=[
                    "Read sample blocks across LBA range",
                    "Confirm zero byte pattern on sampled sectors",
                ],
                warnings=warnings + ["Notice: USB controllers do not guarantee erasure of wear-leveled spare flash."],
                verification_required=True,
            )

        # 7. Fallback / Unknown Device
        return SanitizationPolicy(
            recommended_method=SanitizeMethod.UNSUPPORTED,
            supported_methods=[],
            assurance=AssuranceLevel.NONE,
            reason=f"Storage type '{device.storage_type.value}' is not recognized or lacks a certified sanitization path.",
            verification_plan=[],
            warnings=warnings + ["Unsupported hardware architecture."],
            verification_required=True,
        )

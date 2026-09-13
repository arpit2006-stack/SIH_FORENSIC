"""ATA / SATA Sanitization Adapter.

Provides SATA SSD and magnetic HDD sanitization abstraction using hdparm / ATA Security commands.
"""

from __future__ import annotations

import os
from typing import Any

from sanitization.adapters.base import SanitizationAdapter
from sanitization.adapters.nvme import calculate_entropy
from sanitization.discovery import _safe_run_cmd
from sanitization.models import (
    DeviceInfo,
    SafetyAuthorization,
    SanitizationErrorCode,
    SanitizationException,
    SanitizeCapabilityInfo,
    SanitizeMethod,
    StorageType,
    current_iso_timestamp,
)


class AtaSanitizationAdapter(SanitizationAdapter):
    """Adapter for SATA SSD and HDD storage devices."""

    def supports_device(self, device: DeviceInfo) -> bool:
        return (
            device.storage_type in (StorageType.SATA_SSD, StorageType.HDD)
            and "mock" not in device.device_path.lower()
            and "mock" not in device.model.lower()
        )

    def inspect_capabilities(self, device: DeviceInfo) -> SanitizeCapabilityInfo:
        cmd = ["hdparm", "-I", device.device_path]
        rc, stdout, _ = _safe_run_cmd(cmd)
        enhanced_supported = "enhanced erase" in stdout.lower()
        security_supported = "supported: security" in stdout.lower() or "security" in stdout.lower()
        return SanitizeCapabilityInfo(
            crypto_erase_supported=False,
            block_erase_supported=enhanced_supported,
            overwrite_supported=True,
            sanitize_command_supported=security_supported,
            raw_capabilities={"enhanced_erase": enhanced_supported, "security_supported": security_supported},
        )

    def generate_plan(self, device: DeviceInfo, method: SanitizeMethod) -> dict[str, Any]:
        dev = device.device_path
        if method == SanitizeMethod.ATA_ENHANCED_SECURITY_ERASE:
            cmd = f"hdparm --user-master u --security-set-pass ForensiPass {dev} && hdparm --user-master u --security-erase-enhanced ForensiPass {dev}"
        elif method == SanitizeMethod.ATA_SECURITY_ERASE:
            cmd = f"hdparm --user-master u --security-set-pass ForensiPass {dev} && hdparm --user-master u --security-erase ForensiPass {dev}"
        else:
            cmd = f"dd if=/dev/zero of={dev} bs=4M status=progress conv=fdatasync"

        return {
            "mode": "DRY_RUN",
            "device": dev,
            "method": method.value,
            "command": cmd,
            "destructive": True,
            "executed": False,
            "verificationPlan": [
                "Execute ATA security erase command sequence",
                "Verify hdparm security status shows not locked",
                "Sample 10 block regions across drive capacity",
                "Verify zero byte entropy",
            ],
            "simulated": False,
        }

    def execute_sanitize(
        self,
        device: DeviceInfo,
        method: SanitizeMethod,
        authorization: SafetyAuthorization,
    ) -> dict[str, Any]:
        dev = device.device_path
        start_time = current_iso_timestamp()

        if method in (SanitizeMethod.ATA_SECURITY_ERASE, SanitizeMethod.ATA_ENHANCED_SECURITY_ERASE):
            erase_flag = (
                "--security-erase-enhanced"
                if method == SanitizeMethod.ATA_ENHANCED_SECURITY_ERASE
                else "--security-erase"
            )
            # Step 1: set temp pass
            set_pass_cmd = ["hdparm", "--user-master", "u", "--security-set-pass", "ForensiPass", dev]
            rc1, _, err1 = _safe_run_cmd(set_pass_cmd)
            if rc1 != 0:
                raise SanitizationException(
                    SanitizationErrorCode.EXECUTION_FAILED,
                    f"ATA security-set-pass failed on {dev}: {err1.strip()}",
                )

            # Step 2: issue erase
            erase_cmd = ["hdparm", "--user-master", "u", erase_flag, "ForensiPass", dev]
            rc2, out2, err2 = _safe_run_cmd(erase_cmd, timeout_sec=180.0)
            if rc2 != 0:
                raise SanitizationException(
                    SanitizationErrorCode.EXECUTION_FAILED,
                    f"ATA security-erase command failed on {dev}: {err2.strip()}",
                )
            cmd_str = f"hdparm {erase_flag} {dev}"
        elif method == SanitizeMethod.OVERWRITE:
            # Overwrite via dd with isolated arguments
            dd_cmd = ["dd", "if=/dev/zero", f"of={dev}", "bs=4M", "conv=fdatasync", "status=none"]
            rc, out, err = _safe_run_cmd(dd_cmd, timeout_sec=300.0)
            if rc != 0:
                raise SanitizationException(
                    SanitizationErrorCode.EXECUTION_FAILED,
                    f"Overwrite command failed on {dev}: {err.strip()}",
                )
            cmd_str = f"dd if=/dev/zero of={dev} bs=4M"
        else:
            raise SanitizationException(
                SanitizationErrorCode.UNSUPPORTED_SANITIZATION,
                f"Method '{method.value}' not supported for ATA device.",
            )

        end_time = current_iso_timestamp()
        return {
            "status": "SUCCESS",
            "command": cmd_str,
            "devicePath": dev,
            "startTime": start_time,
            "completionTime": end_time,
            "simulated": False,
        }

    def get_sanitize_status(self, device: DeviceInfo) -> dict[str, Any]:
        cmd = ["hdparm", "-I", device.device_path]
        rc, stdout, _ = _safe_run_cmd(cmd)
        is_locked = "locked" in stdout.lower() and "not locked" not in stdout.lower()
        return {
            "sstat": "0x000" if is_locked else "0x101",
            "sprog": 100 if not is_locked else 0,
            "completed": not is_locked,
            "success": not is_locked,
            "statusDescription": "Device security unlocked and erase completed" if not is_locked else "Device locked",
        }

    def sample_blocks(
        self,
        device: DeviceInfo,
        num_samples: int = 10,
        sample_size: int = 4096,
    ) -> list[dict[str, Any]]:
        samples: list[dict[str, Any]] = []
        path = device.device_path
        if not os.path.exists(path):
            return samples
        try:
            total_bytes = device.capacity_bytes
            step = max(1, total_bytes // max(1, num_samples))
            with open(path, "rb") as f:
                for i in range(num_samples):
                    offset = i * step
                    f.seek(offset)
                    chunk = f.read(sample_size)
                    if not chunk:
                        break
                    is_zeroed = all(b == 0 for b in chunk)
                    samples.append(
                        {
                            "sampleIndex": i,
                            "byteOffset": offset,
                            "sizeBytes": len(chunk),
                            "isZeroed": is_zeroed,
                            "isPatternMatched": is_zeroed,
                            "entropy": calculate_entropy(chunk),
                            "previewHex": chunk[:16].hex(),
                        }
                    )
        except Exception as exc:
            samples.append({"sampleIndex": 0, "error": str(exc), "isZeroed": False})
        return samples

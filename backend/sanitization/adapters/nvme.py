"""NVMe Sanitization Adapter.

Interacts with NVMe controllers via nvme-cli using isolated subprocess arguments
(never raw concatenated shell strings), executes Sanitize actions, polls the
Sanitize Status Log, and performs non-destructive sample reads.
"""

from __future__ import annotations

import json
import math
import os
from typing import Any

from sanitization.adapters.base import SanitizationAdapter
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


def calculate_entropy(data: bytes) -> float:
    """Calculate Shannon Entropy (0.0 to 8.0) of a byte sequence."""
    if not data:
        return 0.0
    length = len(data)
    byte_counts = [0] * 256
    for b in data:
        byte_counts[b] += 1
    entropy = 0.0
    for count in byte_counts:
        if count > 0:
            prob = count / length
            entropy -= prob * math.log2(prob)
    return round(entropy, 4)


class NvmeSanitizationAdapter(SanitizationAdapter):
    """Adapter executing sanitize operations on NVMe storage devices."""

    ACTION_MAP = {
        SanitizeMethod.CRYPTO_ERASE: "start-crypto-erase",
        SanitizeMethod.BLOCK_ERASE: "start-block-erase",
        SanitizeMethod.OVERWRITE: "start-overwrite",
    }

    def supports_device(self, device: DeviceInfo) -> bool:
        return (
            device.storage_type == StorageType.NVME_SSD
            and "mock" not in device.device_path.lower()
            and "mock" not in device.model.lower()
        )

    def inspect_capabilities(self, device: DeviceInfo) -> SanitizeCapabilityInfo:
        ctrl = device.controller_path or device.device_path
        cmd = ["nvme", "id-ctrl", ctrl, "-o", "json"]
        rc, stdout, _ = _safe_run_cmd(cmd)
        if rc == 0 and stdout.strip():
            try:
                data = json.loads(stdout)
                sanicap = int(data.get("sanicap", 0))
                oacs = int(data.get("oacs", 0))
                return SanitizeCapabilityInfo(
                    crypto_erase_supported=bool(sanicap & 0x01),
                    block_erase_supported=bool(sanicap & 0x02),
                    overwrite_supported=bool(sanicap & 0x04),
                    sanitize_command_supported=(sanicap > 0) or bool(oacs & (1 << 9)),
                    no_deallocate_modifies_media=bool(sanicap & (1 << 29)),
                    raw_capabilities=data,
                )
            except (json.JSONDecodeError, ValueError):
                pass
        return SanitizeCapabilityInfo(
            crypto_erase_supported=False,
            block_erase_supported=False,
            overwrite_supported=False,
            sanitize_command_supported=False,
        )

    def generate_plan(self, device: DeviceInfo, method: SanitizeMethod) -> dict[str, Any]:
        ctrl = device.controller_path or device.device_path
        action = self.ACTION_MAP.get(method, "start-crypto-erase")
        intended_command = f"nvme sanitize {ctrl} --sanact={action}"
        return {
            "mode": "DRY_RUN",
            "device": device.device_path,
            "controller": ctrl,
            "method": method.value,
            "command": intended_command,
            "destructive": True,
            "executed": False,
            "verificationPlan": [
                f"Issue {intended_command}",
                f"Poll sanitize-log on controller {ctrl} until completion",
                "Verify sanitize status code (0x101 for crypto, 0x102 for block, 0x103 for overwrite)",
                "Sample 10 block regions across device capacity and verify entropy / zeroing",
                "Re-check device serial and model identity to ensure persistence",
            ],
            "simulated": False,
        }

    def execute_sanitize(
        self,
        device: DeviceInfo,
        method: SanitizeMethod,
        authorization: SafetyAuthorization,
    ) -> dict[str, Any]:
        ctrl = device.controller_path or device.device_path
        action = self.ACTION_MAP.get(method)
        if not action:
            raise SanitizationException(
                SanitizationErrorCode.UNSUPPORTED_SANITIZATION,
                f"Sanitization method '{method.value}' is not supported for NVMe.",
                {"method": method.value},
            )

        start_time = current_iso_timestamp()
        # Strictly use list of arguments - never string formatting with shell=True
        cmd = ["nvme", "sanitize", ctrl, f"--sanact={action}"]
        rc, stdout, stderr = _safe_run_cmd(cmd, timeout_sec=60.0)

        if rc != 0:
            raise SanitizationException(
                SanitizationErrorCode.EXECUTION_FAILED,
                f"NVMe sanitize command failed with code {rc}: {stderr.strip()}",
                {"controller": ctrl, "command": " ".join(cmd), "stderr": stderr},
            )

        end_time = current_iso_timestamp()
        return {
            "status": "SUCCESS",
            "command": " ".join(cmd),
            "devicePath": device.device_path,
            "controllerPath": ctrl,
            "action": action,
            "startTime": start_time,
            "completionTime": end_time,
            "stdout": stdout.strip(),
            "simulated": False,
        }

    def get_sanitize_status(self, device: DeviceInfo) -> dict[str, Any]:
        ctrl = device.controller_path or device.device_path
        cmd = ["nvme", "sanitize-log", ctrl, "-o", "json"]
        rc, stdout, stderr = _safe_run_cmd(cmd, timeout_sec=15.0)

        if rc != 0 or not stdout.strip():
            return {
                "sprog": 0,
                "sstat": "0x000",
                "statusDescription": f"Querying sanitize-log failed: {stderr.strip()}",
                "completed": False,
                "success": False,
            }

        try:
            data = json.loads(stdout)
            sstat_val = int(data.get("sstat", 0))
            sprog_val = int(data.get("sprog", 0))
            scopy_val = int(data.get("scopy", 0))

            # sstat bits 2:0 indicate status:
            # 0: Never sanitized
            # 1: Completed successfully
            # 2: In progress
            # 3: Failed
            status_code = sstat_val & 0x7
            is_completed = status_code == 1
            is_failed = status_code == 3
            is_in_progress = status_code == 2

            sstat_hex = f"0x{sstat_val:03x}"
            return {
                "sprog": sprog_val,
                "sstat": sstat_hex,
                "scopy": scopy_val,
                "completed": is_completed,
                "success": is_completed and not is_failed,
                "inProgress": is_in_progress,
                "statusDescription": (
                    "Sanitize operation completed successfully"
                    if is_completed
                    else ("Sanitize in progress" if is_in_progress else "Sanitize not completed")
                ),
                "raw": data,
            }
        except (json.JSONDecodeError, ValueError) as exc:
            return {
                "sprog": 0,
                "sstat": "0x000",
                "statusDescription": f"Failed to parse sanitize-log JSON: {exc}",
                "completed": False,
                "success": False,
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
                    ent = calculate_entropy(chunk)
                    samples.append(
                        {
                            "sampleIndex": i,
                            "byteOffset": offset,
                            "sizeBytes": len(chunk),
                            "isZeroed": is_zeroed,
                            "isPatternMatched": is_zeroed,
                            "entropy": ent,
                            "previewHex": chunk[:16].hex(),
                        }
                    )
        except (PermissionError, OSError) as exc:
            # When permissions do not allow raw reading, record informative warning check
            samples.append(
                {
                    "sampleIndex": 0,
                    "byteOffset": 0,
                    "sizeBytes": 0,
                    "isZeroed": False,
                    "isPatternMatched": False,
                    "entropy": 0.0,
                    "error": f"Sample read restricted by kernel: {exc}",
                }
            )
        return samples

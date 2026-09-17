"""Safety and Authorization Gate for Secure Drive Sanitization.

Enforces strict human operator authorization, system/root disk protection,
mounted filesystem locks, multi-attribute device identity re-verification,
and explicit destructive confirmation.
"""

from __future__ import annotations

import os
import platform
from typing import Any

from sanitization.models import (
    DeviceInfo,
    OperationMode,
    SafetyAuthorization,
    SanitizationErrorCode,
    SanitizationException,
    SanitizeMethod,
)


class SafetyGate:
    """Pre-execution safety gate validating all authorization and environmental conditions."""

    @classmethod
    def validate_authorization(
        cls,
        auth: SafetyAuthorization,
        device: DeviceInfo,
    ) -> None:
        """Validate all fields in SafetyAuthorization against target DeviceInfo.

        Raises SanitizationException with explicit error code if any constraint fails.
        """
        # 1. Operator and Case identification
        if not auth.operator_id or not auth.operator_id.strip():
            raise SanitizationException(
                SanitizationErrorCode.AUTHORIZATION_REQUIRED,
                "Operator ID is mandatory for chain of custody.",
                {"field": "operatorId"},
            )
        if not auth.case_id or not auth.case_id.strip():
            raise SanitizationException(
                SanitizationErrorCode.AUTHORIZATION_REQUIRED,
                "Case ID is mandatory for forensic chain of custody.",
                {"field": "caseId"},
            )
        if not auth.reason or not auth.reason.strip():
            raise SanitizationException(
                SanitizationErrorCode.AUTHORIZATION_REQUIRED,
                "Sanitization reason/justification is required.",
                {"field": "reason"},
            )

        # 2. Path verification
        if auth.device_path.strip().lower() != device.device_path.strip().lower():
            raise SanitizationException(
                SanitizationErrorCode.DEVICE_IDENTITY_MISMATCH,
                f"Authorized device path '{auth.device_path}' does not match target '{device.device_path}'.",
                {"authorizedPath": auth.device_path, "targetPath": device.device_path},
            )

        # 3. Model confirmation check
        if device.model and auth.model_confirmation.strip().lower() != device.model.strip().lower():
            raise SanitizationException(
                SanitizationErrorCode.DEVICE_IDENTITY_MISMATCH,
                f"Operator model confirmation '{auth.model_confirmation}' does not match actual hardware '{device.model}'.",
                {"expected": device.model, "provided": auth.model_confirmation},
            )

        # 4. Serial confirmation check
        if device.serial and auth.serial_confirmation.strip().lower() != device.serial.strip().lower():
            raise SanitizationException(
                SanitizationErrorCode.DEVICE_IDENTITY_MISMATCH,
                f"Operator serial confirmation '{auth.serial_confirmation}' does not match actual hardware '{device.serial}'.",
                {"expected": device.serial, "provided": auth.serial_confirmation},
            )

        # 5. Method check
        if auth.selected_method == SanitizeMethod.UNSUPPORTED:
            raise SanitizationException(
                SanitizationErrorCode.UNSUPPORTED_SANITIZATION,
                "Requested sanitization method is unsupported for this device.",
                {"method": auth.selected_method.value},
            )

        # 6. System Host Disk Protection
        if device.system_disk:
            raise SanitizationException(
                SanitizationErrorCode.DEVICE_IS_SYSTEM_DISK,
                f"DEVICE_IS_SYSTEM_DISK: Device '{device.device_path}' is an active OS root/boot host drive. "
                "Operation blocked by firmware/kernel safety gate.",
                {"devicePath": device.device_path, "systemDisk": True},
            )

        # 7. Mounted Filesystem Protection
        if device.mounted:
            raise SanitizationException(
                SanitizationErrorCode.DEVICE_MOUNTED,
                f"DEVICE_MOUNTED: Device '{device.device_path}' contains mounted partitions: {device.mount_points}. "
                "All filesystems must be unmounted before sanitization.",
                {"devicePath": device.device_path, "mountPoints": device.mount_points},
            )

        # 8. Destructive Confirmation for Real Execution
        if auth.execution_mode == OperationMode.REAL_EXECUTION:
            if not auth.explicit_destructive_confirmation:
                raise SanitizationException(
                    SanitizationErrorCode.DESTRUCTIVE_CONFIRMATION_MISSING,
                    "DESTRUCTIVE_CONFIRMATION_MISSING: Real execution requires explicit boolean confirmation.",
                    {"executionMode": auth.execution_mode.value},
                )
            cls.check_execution_privilege(device)

    @classmethod
    def verify_pre_execution_integrity(
        cls,
        initial_device: DeviceInfo,
        re_discovered: DeviceInfo,
    ) -> None:
        """Immediately before issuing raw sanitize commands, verify device has not been swapped or modified."""
        # Re-check system disk
        if re_discovered.system_disk:
            raise SanitizationException(
                SanitizationErrorCode.DEVICE_IS_SYSTEM_DISK,
                "Pre-execution re-check detected device has become or is an active system disk.",
                {"devicePath": re_discovered.device_path},
            )

        # Re-check mounted state
        if re_discovered.mounted:
            raise SanitizationException(
                SanitizationErrorCode.DEVICE_MOUNTED,
                "Pre-execution re-check detected device has mounted partitions.",
                {"devicePath": re_discovered.device_path, "mountPoints": re_discovered.mount_points},
            )

        # Verify serial consistency
        if initial_device.serial and re_discovered.serial:
            if initial_device.serial != re_discovered.serial:
                raise SanitizationException(
                    SanitizationErrorCode.DEVICE_IDENTITY_MISMATCH,
                    f"Pre-execution re-check serial mismatch: '{initial_device.serial}' != '{re_discovered.serial}'",
                    {"initial": initial_device.serial, "current": re_discovered.serial},
                )

        # Verify model consistency
        if initial_device.model and re_discovered.model:
            if initial_device.model != re_discovered.model:
                raise SanitizationException(
                    SanitizationErrorCode.DEVICE_IDENTITY_MISMATCH,
                    f"Pre-execution re-check model mismatch: '{initial_device.model}' != '{re_discovered.model}'",
                    {"initial": initial_device.model, "current": re_discovered.model},
                )

        # Verify capacity consistency
        if initial_device.capacity_bytes > 0 and re_discovered.capacity_bytes > 0:
            if initial_device.capacity_bytes != re_discovered.capacity_bytes:
                raise SanitizationException(
                    SanitizationErrorCode.DEVICE_IDENTITY_MISMATCH,
                    f"Pre-execution re-check capacity mismatch: {initial_device.capacity_bytes} != {re_discovered.capacity_bytes}",
                    {"initial": initial_device.capacity_bytes, "current": re_discovered.capacity_bytes},
                )

    @classmethod
    def check_execution_privilege(cls, device: DeviceInfo) -> None:
        """Verify operating system privileges for real block device execution."""
        # Mock devices run without OS root privileges
        if "mock" in device.device_path.lower() or "mock" in device.model.lower():
            return

        current_os = platform.system().lower()
        if current_os == "linux":
            if os.geteuid() != 0:
                raise SanitizationException(
                    SanitizationErrorCode.PRIVILEGE_REQUIRED,
                    "PRIVILEGE_REQUIRED: Real hardware sanitization requires root (EUID 0) privileges on Linux.",
                    {"required": "root"},
                )
        elif current_os == "darwin":
            if os.geteuid() != 0:
                raise SanitizationException(
                    SanitizationErrorCode.PRIVILEGE_REQUIRED,
                    "PRIVILEGE_REQUIRED: Real hardware sanitization requires root (sudo) privileges on macOS.",
                    {"required": "root"},
                )
        elif current_os == "windows":
            # On Windows, real physical disk access requires elevated administrator
            import ctypes
            try:
                is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
            except Exception:
                is_admin = False
            if not is_admin:
                raise SanitizationException(
                    SanitizationErrorCode.PRIVILEGE_REQUIRED,
                    "PRIVILEGE_REQUIRED: Real physical drive sanitization requires Administrator privileges on Windows.",
                    {"required": "Administrator"},
                )

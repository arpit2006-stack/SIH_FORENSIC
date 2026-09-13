"""Fallback adapter for unsupported storage hardware."""

from __future__ import annotations

from typing import Any

from sanitization.adapters.base import SanitizationAdapter
from sanitization.models import (
    DeviceInfo,
    SafetyAuthorization,
    SanitizationErrorCode,
    SanitizationException,
    SanitizeCapabilityInfo,
    SanitizeMethod,
)


class UnsupportedSanitizationAdapter(SanitizationAdapter):
    """Fallback adapter that explicitly rejects unsupported hardware."""

    def supports_device(self, device: DeviceInfo) -> bool:
        return True  # Fallback matches when other adapters don't

    def inspect_capabilities(self, device: DeviceInfo) -> SanitizeCapabilityInfo:
        return SanitizeCapabilityInfo(
            crypto_erase_supported=False,
            block_erase_supported=False,
            overwrite_supported=False,
            sanitize_command_supported=False,
            raw_capabilities={"unsupported": True},
        )

    def generate_plan(self, device: DeviceInfo, method: SanitizeMethod) -> dict[str, Any]:
        return {
            "mode": "DRY_RUN",
            "device": device.device_path,
            "method": "UNSUPPORTED",
            "command": "NONE",
            "destructive": False,
            "executed": False,
            "verificationPlan": [],
            "error": f"No certified sanitization adapter available for device type '{device.storage_type.value}'.",
        }

    def execute_sanitize(
        self,
        device: DeviceInfo,
        method: SanitizeMethod,
        authorization: SafetyAuthorization,
    ) -> dict[str, Any]:
        raise SanitizationException(
            SanitizationErrorCode.UNSUPPORTED_SANITIZATION,
            f"Device '{device.device_path}' has no supported sanitization path.",
            {"device": device.device_path, "type": device.storage_type.value},
        )

    def get_sanitize_status(self, device: DeviceInfo) -> dict[str, Any]:
        return {"completed": False, "success": False, "statusDescription": "Unsupported device"}

    def sample_blocks(
        self,
        device: DeviceInfo,
        num_samples: int = 10,
        sample_size: int = 4096,
    ) -> list[dict[str, Any]]:
        return []

"""Abstract base class for sanitization hardware adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sanitization.models import (
    DeviceInfo,
    SafetyAuthorization,
    SanitizeCapabilityInfo,
    SanitizeMethod,
)


class SanitizationAdapter(ABC):
    """Abstract interface that all device-specific sanitization adapters must implement."""

    @abstractmethod
    def supports_device(self, device: DeviceInfo) -> bool:
        """Return True if this adapter is capable of handling the specified device."""
        pass

    @abstractmethod
    def inspect_capabilities(self, device: DeviceInfo) -> SanitizeCapabilityInfo:
        """Query hardware controller and return granular sanitization capabilities."""
        pass

    @abstractmethod
    def generate_plan(self, device: DeviceInfo, method: SanitizeMethod) -> dict[str, Any]:
        """Return the dry-run plan containing command strings, parameters, and verification expectations."""
        pass

    @abstractmethod
    def execute_sanitize(
        self,
        device: DeviceInfo,
        method: SanitizeMethod,
        authorization: SafetyAuthorization,
    ) -> dict[str, Any]:
        """Execute the sanitization command on the storage device.

        Must only be called after all safety checks pass.
        Returns execution telemetry.
        """
        pass

    @abstractmethod
    def get_sanitize_status(self, device: DeviceInfo) -> dict[str, Any]:
        """Query the controller's sanitize status log / progress indicator."""
        pass

    @abstractmethod
    def sample_blocks(
        self,
        device: DeviceInfo,
        num_samples: int = 10,
        sample_size: int = 4096,
    ) -> list[dict[str, Any]]:
        """Read sample blocks from distinct regions (start, middle, end, pseudo-random)

        to verify whether data has been wiped (all zeros/all 0xFF/high entropy pattern)
        without causing an exhaustive full-disk read timeout.
        """
        pass

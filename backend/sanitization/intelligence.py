"""Storage Intelligence component.

Determines storage device type (NVMe SSD, SATA SSD, HDD, USB) and inspects
hardware controller sanitize capabilities (Crypto Erase, Block Erase, Overwrite)
via nvme-cli, sysfs, or platform interfaces.
"""

from __future__ import annotations

import json
import re
from typing import Any

from sanitization.discovery import _safe_run_cmd
from sanitization.models import (
    DeviceInfo,
    SanitizeCapabilityInfo,
    StorageType,
)


class StorageIntelligence:
    """Evaluates physical storage characteristics and controller capabilities."""

    @classmethod
    def classify_storage(
        cls,
        interface: str,
        rotational: bool,
        removable: bool,
        model: str,
    ) -> StorageType:
        """Deterministically classify device into StorageType."""
        iface = interface.upper()
        if "NVME" in iface:
            return StorageType.NVME_SSD
        if "USB" in iface or removable:
            return StorageType.USB
        if rotational:
            return StorageType.HDD
        if "SATA" in iface or "ATA" in iface or "SCSI" in iface:
            return StorageType.SATA_SSD
        # Check model hints
        m_lower = model.lower()
        if "nvme" in m_lower or "pcie" in m_lower:
            return StorageType.NVME_SSD
        if "ssd" in m_lower:
            return StorageType.SATA_SSD
        if "hdd" in m_lower:
            return StorageType.HDD
        return StorageType.UNKNOWN

    @classmethod
    def inspect_nvme_capabilities(cls, controller_path: str) -> SanitizeCapabilityInfo:
        """Query NVMe controller capabilities via nvme-cli id-ctrl command.

        Inspects the SANICAP (Sanitize Capabilities) 32-bit register:
          - Bit 0 (CES): Crypto Erase Support
          - Bit 1 (BES): Block Erase Support
          - Bit 2 (OWS): Overwrite Support
          - Bit 29 (NDMM): No-Deallocate Modifies Media
        """
        # Execute nvme id-ctrl <ctrl> -o json safely
        cmd = ["nvme", "id-ctrl", controller_path, "-o", "json"]
        rc, stdout, _ = _safe_run_cmd(cmd)

        if rc == 0 and stdout.strip():
            try:
                data = json.loads(stdout)
                sanicap = data.get("sanicap", 0)
                if isinstance(sanicap, str):
                    try:
                        sanicap = int(sanicap, 0)
                    except ValueError:
                        sanicap = 0

                oacs = data.get("oacs", 0)
                if isinstance(oacs, str):
                    try:
                        oacs = int(oacs, 0)
                    except ValueError:
                        oacs = 0

                crypto_support = bool(sanicap & 0x01)
                block_support = bool(sanicap & 0x02)
                overwrite_support = bool(sanicap & 0x04)
                ndmm = bool(sanicap & (1 << 29))
                # Sanitize command supported if any sanicap bit set or oacs bit 9 set
                sanitize_supported = (sanicap > 0) or bool(oacs & (1 << 9))

                return SanitizeCapabilityInfo(
                    crypto_erase_supported=crypto_support,
                    block_erase_supported=block_support,
                    overwrite_supported=overwrite_support,
                    sanitize_command_supported=sanitize_supported,
                    no_deallocate_modifies_media=ndmm,
                    raw_capabilities={
                        "sanicap": sanicap,
                        "oacs": oacs,
                        "mn": data.get("mn", ""),
                        "sn": data.get("sn", ""),
                        "fr": data.get("fr", ""),
                    },
                )
            except json.JSONDecodeError:
                pass

        # If nvme-cli command fails or controller path is not accessible directly,
        # return empty capability object
        return SanitizeCapabilityInfo(
            crypto_erase_supported=False,
            block_erase_supported=False,
            overwrite_supported=False,
            sanitize_command_supported=False,
            raw_capabilities={"error": "Controller capabilities query failed or unprivileged"},
        )

    @classmethod
    def enrich_device_capabilities(cls, device: DeviceInfo) -> DeviceInfo:
        """Enrich a DeviceInfo instance with hardware capabilities if not already present."""
        if device.sanitize_capabilities is not None:
            return device

        if device.storage_type == StorageType.NVME_SSD and device.controller_path:
            caps = cls.inspect_nvme_capabilities(device.controller_path)
            device.sanitize_capabilities = caps
        elif device.storage_type in (StorageType.SATA_SSD, StorageType.HDD):
            # SATA devices support ATA Security Erase and Overwrite
            device.sanitize_capabilities = SanitizeCapabilityInfo(
                crypto_erase_supported=False,
                block_erase_supported=False,
                overwrite_supported=True,
                sanitize_command_supported=False,
                raw_capabilities={"interface": device.interface},
            )
        elif device.storage_type == StorageType.USB:
            device.sanitize_capabilities = SanitizeCapabilityInfo(
                crypto_erase_supported=False,
                block_erase_supported=False,
                overwrite_supported=True,
                sanitize_command_supported=False,
                raw_capabilities={"interface": "USB"},
            )
        else:
            device.sanitize_capabilities = SanitizeCapabilityInfo()

        return device

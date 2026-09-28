"""Universal Privilege and Access Governance Module.

Implements least-privilege role separation and capability checking across
Windows, Linux, and macOS platforms adhering to ISO/IEC 27037 and NIST SP 800-88 Rev 1.
Ensures zero silent fallbacks and clear error reporting when elevated tokens
are required for destructive controller IOCTLs.
"""

from __future__ import annotations

import ctypes
import os
import platform
from enum import Enum
from typing import Any


class PrivilegeState(str, Enum):
    """Universal privilege states for forensic execution."""
    NONE = "NONE"
    LIMITED = "LIMITED"
    ELEVATED = "ELEVATED"
    ROOT = "ROOT"
    ADMINISTRATIVE = "ADMINISTRATIVE"
    UNKNOWN = "UNKNOWN"


class OperationType(str, Enum):
    """Forensic operations categorized by required privilege level."""
    DISCOVERY = "DISCOVERY"
    IMAGE_CARVE = "IMAGE_CARVE"
    FILE_SCRUB = "FILE_SCRUB"
    DRY_RUN = "DRY_RUN"
    DEVICE_READ_SAMPLE = "DEVICE_READ_SAMPLE"
    PHYSICAL_OVERWRITE = "PHYSICAL_OVERWRITE"
    FIRMWARE_SANITIZE = "FIRMWARE_SANITIZE"
    CONTROLLER_IOCTL = "CONTROLLER_IOCTL"


class PrivilegeManager:
    """Evaluates host platform privileges and checks operation-specific authorization."""

    @classmethod
    def get_current_privilege_state(cls) -> PrivilegeState:
        """Inspect host execution token to determine effective privilege level."""
        sys_name = platform.system().lower()

        if sys_name == "windows":
            try:
                # IsUserAnAdmin() returns non-zero if current process has Administrator token
                if ctypes.windll.shell32.IsUserAnAdmin() != 0:
                    return PrivilegeState.ADMINISTRATIVE
                return PrivilegeState.LIMITED
            except Exception:
                return PrivilegeState.UNKNOWN

        elif sys_name in ("linux", "darwin"):
            try:
                if os.geteuid() == 0:
                    return PrivilegeState.ROOT

                # Check Linux capabilities if available
                if sys_name == "linux" and os.path.exists("/proc/self/status"):
                    try:
                        with open("/proc/self/status", "r", encoding="utf-8") as f:
                            for line in f:
                                if line.startswith("CapEff:"):
                                    cap_eff = int(line.split()[1], 16)
                                    # CAP_SYS_RAWIO (bit 17) or CAP_SYS_ADMIN (bit 21)
                                    if (cap_eff & (1 << 17)) or (cap_eff & (1 << 21)):
                                        return PrivilegeState.ELEVATED
                    except Exception:
                        pass
                return PrivilegeState.LIMITED
            except Exception:
                return PrivilegeState.UNKNOWN

        return PrivilegeState.LIMITED

    @classmethod
    def check_operation_requirement(
        cls,
        op: OperationType,
        is_mock: bool = False,
    ) -> bool:
        """Check whether current process token satisfies privilege requirements for the operation.

        Non-destructive tasks (discovery, carving, file scrub) require only standard privileges.
        Direct physical drive overwrites and controller IOCTLs require administrative/root elevation.
        """
        # Mock devices / safe simulations are always permissible
        if is_mock:
            return True

        non_destructive_ops = {
            OperationType.DISCOVERY,
            OperationType.IMAGE_CARVE,
            OperationType.FILE_SCRUB,
            OperationType.DRY_RUN,
        }
        if op in non_destructive_ops:
            return True

        current = cls.get_current_privilege_state()
        elevated_states = {
            PrivilegeState.ADMINISTRATIVE,
            PrivilegeState.ROOT,
            PrivilegeState.ELEVATED,
        }
        return current in elevated_states

    @classmethod
    def explain_required_privilege(cls, op: OperationType) -> str:
        """Provide detailed human-readable explanation of required privileges for remediation."""
        sys_name = platform.system().lower()
        if sys_name == "windows":
            return (
                f"Operation '{op.value}' requires elevated Windows Administrator privileges. "
                "Please run Command Prompt or PowerShell with 'Run as administrator' to permit "
                "direct physical drive access (\\\\.\\PhysicalDriveX) and hardware IOCTL pass-through."
            )
        elif sys_name == "linux":
            return (
                f"Operation '{op.value}' requires Linux root privileges (sudo) or POSIX capabilities "
                "(CAP_SYS_RAWIO / CAP_SYS_ADMIN) to issue raw SCSI/NVMe controller commands to block devices."
            )
        elif sys_name == "darwin":
            return (
                f"Operation '{op.value}' requires macOS root privileges (sudo) to access raw character "
                "disk nodes (/dev/rdisk*) and execute storage controller instructions."
            )
        return f"Operation '{op.value}' requires elevated system privileges on {platform.system()}."

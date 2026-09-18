"""Device Discovery component supporting Linux, Windows, and Mock devices.

Safely discovers connected storage devices (/dev/nvme*, /dev/sd*, \\\\.\\PhysicalDriveX),
identifies system/root disks, active swap, mounted filesystems, bus interfaces,
and normalizes all attributes into a typed DeviceInfo model.
"""

from __future__ import annotations

import json
import os
import platform
import plistlib
import re
import subprocess
from pathlib import Path
from typing import Any

from sanitization.adapters.mock import MockSanitizationAdapter
from sanitization.models import (
    DeviceInfo,
    SanitizeCapabilityInfo,
    StorageType,
)


def _safe_run_cmd(cmd: list[str], timeout_sec: float = 10.0) -> tuple[int, str, str]:
    """Execute command safely without shell=True, returning (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_sec,
            shell=False,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except (subprocess.SubprocessError, FileNotFoundError, PermissionError) as exc:
        return -1, "", str(exc)


class LinuxDeviceDiscovery:
    """Linux block device discovery using /sys/block, lsblk, and nvme-cli."""

    SYSTEM_MOUNT_POINTS = {"/", "/boot", "/boot/efi", "/etc", "/var", "/usr"}

    def get_system_root_devices(self) -> set[str]:
        """Detect base block devices backing active root, boot, and swap filesystems."""
        system_devs: set[str] = set()

        # 1. Inspect /proc/mounts
        try:
            with open("/proc/mounts", "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        dev_path, mount_point = parts[0], parts[1]
                        if mount_point in self.SYSTEM_MOUNT_POINTS:
                            base = self._get_base_block_device(dev_path)
                            if base:
                                system_devs.add(base)
        except (OSError, UnicodeDecodeError):
            pass

        # 2. Inspect /proc/swaps
        try:
            with open("/proc/swaps", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("Filename"):
                        continue
                    parts = line.split()
                    if parts:
                        dev_path = parts[0]
                        base = self._get_base_block_device(dev_path)
                        if base:
                            system_devs.add(base)
        except (OSError, UnicodeDecodeError):
            pass

        return system_devs

    @staticmethod
    def _get_base_block_device(path: str) -> str | None:
        """Resolve partition path to parent block device (e.g. /dev/nvme0n1p2 -> /dev/nvme0n1, /dev/sda1 -> /dev/sda)."""
        if not path.startswith("/dev/"):
            return None
        name = os.path.basename(path)
        # NVMe partition: nvme0n1p1 -> nvme0n1
        m_nvme = re.match(r"^(nvme\d+n\d+)p\d+$", name)
        if m_nvme:
            return f"/dev/{m_nvme.group(1)}"
        # Standard disk partition: sda1 -> sda, vda2 -> vda
        m_sd = re.match(r"^([a-z]+)\d+$", name)
        if m_sd:
            return f"/dev/{m_sd.group(1)}"
        return path

    def discover(self) -> list[DeviceInfo]:
        """Discover all physical block devices on Linux."""
        devices: list[DeviceInfo] = []
        system_root_devs = self.get_system_root_devices()

        # Run lsblk to fetch JSON structured block tree
        cmd = [
            "lsblk",
            "-J",
            "-b",
            "-o",
            "NAME,PATH,TYPE,SIZE,ROTA,RM,MODEL,SERIAL,REV,VENDOR,MOUNTPOINTS,FSTYPE,PTTYPE,LOG-SEC,PHY-SEC,TRAN",
        ]
        rc, stdout, _ = _safe_run_cmd(cmd)
        if rc == 0 and stdout.strip():
            try:
                data = json.loads(stdout)
                for blk in data.get("blockdevices", []):
                    # Filter only top-level disks (ignore loops, ramdisks, cdroms)
                    blk_type = blk.get("type", "").lower()
                    if blk_type not in ("disk", "loop"):
                        continue
                    if blk.get("name", "").startswith(("loop", "ram", "zram")):
                        continue

                    dev_path = blk.get("path") or f"/dev/{blk.get('name')}"
                    info = self._parse_lsblk_device(blk, dev_path, system_root_devs)
                    devices.append(info)
                return devices
            except json.JSONDecodeError:
                pass

        # Fallback: scan /sys/block directly if lsblk is unavailable or failed
        devices.extend(self._scan_sys_block(system_root_devs))
        return devices

    def _parse_lsblk_device(
        self,
        blk: dict[str, Any],
        dev_path: str,
        system_root_devs: set[str],
    ) -> DeviceInfo:
        children = blk.get("children", [])
        all_mounts: list[str] = []
        all_fss: list[str] = []

        def collect_children(node: dict[str, Any]):
            mounts = node.get("mountpoints") or []
            if isinstance(mounts, list):
                for m in mounts:
                    if m and m not in all_mounts:
                        all_mounts.append(m)
            fstype = node.get("fstype")
            if fstype and fstype not in all_fss:
                all_fss.append(fstype)
            for ch in node.get("children", []):
                collect_children(ch)

        collect_children(blk)

        is_mounted = len(all_mounts) > 0
        is_system = (
            dev_path in system_root_devs
            or any(m in self.SYSTEM_MOUNT_POINTS for m in all_mounts)
        )

        tran = (blk.get("tran") or "").lower()
        is_nvme = "nvme" in dev_path or tran == "nvme"
        is_usb = tran == "usb" or bool(blk.get("rm"))
        is_rotational = blk.get("rota") == 1 or blk.get("rota") is True

        if is_nvme:
            storage_type = StorageType.NVME_SSD
            interface = "NVMe"
        elif is_usb:
            storage_type = StorageType.USB
            interface = "USB"
        elif is_rotational:
            storage_type = StorageType.HDD
            interface = tran.upper() if tran else "SATA"
        else:
            storage_type = StorageType.SATA_SSD
            interface = tran.upper() if tran else "SATA"

        # Determine NVMe controller path
        controller_path: str | None = None
        if is_nvme:
            m = re.match(r"^(/dev/nvme\d+)n\d+$", dev_path)
            if m:
                controller_path = m.group(1)

        warnings: list[str] = []
        if is_system:
            warnings.append("CRITICAL: Active system root/boot host drive. Sanitization prohibited.")
        if is_mounted:
            warnings.append("WARNING: Device contains active mounted filesystems.")

        return DeviceInfo(
            device_path=dev_path,
            controller_path=controller_path,
            storage_type=storage_type,
            vendor=(blk.get("vendor") or "").strip(),
            model=(blk.get("model") or "").strip(),
            serial=(blk.get("serial") or "").strip(),
            firmware=(blk.get("rev") or "").strip(),
            capacity_bytes=int(blk.get("size") or 0),
            logical_block_size=int(blk.get("log-sec") or 512),
            physical_block_size=int(blk.get("phy-sec") or 4096),
            interface=interface,
            filesystems=all_fss,
            mounted=is_mounted,
            mount_points=all_mounts,
            removable=bool(blk.get("rm", False)),
            system_disk=is_system,
            encryption="crypto_LUKS" in all_fss,
            warnings=warnings,
        )

    def _scan_sys_block(self, system_root_devs: set[str]) -> list[DeviceInfo]:
        """Direct fallback scanning of /sys/block directory."""
        devices: list[DeviceInfo] = []
        sys_block = Path("/sys/block")
        if not sys_block.exists():
            return devices

        for entry in sys_block.iterdir():
            name = entry.name
            if name.startswith(("loop", "ram", "zram", "sr")):
                continue

            dev_path = f"/dev/{name}"
            size_sectors = 0
            size_file = entry / "size"
            if size_file.exists():
                try:
                    size_sectors = int(size_file.read_text().strip())
                except ValueError:
                    pass

            is_system = dev_path in system_root_devs
            devices.append(
                DeviceInfo(
                    device_path=dev_path,
                    storage_type=StorageType.NVME_SSD if "nvme" in name else StorageType.SATA_SSD,
                    capacity_bytes=size_sectors * 512,
                    system_disk=is_system,
                    warnings=["CRITICAL: System drive"] if is_system else [],
                )
            )
        return devices


class WindowsDeviceDiscovery:
    """Windows storage discovery querying PowerShell Get-Disk and Get-Partition."""

    def discover(self) -> list[DeviceInfo]:
        devices: list[DeviceInfo] = []

        # PowerShell command retrieving detailed disk metadata as JSON
        ps_cmd = (
            "Get-Disk | Select-Object Number, FriendlyName, SerialNumber, "
            "Size, BusType, PartitionStyle, IsBoot, IsSystem, OperationalStatus | ConvertTo-Json -Compress"
        )
        rc, stdout, _ = _safe_run_cmd(["powershell.exe", "-NoProfile", "-Command", ps_cmd])
        if rc != 0 or not stdout.strip():
            # Fallback when powershell isn't reachable
            return devices

        try:
            data = json.loads(stdout)
            # PowerShell returns a single object if only 1 disk, or a list if multiple
            disks = data if isinstance(data, list) else [data]

            for d in disks:
                dev_num = d.get("Number")
                if dev_num is None:
                    continue

                dev_path = rf"\\.\PhysicalDrive{dev_num}"
                is_boot = bool(d.get("IsBoot", False))
                is_system = bool(d.get("IsSystem", False))
                is_system_disk = is_boot or is_system

                bus_type_raw = str(d.get("BusType", "")).upper()
                if "NVME" in bus_type_raw:
                    storage_type = StorageType.NVME_SSD
                    interface = "NVMe"
                elif "USB" in bus_type_raw:
                    storage_type = StorageType.USB
                    interface = "USB"
                elif "SATA" in bus_type_raw:
                    storage_type = StorageType.SATA_SSD
                    interface = "SATA"
                else:
                    storage_type = StorageType.UNKNOWN
                    interface = bus_type_raw or "UNKNOWN"

                # Check partition drive letters for this disk
                mounts, fss, is_mounted = self._get_partitions_for_disk(dev_num)
                if any(m.upper().startswith("C:") for m in mounts):
                    is_system_disk = True

                warnings = []
                if is_system_disk:
                    warnings.append("CRITICAL: Active Windows system root/boot disk. Sanitization prohibited.")
                if is_mounted:
                    warnings.append("WARNING: Drive has assigned drive letters / mounted volumes.")

                devices.append(
                    DeviceInfo(
                        device_path=dev_path,
                        controller_path=dev_path,
                        storage_type=storage_type,
                        vendor="",
                        model=str(d.get("FriendlyName", "")).strip(),
                        serial=str(d.get("SerialNumber", "")).strip(),
                        firmware="",
                        capacity_bytes=int(d.get("Size") or 0),
                        logical_block_size=512,
                        physical_block_size=4096,
                        interface=interface,
                        filesystems=fss,
                        mounted=is_mounted,
                        mount_points=mounts,
                        removable=bus_type_raw == "USB",
                        system_disk=is_system_disk,
                        encryption=False,
                        warnings=warnings,
                    )
                )
        except (json.JSONDecodeError, Exception):
            pass

        return devices

    def _get_partitions_for_disk(self, disk_number: int) -> tuple[list[str], list[str], bool]:
        """Fetch partition drive letters and filesystem types for a given Windows disk."""
        ps_cmd = (
            f"Get-Partition -DiskNumber {disk_number} | "
            "Select-Object DriveLetter, DiskNumber | ConvertTo-Json -Compress"
        )
        rc, stdout, _ = _safe_run_cmd(["powershell.exe", "-NoProfile", "-Command", ps_cmd])
        mounts: list[str] = []
        if rc == 0 and stdout.strip():
            try:
                pdata = json.loads(stdout)
                partitions = pdata if isinstance(pdata, list) else [pdata]
                for p in partitions:
                    letter = p.get("DriveLetter")
                    if letter and str(letter).strip():
                        mounts.append(f"{str(letter).strip()}:")
            except Exception:
                pass
        return mounts, ["NTFS"] if mounts else [], len(mounts) > 0


class MacOSDeviceDiscovery:
    """macOS storage discovery querying diskutil plist output."""

    SYSTEM_MOUNT_POINTS = {"/", "/System/Volumes/Data", "/System/Volumes/BaseSystem"}

    def get_system_root_disks(self) -> set[str]:
        """Detect base physical disk identifiers backing active macOS root/system APFS container."""
        system_disks: set[str] = set()

        # Query diskutil info -plist /
        rc, stdout, _ = _safe_run_cmd(["diskutil", "info", "-plist", "/"])
        if rc == 0 and stdout.strip():
            try:
                info = plistlib.loads(stdout.encode("utf-8"))
                parent = info.get("ParentWholeDisk") or info.get("DeviceIdentifier")
                if parent:
                    system_disks.add(f"/dev/{parent}")
                    system_disks.add(parent)
            except Exception:
                pass

        # Query mount command as fallback
        rc, stdout, _ = _safe_run_cmd(["mount"])
        if rc == 0 and stdout.strip():
            for line in stdout.splitlines():
                parts = line.split()
                if len(parts) >= 3 and parts[2] in self.SYSTEM_MOUNT_POINTS:
                    dev_node = parts[0]
                    m = re.match(r"^/dev/(disk\d+)", dev_node)
                    if m:
                        system_disks.add(f"/dev/{m.group(1)}")
                        system_disks.add(m.group(1))

        return system_disks

    def discover(self) -> list[DeviceInfo]:
        """Discover attached storage disks on macOS via diskutil."""
        devices: list[DeviceInfo] = []
        system_disks = self.get_system_root_disks()

        rc, stdout, _ = _safe_run_cmd(["diskutil", "list", "-plist"])
        if rc != 0 or not stdout.strip():
            return devices

        try:
            data = plistlib.loads(stdout.encode("utf-8"))
            whole_disks = data.get("WholeDisks", [])

            for disk_id in whole_disks:
                dev_node = f"/dev/{disk_id}"
                rc_info, info_out, _ = _safe_run_cmd(["diskutil", "info", "-plist", dev_node])
                if rc_info == 0 and info_out.strip():
                    try:
                        dinfo = plistlib.loads(info_out.encode("utf-8"))
                        dev = self._parse_diskutil_info(dinfo, dev_node, disk_id, system_disks)
                        devices.append(dev)
                    except Exception:
                        pass
        except Exception:
            pass

        return devices

    def _parse_diskutil_info(
        self,
        dinfo: dict[str, Any],
        dev_node: str,
        disk_id: str,
        system_disks: set[str],
    ) -> DeviceInfo:
        is_system = (
            dev_node in system_disks
            or disk_id in system_disks
            or bool(dinfo.get("Bootable", False) and dinfo.get("Internal", False) and bool(system_disks))
        )

        media_name = str(dinfo.get("MediaName") or dinfo.get("DeviceModel") or disk_id).strip()
        vendor = str(dinfo.get("DeviceVendor") or "").strip()
        bus = str(dinfo.get("BusProtocol") or "").upper()
        solid_state = bool(dinfo.get("SolidState", False))
        removable = bool(dinfo.get("Removable", False) or dinfo.get("Ejectable", False))
        internal = bool(dinfo.get("Internal", True))

        if "PCI" in bus or "NVME" in bus or "APPLE FABRIC" in bus or (internal and solid_state):
            storage_type = StorageType.NVME_SSD
            interface = "NVMe/PCIe"
        elif "USB" in bus or removable:
            storage_type = StorageType.USB
            interface = "USB"
        elif solid_state:
            storage_type = StorageType.SATA_SSD
            interface = bus or "SATA"
        else:
            storage_type = StorageType.HDD
            interface = bus or "SATA"

        mount_point = dinfo.get("MountPoint")
        mounts = [mount_point] if mount_point else []
        is_mounted = len(mounts) > 0

        filesystems = []
        fs = dinfo.get("FilesystemType") or dinfo.get("FilesystemName")
        if fs:
            filesystems.append(str(fs))

        warnings = []
        if is_system:
            warnings.append("CRITICAL: Active macOS system root/boot host drive. Sanitization prohibited.")
        if is_mounted:
            warnings.append("WARNING: Drive contains active mounted filesystems.")

        return DeviceInfo(
            device_path=dev_node,
            controller_path=dev_node,
            storage_type=storage_type,
            vendor=vendor,
            model=media_name,
            serial="",
            firmware="",
            capacity_bytes=int(dinfo.get("TotalSize") or 0),
            logical_block_size=int(dinfo.get("DeviceBlockSize") or 512),
            physical_block_size=4096,
            interface=interface,
            filesystems=filesystems,
            mounted=is_mounted,
            mount_points=mounts,
            removable=removable,
            system_disk=is_system,
            encryption=bool(dinfo.get("AESHardware", False) or dinfo.get("CoreStorageEncrypted", False)),
            warnings=warnings,
        )


class DeviceDiscoveryManager:
    """Unified cross-platform device discovery coordinator.

    Automatically uses LinuxDeviceDiscovery on Linux,
    WindowsDeviceDiscovery on Windows, MacOSDeviceDiscovery on macOS,
    and integrates MockSanitizationAdapter for SIH demonstrations and offline test fixtures.
    """

    def __init__(
        self,
        mock_adapter: MockSanitizationAdapter | None = None,
        enable_mock_devices: bool = False,
    ):
        self.mock_adapter = mock_adapter or MockSanitizationAdapter()
        self.enable_mock_devices = enable_mock_devices
        self.current_os = platform.system().lower()

        if self.current_os == "linux":
            self._native_provider = LinuxDeviceDiscovery()
        elif self.current_os == "windows":
            self._native_provider = WindowsDeviceDiscovery()
        elif self.current_os == "darwin":
            self._native_provider = MacOSDeviceDiscovery()
        else:
            self._native_provider = None

    def discover_devices(self, include_mock: bool | None = None) -> list[DeviceInfo]:
        """Discover all storage devices across physical hardware and registered mock devices."""
        should_mock = self.enable_mock_devices if include_mock is None else include_mock
        # Allow environment override FORENSIC_USE_MOCK_STORAGE
        env_mock = os.getenv("FORENSIC_USE_MOCK_STORAGE", "").lower() in ("1", "true", "yes")
        if env_mock:
            should_mock = True

        devices: list[DeviceInfo] = []

        # 1. Native physical discovery
        if self._native_provider:
            try:
                native_devs = self._native_provider.discover()
                devices.extend(native_devs)
            except Exception:
                pass

        # 2. Mock devices (always available for safe demonstration)
        if should_mock and self.mock_adapter:
            mock_devs = self.mock_adapter.list_devices()
            devices.extend(mock_devs)

        return devices

    def find_device_by_path(self, device_path: str) -> DeviceInfo | None:
        """Locate a single device by its exact device path."""
        for dev in self.discover_devices(include_mock=True):
            if dev.device_path.lower() == device_path.lower():
                return dev
        return None

    def verify_identity_consistency(
        self,
        expected: DeviceInfo,
        re_discovered: DeviceInfo,
    ) -> tuple[bool, list[str]]:
        """Verify device attributes have not changed dynamically before an operation.

        Returns (is_consistent, list_of_mismatch_reasons).
        """
        reasons: list[str] = []

        if expected.device_path != re_discovered.device_path:
            reasons.append(f"Device path changed: {expected.device_path} != {re_discovered.device_path}")

        # Serial number check
        if expected.serial and re_discovered.serial:
            if expected.serial != re_discovered.serial:
                reasons.append(f"Serial number mismatch: expected '{expected.serial}', got '{re_discovered.serial}'")

        # Model check
        if expected.model and re_discovered.model:
            if expected.model != re_discovered.model:
                reasons.append(f"Model mismatch: expected '{expected.model}', got '{re_discovered.model}'")

        # Capacity check
        if expected.capacity_bytes > 0 and re_discovered.capacity_bytes > 0:
            if expected.capacity_bytes != re_discovered.capacity_bytes:
                reasons.append(
                    f"Capacity mismatch: expected {expected.capacity_bytes} bytes, got {re_discovered.capacity_bytes}"
                )

        # Controller path check for NVMe
        if expected.controller_path and re_discovered.controller_path:
            if expected.controller_path != re_discovered.controller_path:
                reasons.append(
                    f"Controller mismatch: expected '{expected.controller_path}', got '{re_discovered.controller_path}'"
                )

        return (len(reasons) == 0, reasons)

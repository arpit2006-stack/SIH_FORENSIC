"""Unit tests for Device Discovery and Storage Detection."""

import json
import plistlib
from unittest import TestCase
from unittest.mock import MagicMock, patch

from sanitization.adapters.mock import MockNVMeDevice, MockSanitizationAdapter
from sanitization.discovery import (
    DeviceDiscoveryManager,
    LinuxDeviceDiscovery,
    MacOSDeviceDiscovery,
    WindowsDeviceDiscovery,
)
from sanitization.models import DeviceInfo, StorageType


class TestLinuxDeviceDiscovery(TestCase):
    def setUp(self):
        self.discovery = LinuxDeviceDiscovery()

    @patch("sanitization.discovery._safe_run_cmd")
    def test_parse_lsblk_nvme_and_sata(self, mock_cmd):
        mock_lsblk_json = {
            "blockdevices": [
                {
                    "name": "nvme0n1",
                    "path": "/dev/nvme0n1",
                    "type": "disk",
                    "size": 1000204886016,
                    "rota": False,
                    "rm": False,
                    "model": "Samsung SSD 980 PRO 1TB",
                    "serial": "S5GXNF0R123456",
                    "rev": "5B2QGXA7",
                    "vendor": "Samsung",
                    "mountpoints": [],
                    "fstype": None,
                    "tran": "nvme",
                    "children": [],
                },
                {
                    "name": "sda",
                    "path": "/dev/sda",
                    "type": "disk",
                    "size": 500107862016,
                    "rota": True,
                    "rm": False,
                    "model": "WDC WD5000AAKX",
                    "serial": "WD-WCC2E1234567",
                    "rev": "01.01A01",
                    "vendor": "WDC",
                    "mountpoints": [],
                    "fstype": None,
                    "tran": "sata",
                    "children": [
                        {
                            "name": "sda1",
                            "path": "/dev/sda1",
                            "type": "part",
                            "size": 500106813440,
                            "mountpoints": ["/mnt/backup"],
                            "fstype": "ext4",
                        }
                    ],
                },
            ]
        }
        mock_cmd.return_value = (0, json.dumps(mock_lsblk_json), "")

        devices = self.discovery.discover()
        self.assertEqual(len(devices), 2)

        # Verify NVMe device
        nvme_dev = next(d for d in devices if d.device_path == "/dev/nvme0n1")
        self.assertEqual(nvme_dev.storage_type, StorageType.NVME_SSD)
        self.assertEqual(nvme_dev.controller_path, "/dev/nvme0")
        self.assertEqual(nvme_dev.model, "Samsung SSD 980 PRO 1TB")
        self.assertEqual(nvme_dev.serial, "S5GXNF0R123456")
        self.assertFalse(nvme_dev.mounted)

        # Verify SATA HDD
        sata_dev = next(d for d in devices if d.device_path == "/dev/sda")
        self.assertEqual(sata_dev.storage_type, StorageType.HDD)
        self.assertEqual(sata_dev.model, "WDC WD5000AAKX")
        self.assertTrue(sata_dev.mounted)
        self.assertIn("/mnt/backup", sata_dev.mount_points)

    def test_base_block_device_resolution(self):
        self.assertEqual(LinuxDeviceDiscovery._get_base_block_device("/dev/nvme0n1p2"), "/dev/nvme0n1")
        self.assertEqual(LinuxDeviceDiscovery._get_base_block_device("/dev/sda1"), "/dev/sda")
        self.assertEqual(LinuxDeviceDiscovery._get_base_block_device("/dev/vda3"), "/dev/vda")


class TestWindowsDeviceDiscovery(TestCase):
    def setUp(self):
        self.discovery = WindowsDeviceDiscovery()

    @patch("sanitization.discovery._safe_run_cmd")
    def test_parse_windows_powershell_disks(self, mock_cmd):
        mock_disks = [
            {
                "Number": 0,
                "FriendlyName": "NVMe Samsung SSD 970 EVO 500GB",
                "SerialNumber": "S466NF0M101010",
                "Size": 500107862016,
                "BusType": "NVMe",
                "IsBoot": True,
                "IsSystem": True,
                "OperationalStatus": "OK",
            },
            {
                "Number": 1,
                "FriendlyName": "Crucial CT1000MX500SSD1",
                "SerialNumber": "2104E4B56789",
                "Size": 1000204886016,
                "BusType": "SATA",
                "IsBoot": False,
                "IsSystem": False,
                "OperationalStatus": "OK",
            },
        ]

        def cmd_side_effect(cmd, **kwargs):
            if "Get-Disk" in " ".join(cmd):
                return (0, json.dumps(mock_disks), "")
            if "Get-Partition" in " ".join(cmd):
                if "-DiskNumber 0" in " ".join(cmd):
                    return (0, json.dumps([{"DriveLetter": "C", "DiskNumber": 0}]), "")
                return (0, json.dumps([{"DriveLetter": "D", "DiskNumber": 1}]), "")
            return (1, "", "unknown")

        mock_cmd.side_effect = cmd_side_effect

        devices = self.discovery.discover()
        self.assertEqual(len(devices), 2)

        # Disk 0 must be flagged as system disk
        d0 = next(d for d in devices if d.device_path == r"\\.\PhysicalDrive0")
        self.assertTrue(d0.system_disk)
        self.assertEqual(d0.storage_type, StorageType.NVME_SSD)
        self.assertIn("C:", d0.mount_points)

        # Disk 1 is target data drive
        d1 = next(d for d in devices if d.device_path == r"\\.\PhysicalDrive1")
        self.assertFalse(d1.system_disk)
        self.assertEqual(d1.storage_type, StorageType.SATA_SSD)
        self.assertIn("D:", d1.mount_points)


class TestMacOSDeviceDiscovery(TestCase):
    def setUp(self):
        self.discovery = MacOSDeviceDiscovery()

    @patch("sanitization.discovery._safe_run_cmd")
    def test_discover_macos_disks(self, mock_cmd):
        root_plist = plistlib.dumps({"ParentWholeDisk": "disk0", "DeviceIdentifier": "disk0s1"}).decode("utf-8")
        list_plist = plistlib.dumps({"WholeDisks": ["disk0", "disk1"]}).decode("utf-8")
        disk0_plist = plistlib.dumps(
            {
                "MediaName": "APPLE SSD AP1024Z",
                "DeviceVendor": "Apple",
                "BusProtocol": "PCI-Express",
                "SolidState": True,
                "Internal": True,
                "TotalSize": 1000204886016,
                "DeviceBlockSize": 4096,
                "MountPoint": "/System/Volumes/Data",
                "Bootable": True,
                "Removable": False,
            }
        ).decode("utf-8")
        disk1_plist = plistlib.dumps(
            {
                "MediaName": "SanDisk Extreme SSD",
                "DeviceVendor": "SanDisk",
                "BusProtocol": "USB",
                "SolidState": True,
                "Internal": False,
                "TotalSize": 500107862016,
                "DeviceBlockSize": 512,
                "MountPoint": "/Volumes/Extreme",
                "Bootable": False,
                "Removable": True,
            }
        ).decode("utf-8")

        def cmd_side_effect(cmd, **kwargs):
            if cmd == ["diskutil", "info", "-plist", "/"]:
                return (0, root_plist, "")
            if cmd == ["diskutil", "list", "-plist"]:
                return (0, list_plist, "")
            if cmd == ["diskutil", "info", "-plist", "/dev/disk0"]:
                return (0, disk0_plist, "")
            if cmd == ["diskutil", "info", "-plist", "/dev/disk1"]:
                return (0, disk1_plist, "")
            return (1, "", "failed")

        mock_cmd.side_effect = cmd_side_effect

        devices = self.discovery.discover()
        self.assertEqual(len(devices), 2)

        # disk0: APFS system root disk
        d0 = next(d for d in devices if d.device_path == "/dev/disk0")
        self.assertTrue(d0.system_disk)
        self.assertEqual(d0.storage_type, StorageType.NVME_SSD)
        self.assertEqual(d0.model, "APPLE SSD AP1024Z")
        self.assertTrue(any("Active macOS system root" in w for w in d0.warnings))

        # disk1: USB external disk
        d1 = next(d for d in devices if d.device_path == "/dev/disk1")
        self.assertFalse(d1.system_disk)
        self.assertEqual(d1.storage_type, StorageType.USB)
        self.assertEqual(d1.model, "SanDisk Extreme SSD")


class TestDeviceDiscoveryManager(TestCase):
    def setUp(self):
        self.mock_adapter = MockSanitizationAdapter()
        self.manager = DeviceDiscoveryManager(
            mock_adapter=self.mock_adapter,
            enable_mock_devices=True,
        )

    def test_discover_devices_contains_mock_devices(self):
        devices = self.manager.discover_devices(include_mock=True)
        self.assertGreater(len(devices), 0)
        paths = [d.device_path for d in devices]
        self.assertIn("/dev/mock_nvme0n1", paths)

    def test_find_device_by_path(self):
        dev = self.manager.find_device_by_path("/dev/mock_nvme0n1")
        self.assertIsNotNone(dev)
        self.assertEqual(dev.model, "Samsung SSD 980 PRO 1TB (MOCK)")
        self.assertEqual(dev.serial, "S5GXNF0R876543")

    def test_identity_consistency_check(self):
        original = DeviceInfo(
            device_path="/dev/nvme0n1",
            controller_path="/dev/nvme0",
            model="Samsung SSD 980 PRO 1TB",
            serial="S5GXNF0R123456",
            capacity_bytes=1000204886016,
        )

        # 1. Matching device passes
        consistent, reasons = self.manager.verify_identity_consistency(original, original)
        self.assertTrue(consistent)
        self.assertEqual(len(reasons), 0)

        # 2. Tampered serial number fails
        tampered_serial = DeviceInfo(
            device_path="/dev/nvme0n1",
            controller_path="/dev/nvme0",
            model="Samsung SSD 980 PRO 1TB",
            serial="DIFFERENT_SERIAL_999",
            capacity_bytes=1000204886016,
        )
        consistent, reasons = self.manager.verify_identity_consistency(original, tampered_serial)
        self.assertFalse(consistent)
        self.assertTrue(any("Serial number mismatch" in r for r in reasons))

        # 3. Capacity mismatch fails
        tampered_cap = DeviceInfo(
            device_path="/dev/nvme0n1",
            controller_path="/dev/nvme0",
            model="Samsung SSD 980 PRO 1TB",
            serial="S5GXNF0R123456",
            capacity_bytes=500107862016,
        )
        consistent, reasons = self.manager.verify_identity_consistency(original, tampered_cap)
        self.assertFalse(consistent)
        self.assertTrue(any("Capacity mismatch" in r for r in reasons))

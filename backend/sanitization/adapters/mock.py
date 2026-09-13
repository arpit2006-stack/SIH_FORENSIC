"""Mock NVMe Device and Adapter for safe, hardware-free testing and SIH demonstrations.

Simulates controller identity, SANICAP bitmasks, sanitize execution,
status log polling, completion queues, timeouts, and block sampling.
Works identically on both Linux and Windows.
"""

from __future__ import annotations

import time
from typing import Any

from sanitization.adapters.base import SanitizationAdapter
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


class MockNVMeDevice:
    """Represents a simulated NVMe hardware storage device."""

    def __init__(
        self,
        device_path: str = "/dev/mock_nvme0n1",
        controller_path: str = "/dev/mock_nvme0",
        vendor: str = "Samsung",
        model: str = "Samsung SSD 980 PRO 1TB (MOCK)",
        serial: str = "S5GXNF0R876543",
        firmware: str = "5B2QGXA7",
        capacity_bytes: int = 1_000_204_886_016,  # ~1TB
        logical_block_size: int = 512,
        physical_block_size: int = 4096,
        system_disk: bool = False,
        mounted: bool = False,
        mount_points: list[str] | None = None,
        removable: bool = False,
        crypto_erase_supported: bool = True,
        block_erase_supported: bool = True,
        overwrite_supported: bool = True,
        behavior_mode: str = "SUCCESS",  # "SUCCESS", "FAILURE", "TIMEOUT", "NOT_VERIFIED"
    ):
        self.device_path = device_path
        self.controller_path = controller_path
        self.vendor = vendor
        self.model = model
        self.serial = serial
        self.firmware = firmware
        self.capacity_bytes = capacity_bytes
        self.logical_block_size = logical_block_size
        self.physical_block_size = physical_block_size
        self.system_disk = system_disk
        self.mounted = mounted
        self.mount_points = mount_points or ([] if not mounted else ["/mnt/mock_data"])
        self.removable = removable
        self.crypto_erase_supported = crypto_erase_supported
        self.block_erase_supported = block_erase_supported
        self.overwrite_supported = overwrite_supported
        self.behavior_mode = behavior_mode

        # Runtime state
        self.current_state = "IDLE"  # "IDLE", "SANITIZING", "COMPLETED", "FAILED", "TIMEOUT"
        self.last_method: SanitizeMethod | None = None
        self.sanitize_count = 0
        self.execution_start_time: str | None = None
        self.execution_end_time: str | None = None

    def to_device_info(self) -> DeviceInfo:
        cap_info = SanitizeCapabilityInfo(
            crypto_erase_supported=self.crypto_erase_supported,
            block_erase_supported=self.block_erase_supported,
            overwrite_supported=self.overwrite_supported,
            sanitize_command_supported=True,
            no_deallocate_modifies_media=True,
            raw_capabilities={
                "sanicap": (
                    (0x01 if self.crypto_erase_supported else 0)
                    | (0x02 if self.block_erase_supported else 0)
                    | (0x04 if self.overwrite_supported else 0)
                ),
                "mock_controller": True,
                "behavior_mode": self.behavior_mode,
            },
        )
        return DeviceInfo(
            device_path=self.device_path,
            controller_path=self.controller_path,
            storage_type=StorageType.NVME_SSD,
            vendor=self.vendor,
            model=self.model,
            serial=self.serial,
            firmware=self.firmware,
            capacity_bytes=self.capacity_bytes,
            logical_block_size=self.logical_block_size,
            physical_block_size=self.physical_block_size,
            interface="NVMe",
            filesystems=["ext4"] if self.mounted else [],
            mounted=self.mounted,
            mount_points=list(self.mount_points),
            removable=self.removable,
            system_disk=self.system_disk,
            encryption=False,
            sanitize_capabilities=cap_info,
            warnings=[] if not self.system_disk else ["CRITICAL: Marked as system host drive"],
        )

    def execute_sanitize(self, method: SanitizeMethod) -> dict[str, Any]:
        self.execution_start_time = current_iso_timestamp()
        self.last_method = method

        if self.behavior_mode == "FAILURE":
            self.current_state = "FAILED"
            self.execution_end_time = current_iso_timestamp()
            raise SanitizationException(
                SanitizationErrorCode.EXECUTION_FAILED,
                f"Simulated hardware controller failure executing {method.value} on {self.device_path}",
                {"device": self.device_path, "status_code": "0x100"},
            )

        if self.behavior_mode == "TIMEOUT":
            self.current_state = "TIMEOUT"
            raise SanitizationException(
                SanitizationErrorCode.COMMAND_TIMEOUT,
                f"Simulated controller timeout during {method.value} on {self.device_path}",
                {"device": self.device_path, "timeout_seconds": 60},
            )

        # Successful or NOT_VERIFIED trigger
        self.current_state = "COMPLETED"
        self.sanitize_count += 1
        self.execution_end_time = current_iso_timestamp()

        # In NVMe, sanitize action is an asynchronous controller command
        action_name = method.value.lower()
        return {
            "status": "SUCCESS",
            "command": f"nvme sanitize {self.controller_path} --sanact={action_name}",
            "simulated": True,
            "action": action_name,
            "devicePath": self.device_path,
            "controllerPath": self.controller_path,
            "startTime": self.execution_start_time,
            "completionTime": self.execution_end_time,
            "controllerCode": "0x00",
            "sanitizeCount": self.sanitize_count,
        }

    def get_sanitize_status_log(self) -> dict[str, Any]:
        if self.current_state == "FAILED":
            return {
                "sprog": 0,
                "sstat": "0x100",  # Sanitize Failed
                "scopy": self.sanitize_count,
                "statusDescription": "Sanitize operation failed per controller log",
                "completed": False,
                "success": False,
            }

        if self.current_state == "TIMEOUT":
            return {
                "sprog": 32768,  # 50%
                "sstat": "0x002",  # Sanitize in progress
                "scopy": self.sanitize_count,
                "statusDescription": "Sanitize still running / timed out",
                "completed": False,
                "success": False,
            }

        if self.current_state == "COMPLETED":
            # 0x101: Crypto Erase completed successfully
            # 0x102: Block Erase completed successfully
            # 0x103: Overwrite completed successfully
            sstat_code = "0x101"
            if self.last_method == SanitizeMethod.BLOCK_ERASE:
                sstat_code = "0x102"
            elif self.last_method == SanitizeMethod.OVERWRITE:
                sstat_code = "0x103"

            return {
                "sprog": 65535,  # 100% complete in 16-bit field
                "sstat": sstat_code,
                "scopy": self.sanitize_count,
                "statusDescription": "Most Recent Sanitize Command Completed Successfully",
                "completed": True,
                "success": True,
            }

        return {
            "sprog": 0,
            "sstat": "0x000",
            "scopy": self.sanitize_count,
            "statusDescription": "Device has never been sanitized",
            "completed": False,
            "success": False,
        }

    def sample_blocks(self, num_samples: int = 10, sample_size: int = 4096) -> list[dict[str, Any]]:
        samples = []
        step = max(1, self.capacity_bytes // max(1, num_samples))

        for i in range(num_samples):
            lba_offset = i * step
            # If behavior_mode is NOT_VERIFIED, simulate dirty forensic remnant data
            if self.behavior_mode == "NOT_VERIFIED":
                samples.append(
                    {
                        "sampleIndex": i,
                        "byteOffset": lba_offset,
                        "sizeBytes": sample_size,
                        "isZeroed": False,
                        "isPatternMatched": False,
                        "entropy": 7.842,  # high entropy indicates remnant encrypted or compressed user data
                        "previewHex": "4155544f5245434f564552595f554e53414e4954495a4544",
                    }
                )
            else:
                # Proper sanitization: completely zeroed blocks
                samples.append(
                    {
                        "sampleIndex": i,
                        "byteOffset": lba_offset,
                        "sizeBytes": sample_size,
                        "isZeroed": True,
                        "isPatternMatched": True,
                        "entropy": 0.0,
                        "previewHex": "00000000000000000000000000000000",
                    }
                )
        return samples


class MockSanitizationAdapter(SanitizationAdapter):
    """Sanitization adapter handling simulated devices without physical hardware interaction."""

    def __init__(self, devices: list[MockNVMeDevice] | None = None):
        self._devices: dict[str, MockNVMeDevice] = {}
        if devices is None:
            self._init_default_devices()
        else:
            for d in devices:
                self.register_device(d)

    def _init_default_devices(self) -> None:
        """Register diverse standard mock devices for testing and demonstrations."""
        defaults = [
            # 1. Standard pristine NVMe drive ready for sanitization
            MockNVMeDevice(
                device_path="/dev/mock_nvme0n1",
                controller_path="/dev/mock_nvme0",
                vendor="Samsung",
                model="Samsung SSD 980 PRO 1TB (MOCK)",
                serial="S5GXNF0R876543",
                firmware="5B2QGXA7",
                capacity_bytes=1_000_204_886_016,
                behavior_mode="SUCCESS",
            ),
            # 2. Windows format mock drive
            MockNVMeDevice(
                device_path=r"\\.\PhysicalDrive9",
                controller_path=r"\\.\PhysicalDrive9",
                vendor="Western Digital",
                model="WD_BLACK SN850X 2TB (MOCK-WIN)",
                serial="231456801299",
                firmware="620361WD",
                capacity_bytes=2_000_398_934_016,
                behavior_mode="SUCCESS",
            ),
            # 3. System drive (should be blocked by safety gate)
            MockNVMeDevice(
                device_path="/dev/mock_system_nvme0n1",
                controller_path="/dev/mock_system_nvme0",
                vendor="Micron",
                model="Micron 3400 NVMe 512GB (OS-ROOT)",
                serial="MTR220199182",
                firmware="P4CR003",
                capacity_bytes=512_110_190_592,
                system_disk=True,
                mounted=True,
                mount_points=["/"],
            ),
            # 4. Mounted data drive (should be blocked until unmounted)
            MockNVMeDevice(
                device_path="/dev/mock_mounted_nvme1n1",
                controller_path="/dev/mock_nvme1",
                vendor="Kingston",
                model="Kingston KC3000 1TB (MOUNTED)",
                serial="50026B76850123",
                firmware="E18.2",
                capacity_bytes=1_024_209_543_168,
                mounted=True,
                mount_points=["/mnt/evidence_disk"],
            ),
            # 5. Device without crypto erase support (fallback to block erase)
            MockNVMeDevice(
                device_path="/dev/mock_nocrypto_nvme2n1",
                controller_path="/dev/mock_nvme2",
                vendor="Kioxia",
                model="Kioxia EXCERIA PLUS G2 500GB",
                serial="40XA12398711",
                firmware="EC02.1",
                capacity_bytes=500_107_862_016,
                crypto_erase_supported=False,
                block_erase_supported=True,
                overwrite_supported=True,
            ),
            # 6. Device simulating NOT_VERIFIED (hardware claims success, but residual data found)
            MockNVMeDevice(
                device_path="/dev/mock_unverified_nvme3n1",
                controller_path="/dev/mock_nvme3",
                vendor="Phison",
                model="Phison PS5018-E18 Reference (UNVERIFIED)",
                serial="PHIS20240901",
                firmware="PS18F01",
                capacity_bytes=256_060_514_304,
                behavior_mode="NOT_VERIFIED",
            ),
            # 7. Device simulating hardware failure
            MockNVMeDevice(
                device_path="/dev/mock_fail_nvme4n1",
                controller_path="/dev/mock_nvme4",
                vendor="SK Hynix",
                model="SK Hynix Platinum P41 (FAIL)",
                serial="SKH89234111",
                firmware="51060A20",
                capacity_bytes=1_000_204_886_016,
                behavior_mode="FAILURE",
            ),
            # 8. macOS format mock drive
            MockNVMeDevice(
                device_path="/dev/disk2",
                controller_path="/dev/disk2",
                vendor="Apple",
                model="Apple SSD AP0512M (MOCK-MAC)",
                serial="C02123456789MAC",
                firmware="240.0.0",
                capacity_bytes=500_107_862_016,
                behavior_mode="SUCCESS",
            ),
            # 9. macOS system root disk (APFS container)
            MockNVMeDevice(
                device_path="/dev/disk0",
                controller_path="/dev/disk0",
                vendor="Apple",
                model="Apple SSD AP1024Z (MAC-SYS)",
                serial="C02987654321SYS",
                firmware="240.0.0",
                capacity_bytes=1_000_204_886_016,
                system_disk=True,
                mounted=True,
                mount_points=["/", "/System/Volumes/Data"],
            ),
        ]
        for dev in defaults:
            self.register_device(dev)

    def register_device(self, device: MockNVMeDevice) -> None:
        self._devices[device.device_path] = device

    def get_device(self, device_path: str) -> MockNVMeDevice | None:
        return self._devices.get(device_path)

    def list_devices(self) -> list[DeviceInfo]:
        return [d.to_device_info() for d in self._devices.values()]

    def supports_device(self, device: DeviceInfo) -> bool:
        return (
            device.device_path in self._devices
            or "mock" in device.device_path.lower()
            or "mock" in device.model.lower()
        )

    def inspect_capabilities(self, device: DeviceInfo) -> SanitizeCapabilityInfo:
        mock_dev = self.get_device(device.device_path)
        if mock_dev:
            return mock_dev.to_device_info().sanitize_capabilities or SanitizeCapabilityInfo()
        return SanitizeCapabilityInfo(
            crypto_erase_supported=True,
            block_erase_supported=True,
            overwrite_supported=True,
            sanitize_command_supported=True,
            no_deallocate_modifies_media=True,
        )

    def generate_plan(self, device: DeviceInfo, method: SanitizeMethod) -> dict[str, Any]:
        mock_dev = self.get_device(device.device_path)
        ctrl = mock_dev.controller_path if mock_dev else (device.controller_path or device.device_path)
        action_map = {
            SanitizeMethod.CRYPTO_ERASE: "start-crypto-erase",
            SanitizeMethod.BLOCK_ERASE: "start-block-erase",
            SanitizeMethod.OVERWRITE: "start-overwrite",
        }
        action = action_map.get(method, "start-crypto-erase")
        return {
            "mode": "DRY_RUN",
            "device": device.device_path,
            "controller": ctrl,
            "method": method.value,
            "command": f"nvme sanitize {ctrl} --sanact={action}",
            "destructive": True,
            "executed": False,
            "verificationPlan": [
                "Poll NVMe Sanitize Status Log until completion",
                "Verify Sanitize Status Code (SSTAT) equals 0x101/0x102/0x103",
                "Sample 10 block regions across logical block space",
                "Confirm block entropy equals 0.0 or wipe pattern match",
                "Re-validate device identity to prevent mismatch",
            ],
            "simulated": True,
        }

    def execute_sanitize(
        self,
        device: DeviceInfo,
        method: SanitizeMethod,
        authorization: SafetyAuthorization,
    ) -> dict[str, Any]:
        mock_dev = self.get_device(device.device_path)
        if not mock_dev:
            raise SanitizationException(
                SanitizationErrorCode.DEVICE_NOT_FOUND,
                f"Mock device '{device.device_path}' not registered in MockSanitizationAdapter",
            )
        return mock_dev.execute_sanitize(method)

    def get_sanitize_status(self, device: DeviceInfo) -> dict[str, Any]:
        mock_dev = self.get_device(device.device_path)
        if not mock_dev:
            return {
                "sprog": 0,
                "sstat": "0x000",
                "statusDescription": "Device not found",
                "completed": False,
                "success": False,
            }
        return mock_dev.get_sanitize_status_log()

    def sample_blocks(
        self,
        device: DeviceInfo,
        num_samples: int = 10,
        sample_size: int = 4096,
    ) -> list[dict[str, Any]]:
        mock_dev = self.get_device(device.device_path)
        if not mock_dev:
            return []
        return mock_dev.sample_blocks(num_samples, sample_size)

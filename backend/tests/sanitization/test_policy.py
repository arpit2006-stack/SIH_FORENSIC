"""Unit tests for StoragePolicyEngine."""

from unittest import TestCase

from sanitization.models import (
    AssuranceLevel,
    DeviceInfo,
    SanitizeCapabilityInfo,
    SanitizeMethod,
    StorageType,
)
from sanitization.policy import StoragePolicyEngine


class TestStoragePolicyEngine(TestCase):
    def test_system_disk_policy_blocks_sanitization(self):
        dev = DeviceInfo(
            device_path="/dev/nvme0n1",
            storage_type=StorageType.NVME_SSD,
            system_disk=True,
            sanitize_capabilities=SanitizeCapabilityInfo(crypto_erase_supported=True),
        )
        policy = StoragePolicyEngine.evaluate_policy(dev)
        self.assertEqual(policy.recommended_method, SanitizeMethod.UNSUPPORTED)
        self.assertEqual(policy.assurance, AssuranceLevel.NONE)
        self.assertEqual(len(policy.supported_methods), 0)
        self.assertIn("root/boot", policy.reason)

    def test_nvme_crypto_erase_policy(self):
        dev = DeviceInfo(
            device_path="/dev/nvme0n1",
            storage_type=StorageType.NVME_SSD,
            system_disk=False,
            sanitize_capabilities=SanitizeCapabilityInfo(
                crypto_erase_supported=True,
                block_erase_supported=True,
                overwrite_supported=True,
            ),
        )
        policy = StoragePolicyEngine.evaluate_policy(dev)
        self.assertEqual(policy.recommended_method, SanitizeMethod.CRYPTO_ERASE)
        self.assertEqual(policy.assurance, AssuranceLevel.HIGH)
        self.assertIn(SanitizeMethod.CRYPTO_ERASE, policy.supported_methods)
        self.assertIn(SanitizeMethod.BLOCK_ERASE, policy.supported_methods)
        self.assertIn("Cryptographic Erase", policy.reason)

    def test_nvme_block_erase_fallback(self):
        dev = DeviceInfo(
            device_path="/dev/nvme0n1",
            storage_type=StorageType.NVME_SSD,
            system_disk=False,
            sanitize_capabilities=SanitizeCapabilityInfo(
                crypto_erase_supported=False,
                block_erase_supported=True,
                overwrite_supported=True,
            ),
        )
        policy = StoragePolicyEngine.evaluate_policy(dev)
        self.assertEqual(policy.recommended_method, SanitizeMethod.BLOCK_ERASE)
        self.assertEqual(policy.assurance, AssuranceLevel.HIGH)
        self.assertNotIn(SanitizeMethod.CRYPTO_ERASE, policy.supported_methods)
        self.assertIn(SanitizeMethod.BLOCK_ERASE, policy.supported_methods)

    def test_nvme_overwrite_only(self):
        dev = DeviceInfo(
            device_path="/dev/nvme0n1",
            storage_type=StorageType.NVME_SSD,
            system_disk=False,
            sanitize_capabilities=SanitizeCapabilityInfo(
                crypto_erase_supported=False,
                block_erase_supported=False,
                overwrite_supported=True,
            ),
        )
        policy = StoragePolicyEngine.evaluate_policy(dev)
        self.assertEqual(policy.recommended_method, SanitizeMethod.OVERWRITE)
        self.assertEqual(policy.assurance, AssuranceLevel.MEDIUM)

    def test_sata_ssd_policy(self):
        dev = DeviceInfo(
            device_path="/dev/sda",
            storage_type=StorageType.SATA_SSD,
            system_disk=False,
        )
        policy = StoragePolicyEngine.evaluate_policy(dev)
        self.assertEqual(policy.recommended_method, SanitizeMethod.ATA_ENHANCED_SECURITY_ERASE)
        self.assertEqual(policy.assurance, AssuranceLevel.HIGH)

    def test_hdd_policy(self):
        dev = DeviceInfo(
            device_path="/dev/sda",
            storage_type=StorageType.HDD,
            system_disk=False,
        )
        policy = StoragePolicyEngine.evaluate_policy(dev)
        self.assertEqual(policy.recommended_method, SanitizeMethod.ATA_SECURITY_ERASE)
        self.assertEqual(policy.assurance, AssuranceLevel.HIGH)

    def test_usb_policy(self):
        dev = DeviceInfo(
            device_path="/dev/sdb",
            storage_type=StorageType.USB,
            system_disk=False,
        )
        policy = StoragePolicyEngine.evaluate_policy(dev)
        self.assertEqual(policy.recommended_method, SanitizeMethod.OVERWRITE)
        self.assertEqual(policy.assurance, AssuranceLevel.LOW)

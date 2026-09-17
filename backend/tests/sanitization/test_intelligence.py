"""Unit tests for Storage Intelligence and NVMe capability inspection."""

import json
from unittest import TestCase
from unittest.mock import patch

from sanitization.intelligence import StorageIntelligence
from sanitization.models import (
    DeviceInfo,
    SanitizeCapabilityInfo,
    StorageType,
)


class TestStorageIntelligence(TestCase):
    def test_classify_storage(self):
        self.assertEqual(
            StorageIntelligence.classify_storage("NVME", rotational=False, removable=False, model="Samsung 980"),
            StorageType.NVME_SSD,
        )
        self.assertEqual(
            StorageIntelligence.classify_storage("USB", rotational=False, removable=True, model="SanDisk Ultra"),
            StorageType.USB,
        )
        self.assertEqual(
            StorageIntelligence.classify_storage("SATA", rotational=True, removable=False, model="Seagate Barracuda"),
            StorageType.HDD,
        )
        self.assertEqual(
            StorageIntelligence.classify_storage("SATA", rotational=False, removable=False, model="Crucial MX500 SSD"),
            StorageType.SATA_SSD,
        )

    @patch("sanitization.intelligence._safe_run_cmd")
    def test_inspect_nvme_capabilities_all_supported(self, mock_cmd):
        # 0x07 = 0x01 (Crypto) | 0x02 (Block) | 0x04 (Overwrite)
        mock_output = json.dumps({"sanicap": 7, "oacs": 512, "mn": "Samsung 980 PRO", "sn": "S123", "fr": "1.0"})
        mock_cmd.return_value = (0, mock_output, "")

        caps = StorageIntelligence.inspect_nvme_capabilities("/dev/nvme0")
        self.assertTrue(caps.crypto_erase_supported)
        self.assertTrue(caps.block_erase_supported)
        self.assertTrue(caps.overwrite_supported)
        self.assertTrue(caps.sanitize_command_supported)

    @patch("sanitization.intelligence._safe_run_cmd")
    def test_inspect_nvme_capabilities_crypto_only(self, mock_cmd):
        # 0x01 = Crypto only
        mock_output = json.dumps({"sanicap": 1, "oacs": 0})
        mock_cmd.return_value = (0, mock_output, "")

        caps = StorageIntelligence.inspect_nvme_capabilities("/dev/nvme0")
        self.assertTrue(caps.crypto_erase_supported)
        self.assertFalse(caps.block_erase_supported)
        self.assertFalse(caps.overwrite_supported)

    @patch("sanitization.intelligence._safe_run_cmd")
    def test_inspect_nvme_capabilities_none_supported(self, mock_cmd):
        mock_output = json.dumps({"sanicap": 0, "oacs": 0})
        mock_cmd.return_value = (0, mock_output, "")

        caps = StorageIntelligence.inspect_nvme_capabilities("/dev/nvme0")
        self.assertFalse(caps.crypto_erase_supported)
        self.assertFalse(caps.block_erase_supported)
        self.assertFalse(caps.overwrite_supported)
        self.assertFalse(caps.sanitize_command_supported)

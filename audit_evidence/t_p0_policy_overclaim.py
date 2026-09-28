"""P0-2: Does policy overclaim Purge-tier assurance for a device that cannot do it?"""
import sys; sys.path.insert(0, r"A:\SIH\SIH_FORENSIC\backend")
from sanitization.models import DeviceInfo, StorageType, SanitizeCapabilityInfo, AssuranceLevel
from sanitization.policy import StoragePolicyEngine

# A SATA SSD whose controller explicitly reports NO enhanced erase, NO security cmd support.
caps = SanitizeCapabilityInfo(
    crypto_erase_supported=False,
    block_erase_supported=False,      # <- no enhanced erase
    overwrite_supported=True,
    sanitize_command_supported=False, # <- ATA SECURITY feature set NOT supported
    raw_capabilities={"enhanced_erase": False, "security_supported": False},
)
dev = DeviceInfo(device_path="/dev/sdx", storage_type=StorageType.SATA_SSD,
                 model="CheapSSD", serial="SN123", capacity_bytes=128*1024**3,
                 sanitize_capabilities=caps)
p = StoragePolicyEngine.evaluate_policy(dev)
print("SATA_SSD, caps say NO enhanced erase / NO security cmd:")
print("  recommended_method :", p.recommended_method.value)
print("  assurance          :", p.assurance.value)
print("  reason             :", p.reason[:120])
print("  VERDICT: OVERCLAIM" if p.assurance == AssuranceLevel.HIGH else "  ok")

# HDD with no capabilities at all
dev2 = DeviceInfo(device_path="/dev/sdy", storage_type=StorageType.HDD, model="OldHDD",
                  serial="SN999", capacity_bytes=500*1024**3, sanitize_capabilities=None)
p2 = StoragePolicyEngine.evaluate_policy(dev2)
print("\nHDD, sanitize_capabilities=None (never probed):")
print("  recommended_method :", p2.recommended_method.value)
print("  assurance          :", p2.assurance.value)
print("  VERDICT: OVERCLAIM" if p2.assurance == AssuranceLevel.HIGH else "  ok")

# Does the codebase have any Clear/Purge/Destruct taxonomy at all?
print("\nAssuranceLevel members:", [a.value for a in AssuranceLevel])

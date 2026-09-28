"""P0-3: Is post-erase verification an independent re-read, or self-attestation?"""
import sys; sys.path.insert(0, r"A:\SIH\SIH_FORENSIC\backend")
from sanitization.adapters.ata import AtaSanitizationAdapter
from sanitization.models import DeviceInfo, StorageType, SanitizeMethod, VerificationStatus
from sanitization.verification import ErasureVerificationEngine

a = AtaSanitizationAdapter()
for st in (StorageType.USB, StorageType.SATA_SSD, StorageType.HDD):
    d = DeviceInfo(device_path="/dev/nonexistent-never-touched", storage_type=st,
                   model="M", serial="S", capacity_bytes=1000)
    print(f"{st.value:10s} get_sanitize_status on a device that was NEVER erased and does not exist:")
    print("          ", a.get_sanitize_status(d))

print("\n--- Now: does the entropy rule let residual PLAINTEXT pass? ---")
class FakeAdapter(AtaSanitizationAdapter):
    """Device still full of readable user data (low entropy, not zeroed)."""
    def get_sanitize_status(self, device):
        return {"sstat":"0x101","sprog":100,"completed":True,"success":True,"statusDescription":"done"}
    def sample_blocks(self, device, num_samples=10, sample_size=4096):
        payload = b"CONFIDENTIAL CASE FILE: victim name Jane Doe, acct 4111111111111111. " * 60
        from sanitization.adapters.nvme import calculate_entropy
        return [{"sampleIndex":i,"byteOffset":i*4096,"sizeBytes":4096,
                 "isZeroed":False,"isPatternMatched":False,
                 "entropy":calculate_entropy(payload[:4096]),
                 "previewHex":payload[:16].hex()} for i in range(10)]

d = DeviceInfo(device_path="/dev/sdz", storage_type=StorageType.SATA_SSD, model="M",
               serial="S", capacity_bytes=4096*10)
res, missing, rec = ErasureVerificationEngine.verify_erasure(
    d, d, SanitizeMethod.ATA_ENHANCED_SECURITY_ERASE, {"status":"SUCCESS"}, FakeAdapter())
from sanitization.adapters.nvme import calculate_entropy
print("sample entropy:", calculate_entropy(b"CONFIDENTIAL CASE FILE: victim name Jane Doe, acct 4111111111111111. "*60))
print("preview ascii :", b"CONFIDENTIAL CASE FILE: victim name Jane Doe..."[:46].decode())
print("VERIFICATION STATUS:", res.status.value)
print("details:", res.details)
print("missing evidence:", missing)
print("VERDICT: FAIL - readable plaintext certified as sanitized"
      if res.status == VerificationStatus.VERIFIED else "ok")

import sys; sys.path.insert(0, r"A:\SIH\SIH_FORENSIC\backend")
from sanitization.models import DeviceInfo, StorageType, SanitizeMethod, SafetyAuthorization, SanitizationException
from sanitization.policy import StoragePolicyEngine
from sanitization.adapters.unsupported import UnsupportedSanitizationAdapter
from sanitization.adapters.nvme import NvmeSanitizationAdapter
from sanitization.adapters.ata import AtaSanitizationAdapter

print("P2-2: genuinely unsupported media (optical / tape / unknown bus)")
d = DeviceInfo(device_path="/dev/sr0", storage_type=StorageType.UNKNOWN, model="ASUS DRW-24B1ST",
               serial="OPTICAL1", capacity_bytes=4_700_000_000)
print("  adapter match: nvme=%s ata=%s unsupported=%s" % (
    NvmeSanitizationAdapter().supports_device(d), AtaSanitizationAdapter().supports_device(d),
    UnsupportedSanitizationAdapter().supports_device(d)))
p = StoragePolicyEngine.evaluate_policy(d)
print("  policy ->", p.recommended_method.value, "| assurance", p.assurance.value, "|", p.warnings)
try:
    UnsupportedSanitizationAdapter().execute_sanitize(d, SanitizeMethod.OVERWRITE, SafetyAuthorization())
    print("  VERDICT: FAIL - executed silently")
except SanitizationException as e:
    print("  execute_sanitize raised:", e.code.value, "-", str(e)[:70])
    print("  VERDICT: PASS - explicit unsupported flag, no silent failure")

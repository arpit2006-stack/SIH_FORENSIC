"""P0-4/P0-5: slack-space wipe correctness, TRIM issuance, batch failure handling."""
import sys, os, tempfile, pathlib
sys.path.insert(0, r"A:\SIH\SIH_FORENSIC\backend")
from sanitization.file_eraser import SecureFileEraser, CLUSTER_SIZE

tmp = pathlib.Path(tempfile.mkdtemp())
f = tmp / "secret.txt"
data = b"TOPSECRET" * 100          # 900 bytes -> 3196 bytes of real slack in a 4096 cluster
f.write_bytes(data)
size_before = f.stat().st_size
e = SecureFileEraser()
slack = e.wipe_slack_space(f, size_before)
size_after = f.stat().st_size
print("=== wipe_slack_space ===")
print(f"  file size before : {size_before}")
print(f"  reported slack   : {slack}")
print(f"  file size AFTER  : {size_after}")
print(f"  EXPECTED if truly wiping slack: size unchanged ({size_before})")
print(f"  VERDICT: {'FAIL - it EXTENDED the file, it did not touch on-disk slack' if size_after != size_before else 'ok'}")
print(f"  note: cluster boundary math uses hardcoded CLUSTER_SIZE={CLUSTER_SIZE}, real FS cluster never queried")

print("\n=== TRIM / discard issuance ===")
import inspect, sanitization.file_eraser as fe
src = inspect.getsource(fe)
hits = [k for k in ("TRIM","trim","discard","fstrim","FSCTL","DeviceIoControl","ioctl","BLKDISCARD") if k in src]
print("  tokens found in file_eraser.py:", hits or "NONE")
print("  VERDICT: FAIL - no TRIM/discard is ever issued; result still reports status=COMPLETED" if not hits else "ok")

print("\n=== batch mid-failure handling (P2) ===")
d = tmp / "batch"; d.mkdir()
for n in ("a.bin","b.bin","c.bin"):
    (d/n).write_bytes(b"X"*500)
# make b.bin un-openable for write by holding an exclusive handle (Windows)
lock = open(d/"b.bin", "r+b")
try:
    import msvcrt; msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 500)
except Exception as ex: print("  (lock setup:", ex, ")")
res = e.sanitize_directory(d, passes=1)
print("  files in batch: 3 ; results returned:", len(res))
print("  statuses:", [r.status for r in res])
print("  any FAILED entry recorded?", any(r.status != "COMPLETED" for r in res))
print("  audit events logged:", len(e.audit._events))
print("  VERDICT: FAIL - failure swallowed by bare `except: continue`, no per-file failure record"
      if len(res) < 3 and not any(r.status!="COMPLETED" for r in res) else "  (inspect above)")
try: lock.close()
except Exception: pass

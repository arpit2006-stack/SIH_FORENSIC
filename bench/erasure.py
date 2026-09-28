"""Erasure completeness, measured by raw-volume re-read — not by trusting a return code.

Method: write a file containing a unique marker to the target volume, locate that marker
in the RAW volume bytes (proving it is physically on the medium), apply an erasure method,
then re-read those same physical offsets and count surviving occurrences.

completeness = 1 - (marker copies surviving / marker copies before)

A method that returns SUCCESS while the marker is still readable scores 0.0, which is the
entire point. Raw volume reads on `\\.\D:` work without elevation on this host; raw
*writes*, TRIM and Sanitize do not, so hardware-level methods are out of scope here and
are reported BLOCKED rather than simulated.
"""
from __future__ import annotations

import os
import pathlib
import secrets
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

VOLUME = r"\\.\D:"
TARGET_DIR = pathlib.Path("D:/_fw_erasure_test")
EXPECTED_SERIAL = "C2ED9DAB"          # operator-approved target, re-checked before writing
CHUNK = 8 << 20


def assert_target() -> None:
    """Refuse to run unless the mounted volume is the operator-approved drive."""
    import subprocess
    out = subprocess.run(
        ["powershell", "-NonInteractive", "-Command",
         "(Get-Partition -DriveLetter D | Get-Disk).SerialNumber"],
        capture_output=True, text=True).stdout.strip()
    if out != EXPECTED_SERIAL:
        raise SystemExit(f"ABORT: D: is on disk serial {out!r}, expected {EXPECTED_SERIAL!r}")


def scan_volume(marker: bytes, limit_bytes: int | None = None) -> list[int]:
    """Absolute byte offsets of every occurrence of `marker` in the raw volume."""
    hits, base = [], 0
    with open(VOLUME, "rb") as f:
        prev = b""
        while True:
            if limit_bytes is not None and base >= limit_bytes:
                break
            buf = f.read(CHUNK)
            if not buf:
                break
            hay = prev + buf
            start = 0
            while True:
                i = hay.find(marker, start)
                if i < 0:
                    break
                hits.append(base - len(prev) + i)
                start = i + 1
            prev = hay[-(len(marker) - 1):] if len(marker) > 1 else b""
            base += len(buf)
    return hits


def read_at(offsets: list[int], n: int) -> list[bytes]:
    """Re-read exactly the offsets where the marker was found."""
    out = []
    with open(VOLUME, "rb") as f:
        for off in offsets:
            f.seek(off)
            out.append(f.read(n))
    return out


def make_target(size_kb: int = 256) -> tuple[pathlib.Path, bytes]:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    marker = b"FWMARK-" + secrets.token_hex(24).encode()
    body = (marker + b" CONFIDENTIAL CASE 2026-904 SUSPECT LEDGER ").ljust(1024, b".")
    data = body * (size_kb * 1024 // len(body) + 1)
    p = TARGET_DIR / f"evidence_{secrets.token_hex(4)}.bin"
    with open(p, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    return p, marker


# --------------------------------------------------------------------------- #
# erasure methods under test
# --------------------------------------------------------------------------- #
def method_plain_delete(p: pathlib.Path) -> str:
    """No security at all — what `del` does. Control case."""
    p.unlink()
    return "os.unlink only"


def method_naive_overwrite(p: pathlib.Path) -> str:
    """MARKET BASELINE: single-pass zero overwrite in place, then delete.
    This is what standard OS-level 'secure delete' utilities do."""
    n = p.stat().st_size
    with open(p, "r+b") as f:
        f.write(b"\x00" * n)
        f.flush()
        os.fsync(f.fileno())
    p.unlink()
    return "1-pass zero overwrite + unlink"


def method_forensiwipe(p: pathlib.Path) -> str:
    from sanitization.file_eraser import SecureFileEraser
    SecureFileEraser().sanitize_file(p, passes=3, wipe_slack=True, delete_after=True)
    return "SecureFileEraser passes=3 wipe_slack=True"


METHODS = {
    "plain-delete (control)": method_plain_delete,
    "naive 1-pass overwrite (market baseline)": method_naive_overwrite,
    "forensiwipe SecureFileEraser": method_forensiwipe,
}


def run() -> None:
    assert_target()
    print(f"target volume {VOLUME} on disk serial {EXPECTED_SERIAL} (operator-approved)\n")
    print(f"{'method':<44}{'before':>8}{'after':>8}{'complete':>10}  notes")
    print("-" * 92)
    results = {}
    for name, fn in METHODS.items():
        p, marker = make_target()
        before = scan_volume(marker)
        if not before:
            print(f"{name:<44}{'0':>8}{'-':>8}{'SKIP':>10}  marker never reached the medium")
            p.unlink(missing_ok=True)
            continue
        note = fn(p)
        time.sleep(0.3)
        survived = sum(1 for b in read_at(before, len(marker)) if b == marker)
        completeness = 1.0 - survived / len(before)
        results[name] = completeness
        print(f"{name:<44}{len(before):>8}{survived:>8}{completeness:>10.3f}  {note}")

    # filename residue: a directory entry naming the evidence file is itself disclosure
    print()
    p, marker = make_target()
    fname = p.name.encode()
    before_n = len(scan_volume(fname))
    method_forensiwipe(p)
    time.sleep(0.3)
    after_n = len(scan_volume(fname))
    print(f"filename residue in directory entries: before={before_n} after={after_n} "
          f"-> {'CLEARED' if after_n == 0 else 'RESIDUE REMAINS'}")

    try:
        TARGET_DIR.rmdir()
    except OSError:
        pass
    return results


if __name__ == "__main__":
    run()

"""Tests for Secure File and Folder Eraser (PS Req 2)."""

import tempfile
from pathlib import Path
from sanitization.file_eraser import SecureFileEraser


def test_secure_file_eraser_single_file():
    eraser = SecureFileEraser()
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "evidence_secret.txt"
        test_file.write_bytes(b"CONFIDENTIAL FORENSIC TARGET EVIDENCE DATA" * 50)
        original_size = test_file.stat().st_size

        result = eraser.sanitize_file(
            file_path=test_file,
            passes=2,
            operator_id="OP-TEST-44",
            case_id="CAS-2026-001",
            wipe_slack=True,
            delete_after=False,  # Keep so we can inspect contents
        )

        assert result.status == "COMPLETED"
        assert result.bytes_scrubbed == original_size
        assert result.passes_completed == 2
        assert len(result.audit_hash) == 64
        # Since the file was overwritten with 2 passes, it shouldn't have original data
        wiped_data = test_file.read_bytes()
        assert b"CONFIDENTIAL" not in wiped_data


def test_secure_file_eraser_directory_with_deletion():
    eraser = SecureFileEraser()
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir) / "subfolder"
        folder.mkdir()
        (folder / "file1.bin").write_bytes(b"A" * 1024)
        (folder / "file2.bin").write_bytes(b"B" * 2048)

        results = eraser.sanitize_directory(
            dir_path=folder,
            passes=1,
            delete_after=True,
        )

        assert len(results) == 2
        # After deletion, files and folder should not exist
        assert not folder.exists()

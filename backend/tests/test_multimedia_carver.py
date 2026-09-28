"""Tests for expanded multi-media forensic carving (MP4, WAV, PNG, JPEG, PDF) and MIME filtering."""

import io
import unittest
from unittest import TestCase
import numpy as np
from PIL import Image

from engine.pretrain_utils import BLOCK_SIZE
from engine.signature_carver import (
    SIGNATURES,
    detect_header,
    detect_header_offset,
    find_footer,
    carve,
)
from engine.api import verify_carved_file, normalize_target_mimes


class TestMultiMediaCarver(TestCase):
    def setUp(self):
        self.rng = np.random.default_rng(123)

    def test_signatures_exist(self):
        expected_types = [
            "image/jpeg",
            "image/png",
            "application/pdf",
            "application/zip",
            "video/mp4",
            "video/x-msvideo",
            "video/x-matroska",
            "audio/wav",
            "audio/mpeg",
        ]
        for t in expected_types:
            self.assertIn(t, SIGNATURES)

    def test_normalize_target_mimes(self):
        mimes = normalize_target_mimes(["video", "audio"])
        self.assertIn("video/mp4", mimes)
        self.assertIn("video/x-msvideo", mimes)
        self.assertIn("audio/wav", mimes)
        self.assertIn("audio/mpeg", mimes)
        self.assertNotIn("image/jpeg", mimes)

        image_mimes = normalize_target_mimes(["images"])
        self.assertIn("image/jpeg", image_mimes)
        self.assertIn("image/png", image_mimes)
        self.assertNotIn("application/pdf", image_mimes)

    def test_png_header_and_verification(self):
        img = Image.new("RGB", (32, 32), color=(255, 0, 0))
        buf = io.BytesIO()
        img.save(buf, "PNG")
        png_bytes = buf.getvalue()

        # Detection
        self.assertEqual(detect_header(png_bytes[:BLOCK_SIZE]), "image/png")
        self.assertGreater(find_footer(png_bytes, "image/png"), 0)

        # Verification
        ok, msg = verify_carved_file(png_bytes, "image/png")
        self.assertTrue(ok, msg)

    def test_wav_header_and_verification(self):
        # 1000 bytes sample wav
        data_len = 500
        total_len = 36 + data_len
        raw = (
            b"RIFF"
            + total_len.to_bytes(4, "little")
            + b"WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x40\x1f\x00\x00\x80\x3e\x00\x00\x02\x00\x10\x00"
            + b"data"
            + data_len.to_bytes(4, "little")
            + b"\x00" * data_len
        )
        self.assertEqual(detect_header(raw[:BLOCK_SIZE]), "audio/wav")
        ok, msg = verify_carved_file(raw, "audio/wav")
        self.assertTrue(ok, msg)

    def test_mp4_header_and_verification(self):
        raw = (
            (32).to_bytes(4, "big")
            + b"ftypisom"
            + (512).to_bytes(4, "big")
            + b"isommp41mp42MSNV"
            + (100).to_bytes(4, "big")
            + b"mdat"
            + b"\x00" * 92
        )
        self.assertEqual(detect_header(raw[:BLOCK_SIZE]), "video/mp4")
        ok, msg = verify_carved_file(raw, "video/mp4")
        self.assertTrue(ok, msg)

    def test_strict_mime_filtering_carve(self):
        # Create a synthetic image with 1 JPEG and 1 PNG
        img_jpg = Image.new("RGB", (32, 32), color=(0, 255, 0))
        buf_jpg = io.BytesIO()
        img_jpg.save(buf_jpg, "JPEG")
        jpg_bytes = buf_jpg.getvalue()

        img_png = Image.new("RGB", (32, 32), color=(0, 0, 255))
        buf_png = io.BytesIO()
        img_png.save(buf_png, "PNG")
        png_bytes = buf_png.getvalue()

        image = np.zeros((10, BLOCK_SIZE), dtype=np.uint8)
        # Block 1: JPEG
        image[1, : len(jpg_bytes)] = np.frombuffer(jpg_bytes, dtype=np.uint8)
        # Block 5: PNG
        image[5, : len(png_bytes)] = np.frombuffer(png_bytes, dtype=np.uint8)

        # 1. Carve with ONLY image/jpeg target filter
        res_jpeg_only = carve(image, target_mimes=["image/jpeg"])
        mimes_found = [s.mime for s in res_jpeg_only.streams]
        self.assertIn("image/jpeg", mimes_found)
        self.assertNotIn("image/png", mimes_found)
        self.assertNotIn(5, res_jpeg_only.header_blocks)

        # 2. Carve with ONLY image/png target filter
        res_png_only = carve(image, target_mimes=["image/png"])
        mimes_png = [s.mime for s in res_png_only.streams]
        self.assertIn("image/png", mimes_png)
        self.assertNotIn("image/jpeg", mimes_png)
        self.assertNotIn(1, res_png_only.header_blocks)

    def test_carving_api_router_job_execution(self):
        from engine.api import CarvingApiRouter
        router = CarvingApiRouter()
        # Test synthetic DEMO job with video and audio filters
        job = router.start_job("DEMO", target_mimes=["video", "audio"], deep_ml=False)
        self.assertEqual(job.status, "COMPLETED")
        self.assertEqual(job.progress_percent, 100)
        # Verify no images were recovered since only video & audio were targeted
        for f in job.files_recovered:
            self.assertIn(f.mime, ["video/mp4", "video/x-msvideo", "video/x-matroska", "audio/wav", "audio/mpeg"])
            self.assertNotIn(f.mime, ["image/jpeg", "image/png", "application/pdf"])


if __name__ == "__main__":
    unittest.main()

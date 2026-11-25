"""Автоматичні тести для лабораторної роботи №4 (аудіостеганографія LSB та LSB + PRNG)."""

import tempfile
import unittest
from pathlib import Path

from audio_stego import (
    compare_audio,
    embed_lsb,
    embed_lsb_prng,
    extract_lsb,
    extract_lsb_prng,
    generate_sample_wav,
)


class TestAudioSteganography(unittest.TestCase):
    def test_sequential_lsb_mono_and_stereo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            for ch in (1, 2):
                cover = str(tmp_dir / f"cover_{ch}.wav")
                stego = str(tmp_dir / f"stego_{ch}.wav")
                generate_sample_wav(cover, duration_sec=1.0, sample_rate=8000, channels=ch)

                for msg in (
                    "Least Significant Bit Coding in WAV audio.",
                    "Бондар Владислав — перевірка кирилиці UTF-8!",
                ):
                    embed_res = embed_lsb(cover, stego, msg)
                    ext_res = extract_lsb(stego)
                    self.assertEqual(ext_res.message, msg)
                    self.assertEqual(embed_res.bits_used, ext_res.bits_used)

    def test_lsb_prng_with_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            cover = str(tmp_dir / "cover.wav")
            stego = str(tmp_dir / "stego_prng.wav")
            generate_sample_wav(cover, duration_sec=1.0, sample_rate=16000, channels=1)

            secret = "Секретне повідомлення Бондар В.В. (PRNG)"
            key = "my_secret_key_2026"
            embed_lsb_prng(cover, stego, secret, key)

            ext = extract_lsb_prng(stego, key)
            self.assertEqual(ext.message, secret)

            with self.assertRaises(ValueError):
                extract_lsb_prng(stego, "wrong_key")

    def test_capacity_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            cover = str(tmp_dir / "tiny.wav")
            stego = str(tmp_dir / "tiny_out.wav")
            generate_sample_wav(cover, duration_sec=0.01, sample_rate=8000, channels=1)  # 80 семплів

            with self.assertRaises(ValueError):
                embed_lsb(cover, stego, "Message longer than 10 bytes!")
            with self.assertRaises(ValueError):
                embed_lsb_prng(cover, stego, "Message longer than 10 bytes!", "key")

    def test_audio_comparison_and_plot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            cover = str(tmp_dir / "cover.wav")
            stego = str(tmp_dir / "stego.wav")
            png = str(tmp_dir / "waveforms.png")
            generate_sample_wav(cover, duration_sec=1.0, sample_rate=16000, channels=1)
            embed_lsb(cover, stego, "Test waveform comparison")

            comp = compare_audio(cover, stego, output_png=png)
            self.assertEqual(comp.total_samples, 16000)
            self.assertLessEqual(comp.max_abs_diff, 1)
            self.assertGreater(comp.psnr_db, 90.0)
            self.assertTrue(Path(png).exists())
            self.assertGreater(Path(png).stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main(verbosity=2)

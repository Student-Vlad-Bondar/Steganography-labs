"""Автоматичні тести для лабораторної роботи №3 (текстова стеганографія)."""

import tempfile
import unittest
from pathlib import Path

from file_io import load_stego_file, save_stego_file
from main import METHODS, perform_extract, perform_hide
from robustness import format_robustness_report, run_robustness_suite
from stego_methods import (
    caesar_decrypt,
    caesar_encrypt,
    case_extract,
    case_hide,
    color_extract,
    color_hide,
    whitespace_extract,
    whitespace_hide,
    zwc_extract,
    zwc_hide,
)

LONG_EN_COVER = (
    "The bright sun shone down on the quiet city, warming the old streets "
    "and filling the morning air with a soft golden glow for everyone. "
    "People walked slowly through the green park, enjoying the calm weather "
    "and talking about their plans for the upcoming weekend with friends "
    "while birds were singing in the tall trees near the river bank."
)

LONG_UA_COVER = (
    "Яскраве весняне сонце лагідно світило над тихим містом, зігріваючи "
    "старі вулиці та наповнюючи ранкове повітря легким золотистим сяйвом. "
    "Люди неспішно прогулювалися зеленим парком, насолоджуючись спокійною "
    "погодою та обговорюючи свої плани на найближчі вихідні разом із друзями."
)


class TestTextSteganography(unittest.TestCase):
    def test_zwc_en_and_ua(self) -> None:
        for secret in ("hi", "Бондар Владислав"):
            res = zwc_hide(LONG_EN_COVER, secret)
            ext = zwc_extract(res.stego_text)
            self.assertEqual(ext.extracted_message, secret)

    def test_case_modification(self) -> None:
        res = case_hide(LONG_EN_COVER, "SOS")
        ext = case_extract(res.stego_text)
        self.assertEqual(ext.extracted_message, "SOS")

        # Український носій + кириличне ім'я
        long_ua = LONG_UA_COVER + " " + LONG_UA_COVER
        res_ua = case_hide(long_ua, "Бондар В.В.")
        ext_ua = case_extract(res_ua.stego_text)
        self.assertEqual(ext_ua.extracted_message, "Бондар В.В.")

    def test_whitespacing(self) -> None:
        big_cover = " ".join(["word"] * 300)
        for secret in ("OK", "Бондар Владислав"):
            res = whitespace_hide(big_cover, secret)
            ext = whitespace_extract(res.stego_text)
            self.assertEqual(ext.extracted_message, secret)

    def test_font_color(self) -> None:
        long_cover = LONG_EN_COVER + " " + LONG_EN_COVER
        for secret in ("yes", "Бондар Владислав"):
            res = color_hide(long_cover, secret)
            ext = color_extract(res.color_tokens)
            self.assertEqual(ext.extracted_message, secret)

    def test_capacity_errors(self) -> None:
        short_cover = "Hi there"
        with self.assertRaises(ValueError):
            case_hide(short_cover, "Too long secret message")
        with self.assertRaises(ValueError):
            whitespace_hide(short_cover, "Too long")
        with self.assertRaises(ValueError):
            color_hide(short_cover, "Too long secret message")

    def test_caesar_cipher(self) -> None:
        for msg in ("Secret123!", "Бондар Владислав"):
            enc = caesar_encrypt(msg, 5)
            self.assertNotEqual(enc, msg)
            self.assertEqual(caesar_decrypt(enc, 5), msg)

        big_cover = " ".join(["The quick brown fox jumps over the lazy dog"] * 25)
        for method in METHODS:
            res = perform_hide(method, big_cover, "Бондар В.В.", use_caesar=True, caesar_shift=4)
            ext = perform_extract(
                method,
                res.stego_text,
                color_tokens=res.color_tokens or None,
                use_caesar=True,
                caesar_shift=4,
            )
            self.assertEqual(ext.extracted_message, "Бондар В.В.")

    def test_file_roundtrips(self) -> None:
        big_cover = " ".join(["The quick brown fox jumps over the lazy dog"] * 25)
        secret = "Бондар В.В."

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            # ZWC, Case, Whitespacing -> .txt, .html, .docx
            for method in METHODS[:3]:
                res = perform_hide(method, big_cover, secret)
                for ext_name in (".txt", ".html", ".docx"):
                    path = str(tmp_dir / f"test_{METHODS.index(method)}{ext_name}")
                    save_stego_file(res, path)
                    loaded_text, loaded_tokens = load_stego_file(path)
                    ext = perform_extract(method, loaded_text, loaded_tokens)
                    self.assertEqual(ext.extracted_message, secret, f"{method} failed for {ext_name}")

            # Font Color -> .html, .docx
            res_color = perform_hide(METHODS[3], big_cover, secret)
            for ext_name in (".html", ".docx"):
                path = str(tmp_dir / f"test_color{ext_name}")
                save_stego_file(res_color, path)
                loaded_text, loaded_tokens = load_stego_file(path)
                ext = perform_extract(METHODS[3], loaded_text, loaded_tokens)
                self.assertEqual(ext.extracted_message, secret, f"Color failed for {ext_name}")

    def test_robustness_suite(self) -> None:
        cases = run_robustness_suite()
        self.assertGreaterEqual(len(cases), 12)
        report = format_robustness_report(cases)
        self.assertIn("ТАК", report)
        self.assertIn("НІ", report)


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Модуль перевірки стійкості методів текстової стеганографії до змін і форматування."""

from dataclasses import dataclass
from typing import List

from stego_methods import (
    COLOR_ZERO,
    NBSP,
    SPACE,
    ZWNJ,
    ZWSP,
    case_extract,
    case_hide,
    color_extract,
    color_hide,
    whitespace_extract,
    whitespace_hide,
    zwc_extract,
    zwc_hide,
)


@dataclass
class RobustnessCase:
    method: str
    modification: str
    survived: bool
    extracted: str


def run_robustness_suite(
    cover_text: str = (
        "The bright sun shone down on the city, warming the quiet streets "
        "and filling the morning air with a soft golden glow for everyone in town."
    ),
    secret: str = "OK",
) -> List[RobustnessCase]:
    """Запускає перевірку стійкості всіх 4 методів до типових змін тексту та форматування."""
    results: List[RobustnessCase] = []

    # 1. ZWC
    zwc_res = zwc_hide(cover_text, secret)
    zwc_variants = [
        ("Додавання тексту в кінець", zwc_res.stego_text + " Extra text."),
        ("Зміна регістру (.lower())", zwc_res.stego_text.lower()),
        ("Нормалізація пробілів", zwc_res.stego_text.replace(NBSP, SPACE)),
        ("Видалення невидимих символів", zwc_res.stego_text.replace(ZWSP, "").replace(ZWNJ, "")),
    ]
    for mod_name, modified in zwc_variants:
        ext = zwc_extract(modified).extracted_message
        results.append(RobustnessCase("ZWC", mod_name, ext == secret, ext))

    # 2. Case Modification
    case_res = case_hide(cover_text, secret)
    case_variants = [
        ("Додавання тексту в кінець", case_res.stego_text + " Extra text."),
        ("Редагування перших літер", "X" + case_res.stego_text[1:]),
        ("Зміна регістру (.lower())", case_res.stego_text.lower()),
        ("Нормалізація пробілів", case_res.stego_text.replace(NBSP, SPACE)),
    ]
    for mod_name, modified in case_variants:
        ext = case_extract(modified).extracted_message
        results.append(RobustnessCase("Зміна регістру", mod_name, ext == secret, ext))

    # 3. Whitespacing
    ws_res = whitespace_hide(cover_text, secret)
    ws_variants = [
        ("Додавання тексту в кінець", ws_res.stego_text + " Extra text."),
        ("Зміна регістру (.lower())", ws_res.stego_text.lower()),
        ("Нормалізація пробілів (NBSP -> SPC)", ws_res.stego_text.replace(NBSP, SPACE)),
        ("Видалення першого слова", ws_res.stego_text.split(" ", 1)[-1]),
    ]
    for mod_name, modified in ws_variants:
        ext = whitespace_extract(modified).extracted_message
        results.append(RobustnessCase("Маніпуляція пробілами", mod_name, ext == secret, ext))

    # 4. Font Color Modification
    col_res = color_hide(cover_text, secret)
    col_tokens = col_res.color_tokens
    col_variants = [
        ("Додавання тексту в кінець", col_tokens + [(c, COLOR_ZERO) for c in " Extra"]),
        ("Зміна регістру (.lower())", [(ch.lower(), c) for ch, c in col_tokens]),
        ("Втрата форматування (plain text)", [(ch, COLOR_ZERO) for ch, _ in col_tokens]),
        ("Видалення першого символу", col_tokens[1:]),
    ]
    for mod_name, mod_tokens in col_variants:
        ext = color_extract(mod_tokens).extracted_message
        results.append(RobustnessCase("Зміна кольору шрифту", mod_name, ext == secret, ext))

    return results


def format_robustness_report(cases: List[RobustnessCase]) -> str:
    """Форматує результати перевірки стійкості у вигляді читабельної таблиці."""
    lines = [
        f"{'Метод':<24} | {'Зміна / Атака':<36} | {'Стійкий':<8} | Вилучено",
        "-" * 90,
    ]
    for c in cases:
        status = "ТАК" if c.survived else "НІ"
        if not c.extracted:
            preview = "<порожньо>"
        elif "\ufffd" in c.extracted:
            preview = "<пошкоджено (зсув/спотворення бітів)>"
        else:
            preview = repr(c.extracted)
        lines.append(f"{c.method:<24} | {c.modification:<36} | {status:<8} | {preview}")
    return "\n".join(lines)

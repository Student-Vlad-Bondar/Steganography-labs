"""Модуль реалізації методів текстової стеганографії та допоміжних функцій."""

from dataclasses import dataclass, field
from typing import List, Tuple

ZWSP = "\u200B"  # біт 1
ZWNJ = "\u200C"  # біт 0
NBSP = "\u00A0"  # біт 1
SPACE = "\u0020"  # біт 0

COLOR_ONE = "#0A0A0A"   # RGB(10, 10, 10) -> біт 1
COLOR_ZERO = "#000000"  # RGB(0, 0, 0)    -> біт 0

UA_LOWER = "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя"
UA_UPPER = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ"
EN_LOWER = "abcdefghijklmnopqrstuvwxyz"
EN_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


@dataclass
class StegoResult:
    """Результат операції приховування або вилучення."""
    method: str
    operation: str
    original_message: str = ""
    processed_message: str = ""
    binary_display: str = ""
    cover_text: str = ""
    annotated_text: str = ""
    stego_text: str = ""
    extracted_message: str = ""
    bits_used: int = 0
    bits_capacity: int = 0
    color_tokens: List[Tuple[str, str]] = field(default_factory=list)


def caesar_encrypt(text: str, shift: int) -> str:
    """Шифрує текст шифром Цезаря (підтримка українського та англійського алфавітів)."""
    result = []
    for ch in text:
        if ch in UA_LOWER:
            idx = (UA_LOWER.index(ch) + shift) % len(UA_LOWER)
            result.append(UA_LOWER[idx])
        elif ch in UA_UPPER:
            idx = (UA_UPPER.index(ch) + shift) % len(UA_UPPER)
            result.append(UA_UPPER[idx])
        elif ch in EN_LOWER:
            idx = (EN_LOWER.index(ch) + shift) % len(EN_LOWER)
            result.append(EN_LOWER[idx])
        elif ch in EN_UPPER:
            idx = (EN_UPPER.index(ch) + shift) % len(EN_UPPER)
            result.append(EN_UPPER[idx])
        else:
            result.append(ch)
    return "".join(result)


def caesar_decrypt(text: str, shift: int) -> str:
    """Дешифрує текст, зашифрований шифром Цезаря."""
    return caesar_encrypt(text, -shift)


def text_to_bits(text: str, add_terminator: bool = True) -> str:
    """Перетворює текст (UTF-8) у рядок бітів. За потреби додає нульовий байт-термінатор."""
    data = text.encode("utf-8")
    if add_terminator:
        data += b"\x00"
    return "".join(format(byte, "08b") for byte in data)


def format_binary_display(text: str) -> str:
    """Повертає бінарне представлення тексту без термінатора (з пробілами між байтами)."""
    return " ".join(format(byte, "08b") for byte in text.encode("utf-8"))


def bits_to_text(bits: str, stop_at_null: bool = True) -> str:
    """Перетворює рядок бітів (кратний 8) назад у текст UTF-8."""
    raw_bytes = bytearray()
    for i in range(0, len(bits) - len(bits) % 8, 8):
        byte_val = int(bits[i:i + 8], 2)
        if stop_at_null and byte_val == 0:
            break
        raw_bytes.append(byte_val)
    return raw_bytes.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# 1. Метод символів нульової ширини (ZWC)
# ---------------------------------------------------------------------------

def zwc_hide(cover_text: str, message: str, position: str = "start") -> StegoResult:
    """Приховує повідомлення за допомогою символів нульової ширини (ZWSP / ZWNJ)."""
    if not message:
        raise ValueError("Секретне повідомлення не може бути порожнім.")

    bits = text_to_bits(message, add_terminator=False)
    zwc_payload = "".join(ZWSP if b == "1" else ZWNJ for b in bits)
    annotated_payload = "".join("[ZWSP]" if b == "1" else "[ZWNJ]" for b in bits)

    if position == "start":
        stego_text = zwc_payload + cover_text
        annotated_text = annotated_payload + cover_text
    else:
        stego_text = cover_text + zwc_payload
        annotated_text = cover_text + annotated_payload

    return StegoResult(
        method="Символи нульової ширини (ZWC)",
        operation="Приховування",
        original_message=message,
        processed_message=message,
        binary_display=format_binary_display(message),
        cover_text=cover_text,
        annotated_text=annotated_text,
        stego_text=stego_text,
        bits_used=len(bits),
        bits_capacity=len(bits),
    )


def zwc_extract(stego_text: str) -> StegoResult:
    """Вилучає повідомлення із тексту зі символами нульової ширини."""
    bits = []
    annotated = []
    for ch in stego_text:
        if ch == ZWSP:
            bits.append("1")
            annotated.append("[ZWSP]")
        elif ch == ZWNJ:
            bits.append("0")
            annotated.append("[ZWNJ]")
        else:
            annotated.append(ch)

    bit_str = "".join(bits)
    extracted = bits_to_text(bit_str, stop_at_null=False) if bit_str else ""

    return StegoResult(
        method="Символи нульової ширини (ZWC)",
        operation="Вилучення",
        binary_display=" ".join(bit_str[i:i + 8] for i in range(0, len(bit_str), 8)),
        annotated_text="".join(annotated),
        stego_text=stego_text,
        extracted_message=extracted,
        bits_used=len(bit_str),
    )


# ---------------------------------------------------------------------------
# 2. Метод зміни регістру літер (Case Modification)
# ---------------------------------------------------------------------------

def _is_case_changeable(ch: str) -> bool:
    """Перевіряє, чи має символ різні великий і малий регістри."""
    return ch.isalpha() and ch.upper() != ch.lower()


def case_hide(cover_text: str, message: str) -> StegoResult:
    """Приховує повідомлення за допомогою зміни регістру літер (1 -> велика, 0 -> мала)."""
    if not message:
        raise ValueError("Секретне повідомлення не може бути порожнім.")

    bits = text_to_bits(message, add_terminator=True)
    capacity = sum(1 for ch in cover_text if _is_case_changeable(ch))

    if len(bits) > capacity:
        raise ValueError(
            f"Недостатньо літер у тексті-носії! Доступно: {capacity} біт, "
            f"потрібно: {len(bits)} біт (з урахуванням стоп-байта)."
        )

    stego_chars = []
    bit_idx = 0
    for ch in cover_text:
        if _is_case_changeable(ch) and bit_idx < len(bits):
            stego_chars.append(ch.upper() if bits[bit_idx] == "1" else ch.lower())
            bit_idx += 1
        else:
            stego_chars.append(ch)

    stego_text = "".join(stego_chars)
    return StegoResult(
        method="Зміна регістру літер",
        operation="Приховування",
        original_message=message,
        processed_message=message,
        binary_display=format_binary_display(message),
        cover_text=cover_text,
        annotated_text=stego_text,
        stego_text=stego_text,
        bits_used=len(bits),
        bits_capacity=capacity,
    )


def case_extract(stego_text: str) -> StegoResult:
    """Вилучає повідомлення, закодоване зміною регістру літер."""
    bits = []
    for ch in stego_text:
        if _is_case_changeable(ch):
            bits.append("1" if ch.isupper() else "0")

    bit_str = "".join(bits)
    extracted = bits_to_text(bit_str, stop_at_null=True)
    used_bits = (len(extracted.encode("utf-8")) + 1) * 8 if extracted else 0

    return StegoResult(
        method="Зміна регістру літер",
        operation="Вилучення",
        binary_display=" ".join(bit_str[i:i + 8] for i in range(0, min(used_bits, len(bit_str)), 8)),
        annotated_text=stego_text,
        stego_text=stego_text,
        extracted_message=extracted,
        bits_used=used_bits,
        bits_capacity=len(bit_str),
    )


# ---------------------------------------------------------------------------
# 3. Метод маніпуляції пробілами (Whitespacing)
# ---------------------------------------------------------------------------

def whitespace_hide(cover_text: str, message: str) -> StegoResult:
    """Приховує повідомлення заміною пробілів (1 -> U+00A0 нерозривний пробіл, 0 -> U+0020 звичайний)."""
    if not message:
        raise ValueError("Секретне повідомлення не може бути порожнім.")

    bits = text_to_bits(message, add_terminator=True)
    space_positions = [i for i, ch in enumerate(cover_text) if ch in (SPACE, NBSP)]
    capacity = len(space_positions)

    if len(bits) > capacity:
        raise ValueError(
            f"Недостатньо пробілів у тексті-носії! Доступно: {capacity} біт, "
            f"потрібно: {len(bits)} біт (з урахуванням стоп-байта)."
        )

    stego_chars = list(cover_text)
    annotated_chars = list(cover_text)

    for bit_idx, pos in enumerate(space_positions):
        if bit_idx < len(bits):
            if bits[bit_idx] == "1":
                stego_chars[pos] = NBSP
                annotated_chars[pos] = "[NBSP]"
            else:
                stego_chars[pos] = SPACE
                annotated_chars[pos] = "[SPC]"

    return StegoResult(
        method="Маніпуляція пробілами",
        operation="Приховування",
        original_message=message,
        processed_message=message,
        binary_display=format_binary_display(message),
        cover_text=cover_text,
        annotated_text="".join(annotated_chars),
        stego_text="".join(stego_chars),
        bits_used=len(bits),
        bits_capacity=capacity,
    )


def whitespace_extract(stego_text: str) -> StegoResult:
    """Вилучає повідомлення, закодоване нерозривними та звичайними пробілами."""
    bits = []
    annotated = []
    for ch in stego_text:
        if ch == NBSP:
            bits.append("1")
            annotated.append("[NBSP]")
        elif ch == SPACE:
            bits.append("0")
            annotated.append("[SPC]")
        else:
            annotated.append(ch)

    bit_str = "".join(bits)
    extracted = bits_to_text(bit_str, stop_at_null=True)
    used_bits = (len(extracted.encode("utf-8")) + 1) * 8 if extracted else 0

    return StegoResult(
        method="Маніпуляція пробілами",
        operation="Вилучення",
        binary_display=" ".join(bit_str[i:i + 8] for i in range(0, min(used_bits, len(bit_str)), 8)),
        annotated_text="".join(annotated),
        stego_text=stego_text,
        extracted_message=extracted,
        bits_used=used_bits,
        bits_capacity=len(bit_str),
    )


# ---------------------------------------------------------------------------
# 4. Метод зміни кольору шрифту (Font Color Modification)
# ---------------------------------------------------------------------------

def color_hide(cover_text: str, message: str) -> StegoResult:
    """Приховує повідомлення зміною кольору символів (1 -> #0A0A0A, 0 -> #000000; пробіли пропускаються)."""
    if not message:
        raise ValueError("Секретне повідомлення не може бути порожнім.")

    bits = text_to_bits(message, add_terminator=True)
    capacity = sum(1 for ch in cover_text if not ch.isspace())

    if len(bits) > capacity:
        raise ValueError(
            f"Недостатньо непробільних символів у тексті-носії! Доступно: {capacity} біт, "
            f"потрібно: {len(bits)} біт (з урахуванням стоп-байта)."
        )

    tokens: List[Tuple[str, str]] = []
    annotated_parts = []
    bit_idx = 0

    for ch in cover_text:
        if not ch.isspace() and bit_idx < len(bits):
            color = COLOR_ONE if bits[bit_idx] == "1" else COLOR_ZERO
            tokens.append((ch, color))
            annotated_parts.append(f"[{ch}:{color}]")
            bit_idx += 1
        else:
            tokens.append((ch, COLOR_ZERO))
            annotated_parts.append(ch)

    return StegoResult(
        method="Зміна кольору шрифту",
        operation="Приховування",
        original_message=message,
        processed_message=message,
        binary_display=format_binary_display(message),
        cover_text=cover_text,
        annotated_text="".join(annotated_parts),
        stego_text=cover_text,
        bits_used=len(bits),
        bits_capacity=capacity,
        color_tokens=tokens,
    )


def color_extract(color_tokens: List[Tuple[str, str]]) -> StegoResult:
    """Вилучає повідомлення зі списку токенів (символ, hex-колір)."""
    bits = []
    annotated_parts = []
    plain_chars = []

    for ch, color in color_tokens:
        plain_chars.append(ch)
        if not ch.isspace():
            norm_color = color.strip().upper()
            if not norm_color.startswith("#"):
                norm_color = "#" + norm_color
            bit = "1" if norm_color == COLOR_ONE else "0"
            bits.append(bit)
            annotated_parts.append(f"[{ch}:{norm_color}]")
        else:
            annotated_parts.append(ch)

    bit_str = "".join(bits)
    extracted = bits_to_text(bit_str, stop_at_null=True)
    used_bits = (len(extracted.encode("utf-8")) + 1) * 8 if extracted else 0

    return StegoResult(
        method="Зміна кольору шрифту",
        operation="Вилучення",
        binary_display=" ".join(bit_str[i:i + 8] for i in range(0, min(used_bits, len(bit_str)), 8)),
        annotated_text="".join(annotated_parts),
        stego_text="".join(plain_chars),
        extracted_message=extracted,
        bits_used=used_bits,
        bits_capacity=len(bit_str),
        color_tokens=color_tokens,
    )

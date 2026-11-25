"""Модуль аудіостеганографії у WAV-файлах методами LSB та LSB + PRNG."""

import hashlib
import math
import random
import wave
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont


@dataclass
class AudioStegoResult:
    """Результат приховування або вилучення у WAV-файлі."""
    method: str
    operation: str
    input_wav: str
    output_wav: str = ""
    message: str = ""
    binary_preview: str = ""
    total_samples: int = 0
    bits_used: int = 0
    sample_rate: int = 0
    channels: int = 0


@dataclass
class AudioComparison:
    """Метрики порівняння оригінального та стего-WAV файлів."""
    total_samples: int
    sample_rate: int
    channels: int
    duration_sec: float
    changed_samples: int
    changed_percent: float
    max_abs_diff: int
    mse: float
    psnr_db: float
    png_path: str = ""


def generate_sample_wav(
    output_path: str,
    duration_sec: float = 5.0,
    sample_rate: int = 44100,
    channels: int = 1,
) -> None:
    """Генерує тестовий 16-бітовий PCM WAV-файл із плавним гармонійним сигналом."""
    n_frames = int(duration_sec * sample_rate)
    t = np.linspace(0.0, duration_sec, num=n_frames, endpoint=False)

    # Приємний акорд із плавним наростанням і затуханням
    signal = (
        0.45 * np.sin(2.0 * np.pi * 261.63 * t)
        + 0.30 * np.sin(2.0 * np.pi * 329.63 * t)
        + 0.25 * np.sin(2.0 * np.pi * 392.00 * t)
    )
    envelope = np.sin(np.pi * np.linspace(0.0, 1.0, n_frames)) ** 0.4
    samples_mono = np.clip(signal * envelope * 22000.0, -32767, 32767).astype(np.int16)

    if channels == 2:
        right = np.roll(samples_mono, 150)
        samples = np.column_stack((samples_mono, right)).reshape(-1)
    elif channels == 1:
        samples = samples_mono
    else:
        raise ValueError("Підтримуються лише 1 (моно) або 2 (стерео) канали.")

    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())


def _read_wav_int16(wav_path: str) -> Tuple[wave._wave_params, np.ndarray]:
    """Зчитує 16-бітовий WAV-файл у масив int16."""
    with wave.open(wav_path, "rb") as wf:
        params = wf.getparams()
        if params.sampwidth != 2:
            raise ValueError(
                f"Підтримується лише 16-бітовий PCM WAV (отримано {params.sampwidth * 8}-біт)."
            )
        frames = wf.readframes(params.nframes)
    samples = np.frombuffer(frames, dtype=np.int16).copy()
    return params, samples


def _write_wav_int16(wav_path: str, params: wave._wave_params, samples: np.ndarray) -> None:
    """Записує масив int16 у WAV-файл зі збереженням параметрів."""
    with wave.open(wav_path, "wb") as wf:
        wf.setparams(params)
        wf.writeframes(samples.astype(np.int16).tobytes())


def _text_to_bits_utf8(message: str, add_null_terminator: bool = True) -> str:
    """Перетворює текст UTF-8 у бінарний рядок."""
    data = message.encode("utf-8")
    if add_null_terminator:
        data += b"\x00"
    return "".join(format(byte, "08b") for byte in data)


def _bits_to_text_utf8(bits: str) -> str:
    """Перетворює бінарний рядок (кратний 8) у текст UTF-8."""
    raw = bytearray(int(bits[i:i + 8], 2) for i in range(0, len(bits) - len(bits) % 8, 8))
    return raw.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Завдання 1: Послідовний метод LSB
# ---------------------------------------------------------------------------

def embed_lsb(input_wav: str, output_wav: str, message: str) -> AudioStegoResult:
    """Вбудовує текстове повідомлення у WAV-файл послідовним методом LSB."""
    if not message:
        raise ValueError("Секретне повідомлення не може бути порожнім.")

    params, samples = _read_wav_int16(input_wav)
    bits = _text_to_bits_utf8(message, add_null_terminator=True)

    if len(bits) > len(samples):
        raise ValueError(
            f"Повідомлення завелике! Доступно: {len(samples)} біт, потрібно: {len(bits)} біт."
        )

    bit_arr = np.fromiter((int(b) for b in bits), dtype=np.int16, count=len(bits))
    samples[:len(bits)] = (samples[:len(bits)] & ~1) | bit_arr
    _write_wav_int16(output_wav, params, samples)

    pure_bits = _text_to_bits_utf8(message, add_null_terminator=False)
    preview = " ".join(pure_bits[i:i + 8] for i in range(0, min(len(pure_bits), 64), 8))
    if len(pure_bits) > 64:
        preview += " ..."

    return AudioStegoResult(
        method="LSB (послідовний)",
        operation="Приховування",
        input_wav=input_wav,
        output_wav=output_wav,
        message=message,
        binary_preview=preview,
        total_samples=len(samples),
        bits_used=len(bits),
        sample_rate=params.framerate,
        channels=params.nchannels,
    )


def extract_lsb(stego_wav: str) -> AudioStegoResult:
    """Вилучає текстове повідомлення з WAV-файлу, закодованого послідовним LSB."""
    params, samples = _read_wav_int16(stego_wav)
    lsbs = samples & 1

    # Читаємо по 8 бітів до першого нульового байта-термінатора
    raw_bytes = bytearray()
    n_bytes = len(lsbs) // 8
    bit_matrix = lsbs[:n_bytes * 8].reshape(n_bytes, 8)
    weights = np.array([128, 64, 32, 16, 8, 4, 2, 1], dtype=np.uint8)
    byte_vals = bit_matrix.dot(weights)

    zero_positions = np.where(byte_vals == 0)[0]
    if len(zero_positions) == 0:
        raise ValueError("Маркер завершення не знайдено або файл не містить прихованого тексту.")

    end_idx = int(zero_positions[0])
    raw_bytes.extend(byte_vals[:end_idx].tolist())
    message = bytes(raw_bytes).decode("utf-8", errors="replace")

    used_bits = (end_idx + 1) * 8
    pure_bits = "".join(format(b, "08b") for b in raw_bytes[:8])
    preview = " ".join(pure_bits[i:i + 8] for i in range(0, len(pure_bits), 8))
    if end_idx > 8:
        preview += " ..."

    return AudioStegoResult(
        method="LSB (послідовний)",
        operation="Вилучення",
        input_wav=stego_wav,
        message=message,
        binary_preview=preview,
        total_samples=len(samples),
        bits_used=used_bits,
        sample_rate=params.framerate,
        channels=params.nchannels,
    )


# ---------------------------------------------------------------------------
# Завдання 2: Метод LSB + PRNG (псевдовипадкові позиції за ключем)
# ---------------------------------------------------------------------------

def _prng_unique_indices(key: str, total_samples: int, count: int, used: Optional[set] = None) -> List[int]:
    """Генерує детерміновану послідовність унікальних індексів семплів на основі хешу ключа."""
    if not key:
        raise ValueError("Секретний ключ для LSB + PRNG не може бути порожнім.")
    if count > total_samples:
        raise ValueError(f"Недостатньо семплів ({total_samples}) для {count} бітів.")

    seed = hashlib.sha256(key.encode("utf-8")).digest()
    rng = random.Random(seed)
    seen = used if used is not None else set()
    indices: List[int] = []

    while len(indices) < count:
        idx = rng.randrange(total_samples)
        if idx not in seen:
            seen.add(idx)
            indices.append(idx)
    return indices


def embed_lsb_prng(input_wav: str, output_wav: str, message: str, key: str) -> AudioStegoResult:
    """Вбудовує повідомлення у WAV-файл методом LSB + PRNG на основі секретного ключа."""
    if not message:
        raise ValueError("Секретне повідомлення не може бути порожнім.")

    params, samples = _read_wav_int16(input_wav)
    msg_bytes = message.encode("utf-8")
    header_bits = format(len(msg_bytes), "032b")
    msg_bits = "".join(format(b, "08b") for b in msg_bytes)
    all_bits = header_bits + msg_bits

    if len(all_bits) > len(samples):
        raise ValueError(
            f"Повідомлення завелике! Доступно: {len(samples)} біт, потрібно: {len(all_bits)} біт."
        )

    indices = _prng_unique_indices(key, len(samples), len(all_bits))
    for bit_ch, sample_idx in zip(all_bits, indices):
        samples[sample_idx] = (samples[sample_idx] & ~1) | int(bit_ch)

    _write_wav_int16(output_wav, params, samples)

    preview = " ".join(msg_bits[i:i + 8] for i in range(0, min(len(msg_bits), 64), 8))
    if len(msg_bits) > 64:
        preview += " ..."

    return AudioStegoResult(
        method="LSB + PRNG (ключ)",
        operation="Приховування",
        input_wav=input_wav,
        output_wav=output_wav,
        message=message,
        binary_preview=preview,
        total_samples=len(samples),
        bits_used=len(all_bits),
        sample_rate=params.framerate,
        channels=params.nchannels,
    )


def extract_lsb_prng(stego_wav: str, key: str) -> AudioStegoResult:
    """Вилучає повідомлення з WAV-файлу методом LSB + PRNG за секретним ключем."""
    if not key:
        raise ValueError("Введіть секретний ключ для вилучення повідомлення методом LSB + PRNG.")

    params, samples = _read_wav_int16(stego_wav)
    if len(samples) < 32:
        raise ValueError("Аудіофайл занадто короткий для зчитування заголовка.")

    seed = hashlib.sha256(key.encode("utf-8")).digest()
    rng = random.Random(seed)
    seen: set = set()

    def next_indices(n: int) -> List[int]:
        res: List[int] = []
        while len(res) < n:
            idx = rng.randrange(len(samples))
            if idx not in seen:
                seen.add(idx)
                res.append(idx)
        return res

    header_indices = next_indices(32)
    header_bits = "".join(str(int(samples[i]) & 1) for i in header_indices)
    byte_len = int(header_bits, 2)

    max_bytes = (len(samples) - 32) // 8
    if byte_len == 0 or byte_len > max_bytes:
        raise ValueError("Невірний ключ або файл не містить валідного повідомлення LSB + PRNG.")

    msg_indices = next_indices(byte_len * 8)
    msg_bits = "".join(str(int(samples[i]) & 1) for i in msg_indices)
    raw = bytes(int(msg_bits[i:i + 8], 2) for i in range(0, len(msg_bits), 8))
    try:
        message = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Не вдалося декодувати UTF-8: можливо, вказано невірний ключ.") from exc

    preview = " ".join(msg_bits[i:i + 8] for i in range(0, min(len(msg_bits), 64), 8))
    if len(msg_bits) > 64:
        preview += " ..."

    return AudioStegoResult(
        method="LSB + PRNG (ключ)",
        operation="Вилучення",
        input_wav=stego_wav,
        message=message,
        binary_preview=preview,
        total_samples=len(samples),
        bits_used=32 + byte_len * 8,
        sample_rate=params.framerate,
        channels=params.nchannels,
    )


# ---------------------------------------------------------------------------
# Порівняння аудіофайлів і побудова графіків хвильових форм
# ---------------------------------------------------------------------------

def compare_audio(
    original_wav: str,
    stego_wav: str,
    output_png: Optional[str] = None,
) -> AudioComparison:
    """Обчислює метрики різниці між оригінальним і стего-WAV та будує графік хвильових форм."""
    p1, s1 = _read_wav_int16(original_wav)
    p2, s2 = _read_wav_int16(stego_wav)

    if len(s1) != len(s2) or p1.framerate != p2.framerate or p1.nchannels != p2.nchannels:
        raise ValueError("Параметри або довжина оригінального та стего-WAV файлів не збігаються.")

    diff = np.abs(s1.astype(np.int32) - s2.astype(np.int32))
    changed = int(np.count_nonzero(diff))
    max_diff = int(np.max(diff)) if len(diff) else 0
    mse = float(np.mean((s1.astype(np.float64) - s2.astype(np.float64)) ** 2))
    psnr = float("inf") if mse == 0.0 else 10.0 * math.log10((32767.0 ** 2) / mse)
    duration = p1.nframes / float(p1.framerate)

    if output_png:
        _render_waveform_png(s1, s2, p1.framerate, p1.nchannels, output_png)

    return AudioComparison(
        total_samples=len(s1),
        sample_rate=p1.framerate,
        channels=p1.nchannels,
        duration_sec=duration,
        changed_samples=changed,
        changed_percent=(changed / len(s1) * 100.0) if len(s1) else 0.0,
        max_abs_diff=max_diff,
        mse=mse,
        psnr_db=psnr,
        png_path=output_png or "",
    )


def _render_waveform_png(
    s1: np.ndarray,
    s2: np.ndarray,
    sample_rate: int,
    channels: int,
    output_png: str,
) -> None:
    """Рендерить PNG-графік порівняння хвильових форм оригіналу та стегофайлу."""
    w, h = 1100, 620
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 14)
        small_font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 12)
    except OSError:
        font = ImageFont.load_default()
        small_font = font

    # Виділяємо перший канал для наочності
    c1 = s1[::channels] if channels > 1 else s1
    c2 = s2[::channels] if channels > 1 else s2
    duration = len(c1) / float(sample_rate)

    panels = [
        ("Оригінал (Original WAV)", c1, 40, 275, "#1f77b4"),
        ("Стегофайл (Stego WAV)", c2, 330, 565, "#2a7abf"),
    ]
    left, right = 85, w - 35
    plot_w = right - left

    # Зменшуємо до min/max по стовпцях для швидкої та точної візуалізації
    bins = np.array_split(np.arange(len(c1)), plot_w)

    for title, data, top, bottom, color in panels:
        mid_y = (top + bottom) // 2
        half_h = (bottom - top) // 2 - 10
        draw.rectangle([left, top, right, bottom], outline="#444444", width=1)
        draw.line([left, mid_y, right, mid_y], fill="#cccccc", width=1)
        draw.text((left + plot_w // 2 - 80, top - 22), title, fill="black", font=font)

        # Підписи осі Y
        for val, y_pos in ((32767, top + 10), (0, mid_y), (-32768, bottom - 10)):
            draw.text((12, y_pos - 7), f"{val:>6}", fill="#333333", font=small_font)
            draw.line([left - 4, y_pos, left, y_pos], fill="#444444", width=1)

        # Підписи осі X (час у секундах)
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            x_pos = int(left + frac * (plot_w - 1))
            draw.line([x_pos, bottom, x_pos, bottom + 4], fill="#444444", width=1)
            draw.text((x_pos - 14, bottom + 7), f"{duration * frac:.2f}s", fill="#333333", font=small_font)

        for x_off, idx_bin in enumerate(bins):
            if len(idx_bin) == 0:
                continue
            seg = data[idx_bin]
            y_max = int(mid_y - (float(np.max(seg)) / 32768.0) * half_h)
            y_min = int(mid_y - (float(np.min(seg)) / 32768.0) * half_h)
            x_cur = left + x_off
            draw.line([x_cur, y_max, x_cur, y_min], fill=color, width=1)

    img.save(output_png)

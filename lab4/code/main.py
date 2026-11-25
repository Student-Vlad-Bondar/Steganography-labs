"""Головний модуль аудіостеганографії (GUI на Tkinter + CLI-меню)."""

import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Optional

import numpy as np

from audio_stego import (
    _read_wav_int16,
    compare_audio,
    embed_lsb,
    embed_lsb_prng,
    extract_lsb,
    extract_lsb_prng,
    generate_sample_wav,
)

METHODS = [
    "LSB (послідовний)",
    "LSB + PRNG (з ключем)",
]

DEFAULT_SECRET = "Бондар Владислав — Лабораторна робота 4 (WAV LSB)"


class AudioStegoApp(tk.Tk):
    """Графічний інтерфейс для приховування, вилучення та порівняння WAV-файлів."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Лабораторна робота №4 — Аудіостеганографія у WAV (LSB та LSB + PRNG)")
        self.geometry("1040x780")
        self.minsize(900, 680)
        self._build_ui()

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        # Панель налаштувань
        ctrl = ttk.LabelFrame(self, text="Параметри операції", padding=10)
        ctrl.pack(fill="x", padx=10, pady=(10, 5))

        ttk.Label(ctrl, text="Метод:").grid(row=0, column=0, sticky="w", padx=4)
        self.method_var = tk.StringVar(value=METHODS[0])
        method_cb = ttk.Combobox(ctrl, textvariable=self.method_var, values=METHODS, state="readonly", width=26)
        method_cb.grid(row=0, column=1, sticky="w", padx=4)
        method_cb.bind("<<ComboboxSelected>>", self._on_method_change)

        ttk.Label(ctrl, text="Режим:").grid(row=0, column=2, sticky="w", padx=(14, 4))
        self.mode_var = tk.StringVar(value="hide")
        ttk.Radiobutton(ctrl, text="Приховування", variable=self.mode_var, value="hide").grid(row=0, column=3, padx=4)
        ttk.Radiobutton(ctrl, text="Вилучення", variable=self.mode_var, value="extract").grid(row=0, column=4, padx=4)

        ttk.Label(ctrl, text="Ключ (для PRNG):").grid(row=0, column=5, sticky="w", padx=(14, 4))
        self.key_var = tk.StringVar(value="secret_key_4")
        self.key_entry = ttk.Entry(ctrl, textvariable=self.key_var, width=20, state="disabled")
        self.key_entry.grid(row=0, column=6, sticky="w", padx=4)

        # Шляхи до файлів
        files_lf = ttk.LabelFrame(self, text="Аудіофайли (.wav)", padding=10)
        files_lf.pack(fill="x", padx=10, pady=5)
        files_lf.columnconfigure(1, weight=1)

        default_dir = Path(__file__).resolve().parent
        self.in_wav_var = tk.StringVar(value=str(default_dir / "cover.wav"))
        self.out_wav_var = tk.StringVar(value=str(default_dir / "stego.wav"))

        ttk.Label(files_lf, text="Вхідний WAV (оригінал або стего):").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        self.in_entry = ttk.Entry(files_lf, textvariable=self.in_wav_var)
        self.in_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=3)
        ttk.Button(files_lf, text="Обрати...", command=self._browse_in_wav).grid(row=0, column=2, padx=4, pady=3)

        ttk.Label(files_lf, text="Вихідний стего-WAV:").grid(row=1, column=0, sticky="w", padx=4, pady=3)
        self.out_entry = ttk.Entry(files_lf, textvariable=self.out_wav_var)
        self.out_entry.grid(row=1, column=1, sticky="ew", padx=4, pady=3)
        ttk.Button(files_lf, text="Обрати...", command=self._browse_out_wav).grid(row=1, column=2, padx=4, pady=3)

        # Кнопки дій
        btns = ttk.Frame(self, padding=(10, 4))
        btns.pack(fill="x")
        ttk.Button(btns, text="▶ Виконати", command=self.on_execute).pack(side="left", padx=4)
        ttk.Button(btns, text="🎵 Створити тестовий WAV", command=self.on_generate_sample).pack(side="left", padx=4)
        ttk.Button(btns, text="📊 Порівняти графіки хвиль", command=self.on_compare).pack(side="left", padx=4)
        ttk.Button(btns, text="💾 Зберегти графік (PNG)...", command=self.on_save_plot).pack(side="left", padx=4)
        ttk.Button(btns, text="🧹 Очистити", command=self.on_clear).pack(side="right", padx=4)

        # Секретне повідомлення
        msg_lf = ttk.LabelFrame(self, text="Секретне повідомлення", padding=6)
        msg_lf.pack(fill="x", padx=10, pady=5)
        self.msg_text = scrolledtext.ScrolledText(msg_lf, height=4, wrap="word", font=("Consolas", 10))
        self.msg_text.pack(fill="both", expand=True)
        self.msg_text.insert("1.0", DEFAULT_SECRET)

        # Вкладки результатів
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        tab_res = ttk.Frame(nb, padding=6)
        self.result_text = scrolledtext.ScrolledText(tab_res, wrap="word", font=("Consolas", 10))
        self.result_text.pack(fill="both", expand=True)
        nb.add(tab_res, text="Результати операції")

        tab_wave = ttk.Frame(nb, padding=6)
        self.wave_canvas = tk.Canvas(tab_wave, bg="white", highlightthickness=1, highlightbackground="#cccccc")
        self.wave_canvas.pack(fill="both", expand=True)
        nb.add(tab_wave, text="Порівняння хвильових форм")

        self.notebook = nb
        self._setup_clipboard_support()

    def _setup_clipboard_support(self) -> None:
        """Підтримка Ctrl+C/V/X/A для української та англійської розкладок + контекстне меню."""
        self.bind_all("<Control-KeyPress>", self._handle_ctrl_keys)
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Вирізати", command=lambda: self._trigger_focused("<<Cut>>"))
        menu.add_command(label="Копіювати", command=lambda: self._trigger_focused("<<Copy>>"))
        menu.add_command(label="Вставити", command=lambda: self._trigger_focused("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Виділити все", command=self._select_all_focused)
        self._ctx_menu = menu

        for w in (self.msg_text, self.result_text, self.key_entry, self.in_entry, self.out_entry):
            w.bind("<Button-3>", self._show_ctx)

    def _show_ctx(self, event: tk.Event) -> None:
        event.widget.focus_set()
        self._ctx_menu.tk_popup(event.x_root, event.y_root)

    def _trigger_focused(self, virt: str) -> None:
        w = self.focus_get()
        if w is not None:
            w.event_generate(virt)

    def _select_all_focused(self) -> None:
        w = self.focus_get()
        if isinstance(w, tk.Text):
            w.tag_add("sel", "1.0", "end-1c")
        elif isinstance(w, (tk.Entry, ttk.Entry)):
            w.select_range(0, "end")

    def _handle_ctrl_keys(self, event: tk.Event) -> Optional[str]:
        w = event.widget
        if not isinstance(w, (tk.Text, tk.Entry, ttk.Entry)):
            return None
        low = event.keysym.lower()
        if event.keycode == 86 and low != "v":
            w.event_generate("<<Paste>>")
            return "break"
        if event.keycode == 67 and low != "c":
            w.event_generate("<<Copy>>")
            return "break"
        if event.keycode == 88 and low != "x":
            w.event_generate("<<Cut>>")
            return "break"
        if event.keycode == 65:
            if isinstance(w, tk.Text):
                w.tag_add("sel", "1.0", "end-1c")
            else:
                w.select_range(0, "end")
            return "break"
        return None

    def _on_method_change(self, _event: object = None) -> None:
        is_prng = self.method_var.get() == METHODS[1]
        self.key_entry.configure(state="normal" if is_prng else "disabled")

    def _browse_in_wav(self) -> None:
        path = filedialog.askopenfilename(title="Оберіть WAV-файл", filetypes=[("WAV audio", "*.wav")])
        if path:
            self.in_wav_var.set(path)

    def _browse_out_wav(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Зберегти стего-WAV", defaultextension=".wav", filetypes=[("WAV audio", "*.wav")]
        )
        if path:
            self.out_wav_var.set(path)

    def on_generate_sample(self) -> None:
        path = self.in_wav_var.get().strip() or str(Path(__file__).resolve().parent / "cover.wav")
        try:
            generate_sample_wav(path, duration_sec=5.0, sample_rate=44100, channels=1)
            self.in_wav_var.set(path)
            messagebox.showinfo("Успіх", f"Тестовий 16-бітовий WAV-файл створено:\n{path}")
        except Exception as exc:
            messagebox.showerror("Помилка", str(exc))

    def on_execute(self) -> None:
        method = self.method_var.get()
        mode = self.mode_var.get()
        in_wav = self.in_wav_var.get().strip()
        out_wav = self.out_wav_var.get().strip()
        key = self.key_var.get()
        message = self.msg_text.get("1.0", "end-1c")

        try:
            if mode == "hide":
                if method == METHODS[0]:
                    res = embed_lsb(in_wav, out_wav, message)
                else:
                    res = embed_lsb_prng(in_wav, out_wav, message, key)
                lines = [
                    f"Метод: {res.method}",
                    f"Операція: {res.operation}",
                    f"Аудіопараметри: {res.sample_rate} Гц, каналів: {res.channels}, усього семплів: {res.total_samples}",
                    f"Використано біт: {res.bits_used} із {res.total_samples} ({res.bits_used / res.total_samples * 100:.4f}%)",
                    f"Вхідний файл: {res.input_wav}",
                    f"Вихідний стегофайл: {res.output_wav}",
                    f"\nПриховане повідомлення:\n{res.message}",
                    f"\nБінарний фрагмент (UTF-8):\n{res.binary_preview}",
                ]
            else:
                target_wav = out_wav if (Path(out_wav).exists() and in_wav != out_wav and messagebox.askyesno(
                    "Вибір файлу", f"Вилучати зі стегофайлу?\n{out_wav}\n(Натисніть «Ні», щоб зчитати з поля «Вхідний WAV»)"
                )) else in_wav
                if method == METHODS[0]:
                    res = extract_lsb(target_wav)
                else:
                    res = extract_lsb_prng(target_wav, key)
                lines = [
                    f"Метод: {res.method}",
                    f"Операція: {res.operation}",
                    f"Файл: {res.input_wav}",
                    f"Аудіопараметри: {res.sample_rate} Гц, каналів: {res.channels}, усього семплів: {res.total_samples}",
                    f"Зчитано біт: {res.bits_used}",
                    f"\nВилучене повідомлення:\n{res.message}",
                    f"\nБінарний фрагмент (UTF-8):\n{res.binary_preview}",
                ]

            self.result_text.delete("1.0", "end")
            self.result_text.insert("1.0", "\n".join(lines))
            self.notebook.select(0)
        except Exception as exc:
            messagebox.showerror("Помилка", str(exc))

    def on_compare(self) -> None:
        orig = self.in_wav_var.get().strip()
        stego = self.out_wav_var.get().strip()
        try:
            comp = compare_audio(orig, stego)
            report = (
                f"=== Порівняння WAV-файлів ===\n"
                f"Оригінал: {orig}\n"
                f"Стегофайл: {stego}\n"
                f"Тривалість: {comp.duration_sec:.2f} с ({comp.sample_rate} Гц, каналів: {comp.channels})\n"
                f"Усього семплів: {comp.total_samples}\n"
                f"Змінено семплів: {comp.changed_samples} ({comp.changed_percent:.4f}%)\n"
                f"Макс. відхилення амплітуди: {comp.max_abs_diff}\n"
                f"MSE: {comp.mse:.6f}\n"
                f"PSNR: {comp.psnr_db:.2f} дБ\n"
            )
            self.result_text.delete("1.0", "end")
            self.result_text.insert("1.0", report)

            self._draw_canvas_waveforms(orig, stego)
            self.notebook.select(1)
        except Exception as exc:
            messagebox.showerror("Помилка порівняння", str(exc))

    def _draw_canvas_waveforms(self, orig: str, stego: str) -> None:
        self.wave_canvas.update_idletasks()
        cw = max(self.wave_canvas.winfo_width(), 800)
        ch = max(self.wave_canvas.winfo_height(), 420)
        self.wave_canvas.delete("all")

        p1, s1 = _read_wav_int16(orig)
        _, s2 = _read_wav_int16(stego)
        c1 = s1[::p1.nchannels] if p1.nchannels > 1 else s1
        c2 = s2[::p1.nchannels] if p1.nchannels > 1 else s2

        left, right = 65, cw - 25
        plot_w = max(right - left, 100)
        bins = np.array_split(np.arange(len(c1)), plot_w)

        panels = [
            ("Оригінал", c1, 30, ch // 2 - 20, "#1f77b4"),
            ("Стего", c2, ch // 2 + 25, ch - 30, "#2a7abf"),
        ]
        for title, data, top, bottom, color in panels:
            mid = (top + bottom) // 2
            half = max((bottom - top) // 2 - 8, 20)
            self.wave_canvas.create_rectangle(left, top, right, bottom, outline="#555555")
            self.wave_canvas.create_line(left, mid, right, mid, fill="#dddddd")
            self.wave_canvas.create_text(left + plot_w // 2, top - 12, text=title, font=("Arial", 10, "bold"))
            self.wave_canvas.create_text(35, top + 8, text="32767", font=("Consolas", 8))
            self.wave_canvas.create_text(35, mid, text="0", font=("Consolas", 8))
            self.wave_canvas.create_text(35, bottom - 8, text="-32768", font=("Consolas", 8))

            for x_off, idx_bin in enumerate(bins):
                if len(idx_bin) == 0:
                    continue
                seg = data[idx_bin]
                y_max = mid - int((float(np.max(seg)) / 32768.0) * half)
                y_min = mid - int((float(np.min(seg)) / 32768.0) * half)
                x = left + x_off
                self.wave_canvas.create_line(x, y_max, x, y_min, fill=color)

    def on_save_plot(self) -> None:
        orig = self.in_wav_var.get().strip()
        stego = self.out_wav_var.get().strip()
        out_png = filedialog.asksaveasfilename(
            title="Зберегти графік хвиль", defaultextension=".png", filetypes=[("PNG image", "*.png")]
        )
        if not out_png:
            return
        try:
            compare_audio(orig, stego, output_png=out_png)
            messagebox.showinfo("Успіх", f"Графік порівняння збережено у:\n{out_png}")
        except Exception as exc:
            messagebox.showerror("Помилка", str(exc))

    def on_clear(self) -> None:
        self.msg_text.delete("1.0", "end")
        self.result_text.delete("1.0", "end")
        self.wave_canvas.delete("all")
        self.mode_var.set("hide")


# ---------------------------------------------------------------------------
# Консольне меню (--cli)
# ---------------------------------------------------------------------------

def run_cli() -> None:
    """Консольний інтерфейс взаємодії з користувачем."""
    while True:
        print("\n====== Стеганографія у WAV (LSB) ======")
        print("1. Приховати повідомлення (LSB)")
        print("2. Вилучити повідомлення (LSB)")
        print("3. Приховати повідомлення (LSB + PRNG з ключем)")
        print("4. Вилучити повідомлення (LSB + PRNG з ключем)")
        print("5. Порівняти графіки хвиль та метрики")
        print("6. Згенерувати тестовий WAV-файл")
        print("0. Вихід")
        choice = input("Оберіть опцію: ").strip()

        try:
            if choice == "0":
                print("Роботу завершено.")
                break
            if choice == "1":
                in_wav = input("Шлях до оригіналу (WAV): ").strip().strip('"')
                out_wav = input("Шлях для збереження стего (WAV): ").strip().strip('"')
                msg = input("Повідомлення для вбудовування: ")
                res = embed_lsb(in_wav, out_wav, msg)
                print(f"Повідомлення сховано в {res.output_wav} ({res.bits_used} біт).")
            elif choice == "2":
                stego = input("Шлях до стего-файлу (WAV): ").strip().strip('"')
                res = extract_lsb(stego)
                print(f"Вилучене повідомлення:\n{res.message}")
            elif choice == "3":
                in_wav = input("Шлях до оригіналу (WAV): ").strip().strip('"')
                out_wav = input("Шлях для збереження стего (WAV): ").strip().strip('"')
                msg = input("Повідомлення для вбудовування: ")
                key = input("Секретний ключ: ")
                res = embed_lsb_prng(in_wav, out_wav, msg, key)
                print(f"Повідомлення сховано (LSB+PRNG) в {res.output_wav} ({res.bits_used} біт).")
            elif choice == "4":
                stego = input("Шлях до стего-файлу (WAV): ").strip().strip('"')
                key = input("Секретний ключ: ")
                res = extract_lsb_prng(stego, key)
                print(f"Вилучене повідомлення:\n{res.message}")
            elif choice == "5":
                orig = input("Шлях до оригіналу (WAV): ").strip().strip('"')
                stego = input("Шлях до стего-файлу (WAV): ").strip().strip('"')
                png = input("Шлях для збереження PNG-графіка (Enter щоб пропустити): ").strip().strip('"')
                comp = compare_audio(orig, stego, png or None)
                print(
                    f"Семплів: {comp.total_samples}, змінено: {comp.changed_samples} ({comp.changed_percent:.4f}%), "
                    f"макс. різниця: {comp.max_abs_diff}, PSNR: {comp.psnr_db:.2f} дБ"
                )
            elif choice == "6":
                path = input("Шлях для тестового WAV (напр. cover.wav): ").strip().strip('"') or "cover.wav"
                generate_sample_wav(path)
                print(f"Тестовий WAV створено: {path}")
            else:
                print("Невірний вибір.")
        except Exception as exc:
            print(f"[Помилка]: {exc}")


if __name__ == "__main__":
    if "--cli" in sys.argv:
        run_cli()
    else:
        app = AudioStegoApp()
        app.mainloop()

"""Головний модуль програми текстової стеганографії (GUI + CLI)."""

import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import List, Optional, Tuple

from file_io import load_stego_file, save_stego_file
from robustness import format_robustness_report, run_robustness_suite
from stego_methods import (
    COLOR_ONE,
    COLOR_ZERO,
    StegoResult,
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

METHODS = [
    "Символи нульової ширини (ZWC)",
    "Зміна регістру літер",
    "Маніпуляція пробілами",
    "Зміна кольору шрифту",
]

DEFAULT_COVER = (
    "The bright sun shone down on the quiet city, warming the old streets "
    "and filling the morning air with a soft golden glow for everyone. "
    "People walked slowly through the green park, enjoying the calm weather "
    "and talking about their plans for the upcoming weekend."
)
DEFAULT_SECRET = "Бондар Владислав"


def perform_hide(
    method: str,
    cover_text: str,
    secret_message: str,
    use_caesar: bool = False,
    caesar_shift: int = 3,
) -> StegoResult:
    """Виконує приховування повідомлення обраним методом (із опційним шифром Цезаря)."""
    processed = caesar_encrypt(secret_message, caesar_shift) if use_caesar else secret_message

    if method == METHODS[0]:
        res = zwc_hide(cover_text, processed)
    elif method == METHODS[1]:
        res = case_hide(cover_text, processed)
    elif method == METHODS[2]:
        res = whitespace_hide(cover_text, processed)
    elif method == METHODS[3]:
        res = color_hide(cover_text, processed)
    else:
        raise ValueError(f"Невідомий метод: {method}")

    res.original_message = secret_message
    res.processed_message = processed
    return res


def perform_extract(
    method: str,
    stego_text: str,
    color_tokens: Optional[List[Tuple[str, str]]] = None,
    use_caesar: bool = False,
    caesar_shift: int = 3,
) -> StegoResult:
    """Виконує вилучення повідомлення обраним методом (із опційним дешифруванням Цезаря)."""
    if method == METHODS[0]:
        res = zwc_extract(stego_text)
    elif method == METHODS[1]:
        res = case_extract(stego_text)
    elif method == METHODS[2]:
        res = whitespace_extract(stego_text)
    elif method == METHODS[3]:
        tokens = color_tokens if color_tokens else [(ch, COLOR_ZERO) for ch in stego_text]
        res = color_extract(tokens)
    else:
        raise ValueError(f"Невідомий метод: {method}")

    if use_caesar and res.extracted_message:
        res.processed_message = res.extracted_message
        res.extracted_message = caesar_decrypt(res.extracted_message, caesar_shift)
    return res


# ---------------------------------------------------------------------------
# GUI (Tkinter)
# ---------------------------------------------------------------------------

class StegoApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Лабораторна робота №3 — Текстова стеганографія")
        self.geometry("1040x780")
        self.minsize(900, 680)

        self.last_result: Optional[StegoResult] = None
        self.loaded_color_tokens: Optional[List[Tuple[str, str]]] = None

        self._build_ui()

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        # Верхня панель налаштувань
        ctrl_frame = ttk.LabelFrame(self, text="Параметри операції", padding=10)
        ctrl_frame.pack(fill="x", padx=10, pady=(10, 5))

        ttk.Label(ctrl_frame, text="Метод:").grid(row=0, column=0, sticky="w", padx=4)
        self.method_var = tk.StringVar(value=METHODS[0])
        method_cb = ttk.Combobox(
            ctrl_frame, textvariable=self.method_var, values=METHODS, state="readonly", width=32
        )
        method_cb.grid(row=0, column=1, sticky="w", padx=4)

        ttk.Label(ctrl_frame, text="Режим:").grid(row=0, column=2, sticky="w", padx=(14, 4))
        self.mode_var = tk.StringVar(value="hide")
        ttk.Radiobutton(ctrl_frame, text="Приховування", variable=self.mode_var, value="hide").grid(
            row=0, column=3, padx=4
        )
        ttk.Radiobutton(ctrl_frame, text="Вилучення", variable=self.mode_var, value="extract").grid(
            row=0, column=4, padx=4
        )

        self.caesar_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(ctrl_frame, text="Шифр Цезаря, зсув:", variable=self.caesar_var).grid(
            row=0, column=5, sticky="w", padx=(14, 4)
        )
        self.shift_var = tk.IntVar(value=3)
        ttk.Spinbox(ctrl_frame, from_=1, to=32, textvariable=self.shift_var, width=4).grid(
            row=0, column=6, sticky="w"
        )

        # Кнопки дій
        btn_frame = ttk.Frame(self, padding=(10, 4))
        btn_frame.pack(fill="x")

        ttk.Button(btn_frame, text="▶ Виконати", command=self.on_execute).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="💾 Зберегти стеготекст...", command=self.on_save).pack(
            side="left", padx=4
        )
        ttk.Button(btn_frame, text="📂 Відкрити файл...", command=self.on_open).pack(
            side="left", padx=4
        )
        ttk.Button(btn_frame, text="🧹 Очистити", command=self.on_clear).pack(
            side="left", padx=4
        )
        ttk.Button(btn_frame, text="🛡 Аналіз стійкості", command=self.on_robustness).pack(
            side="right", padx=4
        )

        # Область вхідних даних
        input_pane = ttk.PanedWindow(self, orient="horizontal")
        input_pane.pack(fill="both", expand=False, padx=10, pady=5)

        cover_lf = ttk.LabelFrame(input_pane, text="Текст-носій / Стеготекст", padding=6)
        self.cover_text = scrolledtext.ScrolledText(cover_lf, height=6, wrap="word", font=("Consolas", 10))
        self.cover_text.pack(fill="both", expand=True)
        self.cover_text.insert("1.0", DEFAULT_COVER)
        input_pane.add(cover_lf, weight=3)

        secret_lf = ttk.LabelFrame(input_pane, text="Секретне повідомлення", padding=6)
        self.secret_entry = scrolledtext.ScrolledText(secret_lf, height=6, wrap="word", font=("Consolas", 10))
        self.secret_entry.pack(fill="both", expand=True)
        self.secret_entry.insert("1.0", DEFAULT_SECRET)
        input_pane.add(secret_lf, weight=2)

        # Результати
        res_nb = ttk.Notebook(self)
        res_nb.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        # Вкладка 1: Повний звіт перетворень
        tab_summary = ttk.Frame(res_nb, padding=6)
        self.summary_text = scrolledtext.ScrolledText(tab_summary, wrap="word", font=("Consolas", 10))
        self.summary_text.pack(fill="both", expand=True)
        res_nb.add(tab_summary, text="Результати перетворень")

        # Вкладка 2: Стеготекст (з підтримкою кольорів)
        tab_stego = ttk.Frame(res_nb, padding=6)
        self.stego_preview = scrolledtext.ScrolledText(tab_stego, wrap="word", font=("Arial", 11))
        self.stego_preview.pack(fill="both", expand=True)
        self.stego_preview.tag_configure("bit1", foreground=COLOR_ONE)
        self.stego_preview.tag_configure("bit0", foreground=COLOR_ZERO)
        res_nb.add(tab_stego, text="Стеготекст (попередній перегляд)")

        # Вкладка 3: Аналіз стійкості
        tab_robust = ttk.Frame(res_nb, padding=6)
        self.robust_text = scrolledtext.ScrolledText(tab_robust, wrap="none", font=("Consolas", 10))
        self.robust_text.pack(fill="both", expand=True)
        res_nb.add(tab_robust, text="Стійкість методів")
        self.notebook = res_nb

        self._setup_clipboard_support()

    def _setup_clipboard_support(self) -> None:
        """Забезпечує роботу Ctrl+C/V/X/A для будь-якої розкладки (укр/англ) та контекстне меню."""
        self.bind_all("<Control-KeyPress>", self._handle_ctrl_keys)
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Вирізати", command=lambda: self._trigger_focused("<<Cut>>"))
        menu.add_command(label="Копіювати", command=lambda: self._trigger_focused("<<Copy>>"))
        menu.add_command(label="Вставити", command=lambda: self._trigger_focused("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Виділити все", command=self._select_all_focused)
        self._context_menu = menu

        for widget in (
            self.cover_text,
            self.secret_entry,
            self.summary_text,
            self.stego_preview,
            self.robust_text,
        ):
            widget.bind("<Button-3>", self._show_context_menu)

    def _show_context_menu(self, event: tk.Event) -> None:
        event.widget.focus_set()
        self._context_menu.tk_popup(event.x_root, event.y_root)

    def _trigger_focused(self, virtual_event: str) -> None:
        w = self.focus_get()
        if w is not None:
            w.event_generate(virtual_event)

    def _select_all_focused(self) -> None:
        w = self.focus_get()
        if isinstance(w, tk.Text):
            w.tag_add("sel", "1.0", "end-1c")
        elif isinstance(w, (tk.Entry, ttk.Entry)):
            w.select_range(0, "end")

    def _handle_ctrl_keys(self, event: tk.Event) -> Optional[str]:
        # Virtual-key codes on Windows: A=65, C=67, V=86, X=88 (працює незалежно від укр/англ розкладки)
        w = event.widget
        if not isinstance(w, (tk.Text, tk.Entry, ttk.Entry)):
            return None

        keysym_low = event.keysym.lower()
        if event.keycode == 86 and keysym_low != "v":
            w.event_generate("<<Paste>>")
            return "break"
        if event.keycode == 67 and keysym_low != "c":
            w.event_generate("<<Copy>>")
            return "break"
        if event.keycode == 88 and keysym_low != "x":
            w.event_generate("<<Cut>>")
            return "break"
        if event.keycode == 65:
            if isinstance(w, tk.Text):
                w.tag_add("sel", "1.0", "end-1c")
            else:
                w.select_range(0, "end")
            return "break"
        return None

    def on_execute(self) -> None:
        method = self.method_var.get()
        mode = self.mode_var.get()
        use_caesar = self.caesar_var.get()
        shift = self.shift_var.get()
        cover = self.cover_text.get("1.0", "end-1c")
        secret = self.secret_entry.get("1.0", "end-1c")

        try:
            if mode == "hide":
                res = perform_hide(method, cover, secret, use_caesar, shift)
                self.last_result = res
                self.loaded_color_tokens = res.color_tokens or None
                # Підставляємо стеготекст у прев'ю
                self._render_stego_preview(res)
            else:
                res = perform_extract(method, cover, self.loaded_color_tokens, use_caesar, shift)
                self.last_result = res
                self._render_stego_preview(res)

            self._render_summary(res, use_caesar, shift)
            self.notebook.select(0)
        except Exception as exc:
            messagebox.showerror("Помилка", str(exc))

    def _render_summary(self, res: StegoResult, use_caesar: bool, shift: int) -> None:
        lines = [
            f"Метод: {res.method}",
            f"Операція: {res.operation}",
        ]
        if res.bits_capacity > 0:
            lines.append(f"Ємність: використано {res.bits_used} біт із {res.bits_capacity} біт")
        else:
            lines.append(f"Розмір прихованих даних: {res.bits_used} біт")

        if res.operation == "Приховування":
            lines.append(f"\nПочаткове повідомлення: {res.original_message}")
            if use_caesar:
                lines.append(f"Після шифру Цезаря (зсув {shift}): {res.processed_message}")
            lines.append(f"Бінарне представлення:\n{res.binary_display}")
            lines.append(f"\nОригінальний текст:\n{res.cover_text}")
            lines.append(f"\nТекст із позначенням прихованих символів:\n{res.annotated_text}")
            lines.append(f"\nСтеготекст:\n{res.stego_text}")
        else:
            lines.append(f"\nВилучене повідомлення: {res.extracted_message}")
            if use_caesar and res.processed_message:
                lines.append(f"Вилучено (до дешифрування Цезаря): {res.processed_message}")
            lines.append(f"\nБінарне представлення:\n{res.binary_display}")
            lines.append(f"\nТекст із позначенням прихованих символів:\n{res.annotated_text}")

        self.summary_text.delete("1.0", "end")
        self.summary_text.insert("1.0", "\n".join(lines))

    def _render_stego_preview(self, res: StegoResult) -> None:
        self.stego_preview.delete("1.0", "end")
        if res.color_tokens:
            for ch, color in res.color_tokens:
                tag = "bit1" if color.upper() == COLOR_ONE else "bit0"
                self.stego_preview.insert("end", ch, tag)
        else:
            self.stego_preview.insert("1.0", res.stego_text)

    def on_save(self) -> None:
        if self.last_result is None or self.last_result.operation != "Приховування":
            messagebox.showwarning("Увага", "Спочатку виконайте приховування повідомлення.")
            return

        selected_type = tk.StringVar(value="Text files")
        file_path = filedialog.asksaveasfilename(
            title="Зберегти стеготекст",
            typevariable=selected_type,
            filetypes=[
                ("Text files", "*.txt"),
                ("Word documents", "*.docx"),
                ("HTML files", "*.html"),
            ],
        )
        if not file_path:
            return

        ext_map = {
            "Text files": ".txt",
            "Word documents": ".docx",
            "HTML files": ".html",
        }
        if Path(file_path).suffix.lower() not in (".txt", ".docx", ".html"):
            file_path += ext_map.get(selected_type.get(), ".txt")

        if file_path.lower().endswith(".txt") and self.last_result.color_tokens:
            messagebox.showinfo(
                "Примітка",
                "Формат .txt не зберігає кольори шрифту. Для збереження кольорів використовуйте .docx або .html.",
            )

        try:
            save_stego_file(self.last_result, file_path)
            messagebox.showinfo("Успіх", f"Стеготекст збережено у:\n{file_path}")
        except Exception as exc:
            messagebox.showerror("Помилка збереження", str(exc))

    def on_open(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Відкрити файл зі стеготекстом",
            filetypes=[
                ("Підтримувані файли", "*.txt *.docx *.html"),
                ("Text files", "*.txt"),
                ("Word documents", "*.docx"),
                ("HTML files", "*.html"),
            ],
        )
        if not file_path:
            return

        try:
            text, tokens = load_stego_file(file_path)
            self.cover_text.delete("1.0", "end")
            self.cover_text.insert("1.0", text)
            self.loaded_color_tokens = tokens
            self.mode_var.set("extract")
            messagebox.showinfo("Файл завантажено", "Файл завантажено. Оберіть метод та натисніть «Виконати».")
        except Exception as exc:
            messagebox.showerror("Помилка читання", str(exc))

    def on_clear(self) -> None:
        """Повністю очищає всі поля інтерфейсу та внутрішній стан завантажених файлів."""
        for widget in (
            self.cover_text,
            self.secret_entry,
            self.summary_text,
            self.stego_preview,
            self.robust_text,
        ):
            widget.delete("1.0", "end")
        self.last_result = None
        self.loaded_color_tokens = None
        self.mode_var.set("hide")

    def on_robustness(self) -> None:
        cases = run_robustness_suite()
        report = format_robustness_report(cases)
        self.robust_text.delete("1.0", "end")
        self.robust_text.insert("1.0", report)
        self.notebook.select(2)


# ---------------------------------------------------------------------------
# CLI-меню
# ---------------------------------------------------------------------------

def run_cli() -> None:
    """Інтерактивне консольне меню."""
    while True:
        print("\n=== Текстова стеганографія (ЛР №3) ===")
        print("1. Приховати повідомлення")
        print("2. Вилучити повідомлення (з тексту або файлу)")
        print("3. Перевірити стійкість методів")
        print("0. Вихід")
        choice = input("Ваш вибір: ").strip()

        if choice == "0":
            break
        if choice == "3":
            print("\n" + format_robustness_report(run_robustness_suite()))
            continue
        if choice not in ("1", "2"):
            print("Невірний вибір.")
            continue

        print("\nОберіть метод:")
        for idx, name in enumerate(METHODS, 1):
            print(f"{idx}. {name}")
        m_idx = input("Метод (1-4): ").strip()
        if m_idx not in ("1", "2", "3", "4"):
            print("Невірний метод.")
            continue
        method = METHODS[int(m_idx) - 1]

        use_caesar = input("Використовувати шифр Цезаря? (y/n): ").strip().lower() == "y"
        shift = int(input("Зсув (напр. 3): ").strip() or "3") if use_caesar else 3

        try:
            if choice == "1":
                cover = input("Текст-носій (Enter — стандартний): ").strip() or DEFAULT_COVER
                secret = input("Секретне повідомлення: ").strip() or DEFAULT_SECRET
                res = perform_hide(method, cover, secret, use_caesar, shift)
                print(f"\nБінарний вигляд:\n{res.binary_display}")
                print(f"Позначений текст:\n{res.annotated_text}")
                print(f"Стеготекст:\n{res.stego_text}")
                save_path = input("Зберегти у файл (.txt/.docx/.html) або Enter для пропуску: ").strip()
                if save_path:
                    save_stego_file(res, save_path)
                    print("Збережено успішно.")
            else:
                path = input("Шлях до файлу (.txt/.docx/.html) або Enter для вводу тексту: ").strip()
                if path:
                    text, tokens = load_stego_file(path)
                else:
                    text = input("Введіть стеготекст: ")
                    tokens = None
                res = perform_extract(method, text, tokens, use_caesar, shift)
                print(f"\nПозначений текст:\n{res.annotated_text}")
                print(f"Вилучене повідомлення: {res.extracted_message}")
        except Exception as exc:
            print(f"[Помилка] {exc}")


if __name__ == "__main__":
    if "--cli" in sys.argv:
        run_cli()
    else:
        app = StegoApp()
        app.mainloop()

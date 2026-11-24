"""Модуль збереження та зчитування стеготексту у форматах TXT, HTML та DOCX."""

import html
import re
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional, Tuple

from stego_methods import COLOR_ZERO, NBSP, StegoResult

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"


def save_stego_file(result: StegoResult, file_path: str) -> None:
    """Зберігає результат приховування у файл (.txt, .html, .docx)."""
    ext = Path(file_path).suffix.lower()
    if ext == ".txt":
        _save_txt(result.stego_text, file_path)
    elif ext == ".html":
        _save_html(result, file_path)
    elif ext == ".docx":
        _save_docx(result, file_path)
    else:
        raise ValueError(f"Непідтримуваний формат файлу: {ext}. Використовуйте .txt, .html або .docx.")


def load_stego_file(file_path: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Зчитує стеготекст і (за наявності) токени кольорів із файлу (.txt, .html, .docx)."""
    ext = Path(file_path).suffix.lower()
    if ext == ".txt":
        text = _load_txt(file_path)
        return text, [(ch, COLOR_ZERO) for ch in text]
    if ext == ".html":
        return _load_html(file_path)
    if ext == ".docx":
        return _load_docx(file_path)
    raise ValueError(f"Непідтримуваний формат файлу: {ext}. Використовуйте .txt, .html або .docx.")


# ---------------------------------------------------------------------------
# TXT
# ---------------------------------------------------------------------------

def _save_txt(text: str, file_path: str) -> None:
    with open(file_path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def _load_txt(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8", newline="") as f:
        return f.read()


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

def _save_html(result: StegoResult, file_path: str) -> None:
    if result.color_tokens:
        body_parts = []
        for ch, color in result.color_tokens:
            if ch == "\n":
                body_parts.append("<br>\n")
            elif ch == NBSP:
                body_parts.append("&nbsp;")
            else:
                escaped = html.escape(ch, quote=False)
                body_parts.append(f'<span style="color: {color};">{escaped}</span>')
        body_html = "".join(body_parts)
    else:
        escaped = html.escape(result.stego_text, quote=False)
        escaped = escaped.replace(NBSP, "&nbsp;").replace("\n", "<br>\n")
        body_html = escaped

    doc = (
        "<!DOCTYPE html>\n"
        '<html lang="uk">\n'
        "<head>\n"
        '  <meta charset="UTF-8">\n'
        "  <title>Stegotext</title>\n"
        "</head>\n"
        "<body>\n"
        f'  <div id="stegotext" style="font-family: Arial, sans-serif; white-space: pre-wrap;">{body_html}</div>\n'
        "</body>\n"
        "</html>\n"
    )
    with open(file_path, "w", encoding="utf-8", newline="") as f:
        f.write(doc)


class _StegoHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.in_container = False
        self.color_stack: List[str] = [COLOR_ZERO]
        self.tokens: List[Tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        attr_dict = dict(attrs)
        if tag == "div" and attr_dict.get("id") == "stegotext":
            self.in_container = True
            return
        if not self.in_container:
            return
        if tag == "br":
            self.tokens.append(("\n", self.color_stack[-1]))
        elif tag == "span":
            style = attr_dict.get("style") or ""
            match = re.search(r"color:\s*(#[0-9a-fA-F]{6})", style)
            color = match.group(1).upper() if match else self.color_stack[-1]
            self.color_stack.append(color)

    def handle_endtag(self, tag: str) -> None:
        if tag == "div" and self.in_container:
            self.in_container = False
        elif tag == "span" and self.in_container and len(self.color_stack) > 1:
            self.color_stack.pop()

    def handle_data(self, data: str) -> None:
        if not self.in_container:
            return
        current_color = self.color_stack[-1]
        for ch in data:
            if ch != "\r":
                self.tokens.append((ch, current_color))

    def handle_entityref(self, name: str) -> None:
        if not self.in_container:
            return
        ch = html.unescape(f"&{name};")
        self.tokens.append((ch, self.color_stack[-1]))

    def handle_charref(self, name: str) -> None:
        if not self.in_container:
            return
        ch = html.unescape(f"&#{name};")
        self.tokens.append((ch, self.color_stack[-1]))


def _load_html(file_path: str) -> Tuple[str, List[Tuple[str, str]]]:
    with open(file_path, "r", encoding="utf-8") as f:
        raw = f.read()

    parser = _StegoHTMLParser()
    parser.feed(raw)
    parser.close()

    # Видаляємо службові переноси рядків, додані після <br>\n при форматуванні HTML
    cleaned_tokens: List[Tuple[str, str]] = []
    skip_next_newline = False
    for idx, (ch, color) in enumerate(parser.tokens):
        if skip_next_newline and ch == "\n":
            skip_next_newline = False
            continue
        skip_next_newline = False
        if ch == "\n" and idx + 1 < len(parser.tokens) and parser.tokens[idx + 1][0] == "\n":
            skip_next_newline = True
        cleaned_tokens.append((ch, color))

    text = "".join(ch for ch, _ in cleaned_tokens)
    return text, cleaned_tokens


# ---------------------------------------------------------------------------
# DOCX (чистий OOXML без зовнішніх бібліотек)
# ---------------------------------------------------------------------------

_CONTENT_TYPES_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    "</Types>"
)

_RELS_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="word/document.xml"/>'
    "</Relationships>"
)


def _save_docx(result: StegoResult, file_path: str) -> None:
    ET.register_namespace("w", W_NS)
    document = ET.Element(f"{{{W_NS}}}document")
    body = ET.SubElement(document, f"{{{W_NS}}}body")

    tokens = result.color_tokens if result.color_tokens else [(ch, COLOR_ZERO) for ch in result.stego_text]

    # Розбиваємо на абзаци за символом нового рядка
    paragraphs: List[List[Tuple[str, str]]] = [[]]
    for ch, color in tokens:
        if ch == "\n":
            paragraphs.append([])
        else:
            paragraphs[-1].append((ch, color))

    for para_tokens in paragraphs:
        p = ET.SubElement(body, f"{{{W_NS}}}p")
        if result.color_tokens:
            for ch, color in para_tokens:
                _append_docx_run(p, ch, color.lstrip("#"))
        else:
            _append_docx_run(p, "".join(ch for ch, _ in para_tokens), None)

    xml_bytes = ET.tostring(document, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(file_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES_XML.encode("utf-8"))
        zf.writestr("_rels/.rels", _RELS_XML.encode("utf-8"))
        zf.writestr("word/document.xml", xml_bytes)


def _append_docx_run(paragraph: ET.Element, text: str, hex_color: Optional[str]) -> None:
    r = ET.SubElement(paragraph, f"{{{W_NS}}}r")
    if hex_color is not None:
        r_pr = ET.SubElement(r, f"{{{W_NS}}}rPr")
        color_el = ET.SubElement(r_pr, f"{{{W_NS}}}color")
        color_el.set(f"{{{W_NS}}}val", hex_color)
    t = ET.SubElement(r, f"{{{W_NS}}}t")
    t.set(f"{{{XML_NS}}}space", "preserve")
    t.text = text


def _load_docx(file_path: str) -> Tuple[str, List[Tuple[str, str]]]:
    with zipfile.ZipFile(file_path, "r") as zf:
        xml_data = zf.read("word/document.xml")

    root = ET.fromstring(xml_data)
    body = root.find(f"{{{W_NS}}}body")
    if body is None:
        return "", []

    paragraphs = body.findall(f"{{{W_NS}}}p")
    tokens: List[Tuple[str, str]] = []

    for p_idx, p in enumerate(paragraphs):
        if p_idx > 0:
            tokens.append(("\n", COLOR_ZERO))
        for r in p.findall(f"{{{W_NS}}}r"):
            color = COLOR_ZERO
            r_pr = r.find(f"{{{W_NS}}}rPr")
            if r_pr is not None:
                color_el = r_pr.find(f"{{{W_NS}}}color")
                if color_el is not None:
                    val = color_el.get(f"{{{W_NS}}}val")
                    if val and val.lower() != "auto":
                        color = "#" + val.upper()
            for t in r.findall(f"{{{W_NS}}}t"):
                if t.text:
                    for ch in t.text:
                        tokens.append((ch, color))

    text = "".join(ch for ch, _ in tokens)
    return text, tokens

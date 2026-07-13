"""Пользовательское Streamlit-приложение МироВизор."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import streamlit as st

from miro_vizor.exporter import MiroExporter
from miro_vizor.graphify_adapter import MiroGraphifyExporter
from miro_vizor.languages import detect_language
from miro_vizor.marker import MiroMarker
from miro_vizor.ontology import MiroOntology


# ── Автоопределение кодировки текстовых файлов (.txt, .md) ──────────────

# Порядок важен: BOM → UTF-8 → Windows-1251 (кириллица) → Latin-1 fallback.
_TXT_ENCODINGS = [
    "utf-8-sig",   # UTF-8 с BOM или без
    "utf-8",       # чистый UTF-8 без BOM
    "cp1251",      # ANSI / Windows-1251 (русская кодировка)
    "utf-16-le",   # UTF-16 Little Endian
    "utf-16-be",   # UTF-16 Big Endian
]


def _detect_encoding(raw_bytes: bytes, *, filename: str = "") -> str:
    """Подобрать кодировку по байтам файла.

    Возвращает название кодировки из :pymod:`codecs`, которую можно передать в
    ``bytes.decode()``.
    """
    if not raw_bytes:
        return "utf-8"

    # 1. BOM — самый надёжный признак.
    if raw_bytes[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    if raw_bytes[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "utf-16-le" if raw_bytes[:2] == b"\xff\xfe" else "utf-16-be"
    if raw_bytes[:2] == b"\x00\x00":
        return "utf-32-be" if len(raw_bytes) > 2 else "utf-8"

    # 2. Пробуем каждую кодировку по очереди; первая успешная побеждает.
    sample = raw_bytes[:8192]
    for enc in _TXT_ENCODINGS:
        try:
            decoded = sample.decode(enc, errors="strict")
            # Для cp1251 проверяем, что результат не мусорный (есть читаемые символы).
            if enc == "cp1251" and not any(
                "\u0400" <= ch <= "\u04ff" or ch.isalnum() or ch.isspace()
                for ch in decoded
            ):
                continue
            return enc
        except (UnicodeDecodeError, ValueError):
            continue

    # 3. Fallback — latin-1 никогда не падает на decode.
    return "latin-1"


def _read_uploaded_text(uploaded_file: Any) -> str | None:
    """Прочитать загруженный файл с автоопределением кодировки.

    Возвращает декодированный текст или ``None`` при ошибке.
    """
    try:
        raw: bytes = uploaded_file.getvalue()
    except Exception:
        return None
    enc = _detect_encoding(raw, filename=uploaded_file.name)
    try:
        text = raw.decode(enc)
    except Exception:
        st.session_state["upload_encoding_error"] = (
            f"Не удалось прочитать файл «{uploaded_file.name}» "
            f"(определена кодировка: {enc}). Попробуйте сохранить его как UTF-8."
        )
        return None
    st.session_state["upload_detected_encoding"] = enc
    return text

DEFAULT_TEXT = (
    "Глава 1. Гармония\n\n"
    "Гармония природы требует сотрудничества всех живых систем. "
    "Язык и диалог помогают увидеть общую картину."
)

# Символы слоёв Миросложения (читаемые и в светлой, и в тёмной теме).
LEVEL_SYMBOLS: dict[str, str] = {
    "L1": "⬡",
    "L2": "∿",
    "L3": "✦",
    "L4": "❖",
    "L5": "◎",
    "L6": "✶",
    "L7": "◉",
}

LEVEL_FALLBACK_HINTS: dict[str, str] = {
    "L1": "Основа, структура, выживание",
    "L2": "Динамика, эмоции, движение",
    "L3": "Воля, регуляция, намерение",
    "L4": "Гармония, связь, симбиоз",
    "L5": "Коммуникация, сигналы, речь",
    "L6": "Паттерны, интуиция, карты смысла",
    "L7": "Целостность, эмерджентность, целое",
}


def _level_symbol(level_id: str | None) -> str:
    if not level_id:
        return "○"
    return LEVEL_SYMBOLS.get(level_id, "○")


def _apply_styles(theme: str) -> None:
    dark = theme == "Тёмная"
    # CSS variables for both themes
    if dark:
        root_vars = """
        --miro-ink: #e8eef8;
        --miro-muted: #9aa8bf;
        --miro-line: rgba(180, 200, 230, 0.12);
        --miro-card: rgba(22, 30, 48, 0.82);
        --miro-card-solid: #161e30;
        --miro-soft: #121826;
        --miro-page-a: #0d121c;
        --miro-page-b: #121a2a;
        --miro-page-c: #17132a;
        --miro-page-d: #101820;
        --miro-hero-a: #0f1626;
        --miro-hero-b: #1a2d4a;
        --miro-hero-c: #1d3f3a;
        --miro-hero-d: #2a2140;
        --miro-sidebar: linear-gradient(180deg, #121a28 0%, #0f1520 100%);
        --miro-header: rgba(13, 18, 28, 0.72);
        --miro-empty-bg: rgba(18, 26, 42, 0.85);
        --miro-chip-bg: rgba(255,255,255,0.10);
        --miro-input-bg: rgba(12, 16, 26, 0.55);
        """
        app_bg_extra = """
            radial-gradient(circle at 12% 18%, rgba(229, 57, 53, 0.16), transparent 28%),
            radial-gradient(circle at 28% 72%, rgba(251, 140, 0, 0.12), transparent 30%),
            radial-gradient(circle at 48% 20%, rgba(253, 216, 53, 0.10), transparent 26%),
            radial-gradient(circle at 66% 78%, rgba(67, 160, 71, 0.12), transparent 30%),
            radial-gradient(circle at 82% 24%, rgba(30, 136, 229, 0.14), transparent 28%),
            radial-gradient(circle at 90% 70%, rgba(57, 73, 171, 0.16), transparent 30%),
            radial-gradient(circle at 74% 46%, rgba(142, 36, 170, 0.14), transparent 24%),
            linear-gradient(165deg, var(--miro-page-a) 0%, var(--miro-page-b) 42%, var(--miro-page-c) 72%, var(--miro-page-d) 100%)
        """
        rings = "rgba(232, 238, 248, 0.06)"
        grid = "rgba(232, 238, 248, 0.03)"
    else:
        root_vars = """
        --miro-ink: #1a2233;
        --miro-muted: #5b667a;
        --miro-line: rgba(28, 42, 68, 0.10);
        --miro-card: rgba(255, 252, 248, 0.86);
        --miro-card-solid: #fffdf9;
        --miro-soft: #f4f0ea;
        --miro-page-a: #f7f1ea;
        --miro-page-b: #eef4fb;
        --miro-page-c: #f5eef8;
        --miro-page-d: #f8f4ee;
        --miro-hero-a: #1b2742;
        --miro-hero-b: #253f67;
        --miro-hero-c: #2f5f58;
        --miro-hero-d: #3a2e55;
        --miro-sidebar: linear-gradient(180deg, rgba(255,253,249,0.96) 0%, rgba(241,245,251,0.94) 100%);
        --miro-header: rgba(247, 241, 234, 0.55);
        --miro-empty-bg: rgba(255, 253, 249, 0.8);
        --miro-chip-bg: rgba(255,255,255,0.12);
        --miro-input-bg: rgba(255,253,249,0.7);
        """
        app_bg_extra = """
            radial-gradient(circle at 12% 18%, rgba(229, 57, 53, 0.14), transparent 28%),
            radial-gradient(circle at 28% 72%, rgba(251, 140, 0, 0.12), transparent 30%),
            radial-gradient(circle at 48% 20%, rgba(253, 216, 53, 0.16), transparent 26%),
            radial-gradient(circle at 66% 78%, rgba(67, 160, 71, 0.14), transparent 30%),
            radial-gradient(circle at 82% 24%, rgba(30, 136, 229, 0.13), transparent 28%),
            radial-gradient(circle at 90% 70%, rgba(57, 73, 171, 0.14), transparent 30%),
            radial-gradient(circle at 74% 46%, rgba(142, 36, 170, 0.12), transparent 24%),
            linear-gradient(165deg, var(--miro-page-a) 0%, var(--miro-page-b) 42%, var(--miro-page-c) 72%, var(--miro-page-d) 100%)
        """
        rings = "rgba(26, 34, 51, 0.035)"
        grid = "rgba(26, 34, 51, 0.015)"

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Spectral:ital,wght@0,500;0,600;1,500&display=swap');

        :root {{
            {root_vars}
            --l1: #E53935; --l2: #FB8C00; --l3: #FDD835;
            --l4: #43A047; --l5: #1E88E5; --l6: #3949AB; --l7: #8E24AA;
        }}

        html, body, [class*="css"]  {{
            font-family: "Manrope", "Segoe UI", sans-serif;
        }}

        .stApp {{
            color: var(--miro-ink);
            background: {app_bg_extra};
            background-attachment: fixed;
        }}

        .stApp::before {{
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            z-index: 0;
            opacity: 0.7;
            background-image:
                radial-gradient(circle at center, transparent 0 46%, {rings} 47%, transparent 52%),
                radial-gradient(circle at center, transparent 0 62%, {rings} 63%, transparent 68%),
                radial-gradient(circle at center, transparent 0 78%, {rings} 79%, transparent 84%),
                repeating-linear-gradient(
                    -18deg,
                    transparent 0 18px,
                    {grid} 18px 19px
                );
            background-size: min(92vmin, 820px) min(92vmin, 820px), min(92vmin, 820px) min(92vmin, 820px),
                min(92vmin, 820px) min(92vmin, 820px), auto;
            background-position: 82% 12%, 82% 12%, 82% 12%, 0 0;
            background-repeat: no-repeat, no-repeat, no-repeat, repeat;
        }}

        /* floating level glyphs at edges of the world-layer canvas */
        .stApp::after {{
            content: "⬡  ∿  ✦  ❖  ◎  ✶  ◉";
            position: fixed;
            left: 1.2rem;
            bottom: 1rem;
            z-index: 0;
            pointer-events: none;
            font-size: 0.95rem;
            letter-spacing: 0.55rem;
            opacity: {"0.18" if dark else "0.14"};
            color: var(--miro-ink);
            filter: blur(0.2px);
        }}

        .stApp > header {{ background: transparent; }}
        .block-container {{
            position: relative;
            z-index: 1;
            max-width: 1180px;
            padding-top: 1.4rem;
            padding-bottom: 3rem;
        }}

        h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {{
            color: var(--miro-ink) !important;
            font-family: "Manrope", "Segoe UI", sans-serif !important;
            letter-spacing: -0.02em;
            font-weight: 700 !important;
        }}

        p, label, .stMarkdown, .stCaption, .stText, .stAlert {{
            color: var(--miro-ink);
        }}

        [data-testid="stSidebar"] {{
            background: var(--miro-sidebar);
            border-right: 1px solid var(--miro-line);
        }}
        [data-testid="stSidebar"] * {{ color: var(--miro-ink) !important; }}
        [data-testid="stSidebar"] .stCaption {{ color: var(--miro-muted) !important; }}
        [data-testid="stSidebar"] hr {{
            border-color: var(--miro-line) !important;
            margin: 0.85rem 0 !important;
        }}

        [data-testid="stHeader"] {{ background: var(--miro-header); backdrop-filter: blur(8px); }}

        .hero {{
            position: relative;
            overflow: hidden;
            padding: 1.55rem 1.8rem 1.4rem;
            border-radius: 24px;
            color: #fff;
            margin-bottom: 1.15rem;
            border: 1px solid rgba(255,255,255,0.18);
            background:
                radial-gradient(circle at 88% 20%, rgba(253, 216, 53, 0.28), transparent 22%),
                radial-gradient(circle at 78% 78%, rgba(67, 160, 71, 0.22), transparent 24%),
                radial-gradient(circle at 96% 58%, rgba(142, 36, 170, 0.25), transparent 20%),
                linear-gradient(125deg, var(--miro-hero-a) 0%, var(--miro-hero-b) 42%, var(--miro-hero-c) 78%, var(--miro-hero-d) 100%);
            box-shadow: 0 18px 42px rgba(8, 12, 24, 0.28);
        }}
        .hero::before {{
            content: "";
            position: absolute;
            width: 220px; height: 220px;
            right: -20px; top: -40px;
            border-radius: 50%;
            border: 2px solid rgba(255,255,255,0.14);
            box-shadow:
                0 0 0 18px rgba(255,255,255,0.05),
                0 0 0 36px rgba(255,255,255,0.035),
                inset 0 0 40px rgba(255,255,255,0.06);
        }}
        .hero::after {{
            content: "";
            position: absolute;
            left: 0; right: 0; bottom: 0; height: 7px;
            background: linear-gradient(90deg,
                var(--l1), var(--l2), var(--l3), var(--l4),
                var(--l5), var(--l6), var(--l7));
        }}
        .hero h1 {{
            color: #fff !important;
            margin: 0 0 .4rem 0 !important;
            font-size: clamp(1.7rem, 2.4vw, 2.15rem) !important;
            font-weight: 800 !important;
        }}
        .hero p {{
            margin: 0;
            max-width: 46rem;
            opacity: .94;
            font-size: 1.05rem;
            line-height: 1.55;
            color: rgba(255,255,255,0.92) !important;
        }}
        .hero-levels {{
            display: flex;
            flex-wrap: wrap;
            gap: .45rem;
            margin-top: 1rem;
        }}
        .hero-chip {{
            display: inline-flex;
            align-items: center;
            gap: .4rem;
            padding: .3rem .7rem;
            border-radius: 999px;
            font-size: .78rem;
            font-weight: 600;
            letter-spacing: .01em;
            color: #fff;
            background: var(--miro-chip-bg);
            border: 1px solid rgba(255,255,255,0.16);
            backdrop-filter: blur(4px);
        }}
        .hero-glyph {{
            font-size: .95rem;
            line-height: 1;
            opacity: .95;
        }}
        .hero-dot {{
            width: .5rem; height: .5rem; border-radius: 50%;
            box-shadow: 0 0 0 2px rgba(255,255,255,0.22);
        }}

        div[data-testid="stTabs"] {{
            background: var(--miro-card);
            border: 1px solid var(--miro-line);
            border-radius: 20px;
            padding: .55rem .7rem 1rem;
            box-shadow: 0 10px 30px rgba(8, 12, 24, 0.08);
            backdrop-filter: blur(10px);
        }}
        button[data-baseweb="tab"] {{
            font-weight: 600 !important;
            color: var(--miro-muted) !important;
        }}
        button[data-baseweb="tab"][aria-selected="true"] {{
            color: var(--miro-ink) !important;
        }}

        [data-testid="stMetric"] {{
            background: var(--miro-card-solid);
            border: 1px solid var(--miro-line);
            border-radius: 16px;
            padding: .7rem .85rem .85rem;
            box-shadow: 0 8px 20px rgba(8, 12, 24, 0.06);
        }}
        [data-testid="stMetricLabel"] {{ color: var(--miro-muted) !important; }}
        [data-testid="stMetricValue"] {{
            color: var(--miro-ink) !important;
            font-size: 1.15rem !important;
            font-weight: 700 !important;
        }}

        .level-card {{
            padding: 1.15rem 1.25rem;
            border-radius: 18px;
            background: var(--miro-card-solid);
            border: 1px solid var(--miro-line);
            box-shadow: 0 10px 26px rgba(8, 12, 24, 0.06);
            min-height: 108px;
            position: relative;
            overflow: hidden;
        }}
        .level-card::before {{
            content: "";
            position: absolute;
            left: 0; top: 0; bottom: 0; width: 6px;
            background: linear-gradient(180deg, var(--l1), var(--l4), var(--l7));
        }}
        .level-card .level-head {{
            display: flex;
            align-items: center;
            gap: .55rem;
            margin: 0 0 .45rem 0;
            padding-left: .45rem;
        }}
        .level-card .level-head .glyph {{
            width: 2rem; height: 2rem;
            border-radius: 10px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 1.1rem;
            color: #fff;
            flex-shrink: 0;
            box-shadow: 0 4px 12px rgba(0,0,0,0.12);
        }}
        .level-card h3 {{
            margin: 0 !important;
            font-size: 1.15rem !important;
            color: var(--miro-ink) !important;
        }}
        .level-card p {{
            margin: 0;
            padding-left: .45rem;
            color: var(--miro-muted) !important;
            line-height: 1.55;
            font-size: 0.98rem;
        }}

        .spectrum-block {{
            background: var(--miro-card-solid);
            border: 1px solid var(--miro-line);
            border-radius: 18px;
            padding: 1rem 1.1rem .85rem;
            box-shadow: 0 8px 22px rgba(8, 12, 24, 0.05);
        }}
        .spectrum-row {{ margin: .72rem 0; }}
        .spectrum-label {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            gap: 1rem;
            margin-bottom: .34rem;
            color: var(--miro-ink);
            font-size: 0.95rem;
        }}
        .spectrum-label .left {{
            display: inline-flex;
            align-items: center;
            gap: .45rem;
            font-weight: 700;
        }}
        .spectrum-label .left .glyph {{
            width: 1.45rem;
            height: 1.45rem;
            border-radius: 8px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: .85rem;
            color: #fff;
            flex-shrink: 0;
        }}
        .spectrum-label span.pct {{
            color: var(--miro-muted);
            font-variant-numeric: tabular-nums;
            font-weight: 600;
        }}
        .spectrum-track {{
            height: 14px;
            border-radius: 999px;
            background: linear-gradient(90deg, rgba(128,128,128,0.10), rgba(128,128,128,0.05));
            border: 1px solid var(--miro-line);
            overflow: hidden;
        }}
        .spectrum-fill {{
            height: 100%;
            border-radius: 999px;
            box-shadow: inset 0 0 0 1px rgba(255,255,255,0.25);
        }}

        .legend-title {{
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            color: var(--miro-muted) !important;
            margin: 0.2rem 0 0.55rem 0;
        }}
        .legend-list {{
            display: flex;
            flex-direction: column;
            gap: 0.45rem;
            margin-bottom: 0.35rem;
        }}
        .legend-item {{
            display: grid;
            grid-template-columns: 1.6rem 1fr;
            gap: 0.55rem;
            align-items: start;
            padding: 0.45rem 0.5rem;
            border-radius: 12px;
            background: {"rgba(255,255,255,0.04)" if dark else "rgba(26,34,51,0.03)"};
            border: 1px solid var(--miro-line);
        }}
        .legend-glyph {{
            width: 1.6rem;
            height: 1.6rem;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #fff;
            font-size: 0.85rem;
            margin-top: 0.1rem;
        }}
        .legend-body strong {{
            display: block;
            font-size: 0.82rem;
            font-weight: 700;
            color: var(--miro-ink) !important;
            line-height: 1.25;
        }}
        .legend-body span {{
            display: block;
            font-size: 0.72rem;
            color: var(--miro-muted) !important;
            line-height: 1.35;
            margin-top: 0.12rem;
        }}

        .symbol-key {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem;
            margin: 0.35rem 0 0.75rem 0;
        }}
        .symbol-pill {{
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
            padding: 0.22rem 0.5rem;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 600;
            color: var(--miro-ink);
            background: var(--miro-card-solid);
            border: 1px solid var(--miro-line);
        }}
        .symbol-pill i {{
            font-style: normal;
            color: #fff;
            width: 1.15rem;
            height: 1.15rem;
            border-radius: 6px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 0.72rem;
        }}

        .empty-state {{
            padding: 2.2rem 1.4rem;
            text-align: center;
            border: 1px dashed {"rgba(180,200,230,0.28)" if dark else "rgba(28, 42, 68, 0.22)"};
            border-radius: 18px;
            color: var(--miro-muted);
            background:
                radial-gradient(circle at 50% 0%, rgba(30, 136, 229, 0.10), transparent 45%),
                var(--miro-empty-bg);
            line-height: 1.55;
        }}
        .empty-state strong {{
            display: block;
            color: var(--miro-ink);
            font-size: 1.05rem;
            margin-bottom: .35rem;
        }}
        .empty-glyphs {{
            display: flex;
            justify-content: center;
            gap: 0.55rem;
            margin-bottom: 0.85rem;
            font-size: 1.15rem;
            opacity: 0.85;
        }}
        .empty-glyphs span {{
            width: 2rem; height: 2rem;
            border-radius: 10px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            color: #fff;
            font-size: 0.95rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.12);
        }}

        .miro-ribbon {{
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: .35rem;
            margin: 0 0 1rem 0;
        }}
        .miro-ribbon span {{
            height: 8px;
            border-radius: 999px;
            box-shadow: 0 2px 8px rgba(8, 12, 24, 0.12);
        }}

        .stButton > button {{
            border-radius: 12px !important;
            font-weight: 700 !important;
            border: 1px solid rgba(26, 34, 51, 0.08) !important;
            transition: transform .12s ease, box-shadow .12s ease;
        }}
        .stButton > button:hover {{
            transform: translateY(-1px);
            box-shadow: 0 8px 18px rgba(8, 12, 24, 0.16) !important;
        }}
        .stButton > button[kind="primary"],
        .stButton > button[data-testid="baseButton-primary"] {{
            background: linear-gradient(135deg, #2b4170 0%, #2f6b5d 100%) !important;
            color: #fff !important;
        }}

        textarea, [data-baseweb="input"] input, [data-baseweb="base-input"] {{
            border-radius: 12px !important;
        }}
        [data-testid="stFileUploader"] {{
            background: var(--miro-input-bg);
            border-radius: 14px;
            padding: .35rem .2rem;
        }}
        [data-testid="stExpander"] {{
            background: {"rgba(18,26,42,0.75)" if dark else "rgba(255,253,249,0.8)"};
            border: 1px solid var(--miro-line);
            border-radius: 14px !important;
        }}
        iframe {{
            border-radius: 16px !important;
            border: 1px solid var(--miro-line) !important;
            background: {"#0f1520" if dark else "#fff"};
        }}
        .stSuccess, .stInfo, .stWarning, .stError {{
            border-radius: 14px;
        }}

        /* Streamlit optional dark widget polish */
        [data-testid="stWidgetLabel"] p {{
            color: var(--miro-ink) !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource(show_spinner=False)
def _build_marker(language: str, use_embeddings: bool) -> MiroMarker:
    ontology = MiroOntology.from_package(language=language)
    return MiroMarker(
        ontology=ontology,
        use_embeddings=use_embeddings,
        language=language,
    )


def _load_uploaded_text(uploaded_file: Any) -> None:
    if uploaded_file is None:
        return

    file_key = f"{uploaded_file.name}:{uploaded_file.size}"
    if st.session_state.get("loaded_file_key") == file_key:
        return  # этот файл уже загружен в этом сеансе

    # Очистим предыдущую ошибку, если была.
    st.session_state.pop("upload_encoding_error", None)

    text = _read_uploaded_text(uploaded_file)
    if text is None:
        error_msg = st.session_state.get("upload_encoding_error")
        if error_msg:
            st.error(error_msg)
            return

    st.session_state["input_text"] = text
    st.session_state["document_title"] = Path(uploaded_file.name).stem
    st.session_state["loaded_file_key"] = file_key

    # Покажем пользователю определённую кодировку.
    enc = st.session_state.get("upload_detected_encoding", "?")
    st.caption(f"📄 Файл загружен · кодировка: **{enc}**")


def _level_label(ontology: MiroOntology, level_id: str | None, *, with_symbol: bool = True) -> str:
    if not level_id:
        return "Не определён"
    name = f"{level_id} · {ontology.name(level_id)}"
    if with_symbol:
        return f"{_level_symbol(level_id)} {name}"
    return name


def _level_hint(ontology: MiroOntology, level_id: str) -> str:
    level = ontology.level(level_id)
    theme = (level.get("theme") or "").strip()
    if theme:
        return theme
    return LEVEL_FALLBACK_HINTS.get(level_id, "")


def _render_sidebar_legend(ontology: MiroOntology) -> None:
    rows = ['<div class="legend-title">Слои Миросложения</div><div class="legend-list">']
    for level_id in ontology.levels_ids():
        color = ontology.color(level_id)
        symbol = _level_symbol(level_id)
        name = ontology.name(level_id)
        hint = _level_hint(ontology, level_id)
        rows.append(
            '<div class="legend-item">'
            f'<div class="legend-glyph" style="background:{color}">{symbol}</div>'
            '<div class="legend-body">'
            f"<strong>{level_id} · {name}</strong>"
            f"<span>{hint}</span>"
            "</div></div>"
        )
    rows.append("</div>")
    st.markdown("".join(rows), unsafe_allow_html=True)


def _render_symbol_key(ontology: MiroOntology) -> None:
    pills = []
    for level_id in ontology.levels_ids():
        color = ontology.color(level_id)
        symbol = _level_symbol(level_id)
        pills.append(
            f'<span class="symbol-pill"><i style="background:{color}">{symbol}</i>'
            f"{level_id}</span>"
        )
    st.markdown(f'<div class="symbol-key">{"".join(pills)}</div>', unsafe_allow_html=True)


def _render_spectrum(spectrum: dict[str, float], ontology: MiroOntology) -> None:
    rows: list[str] = ['<div class="spectrum-block">']
    for level_id in ontology.levels_ids():
        value = float(spectrum.get(level_id, 0.0))
        color = ontology.color(level_id)
        symbol = _level_symbol(level_id)
        rows.append(
            '<div class="spectrum-row">'
            '<div class="spectrum-label">'
            f'<span class="left"><span class="glyph" style="background:{color}">{symbol}</span>'
            f"{level_id} · {ontology.name(level_id)}</span>"
            f'<span class="pct">{value * 100:.1f}%</span>'
            "</div>"
            '<div class="spectrum-track">'
            f'<div class="spectrum-fill" style="width:{value * 100:.2f}%;'
            f'background:{color}"></div>'
            "</div></div>"
        )
    rows.append("</div>")
    st.markdown("".join(rows), unsafe_allow_html=True)


def _render_level_ribbon(ontology: MiroOntology) -> None:
    chips = "".join(
        f'<span style="background:{ontology.color(level_id)}"></span>'
        for level_id in ontology.levels_ids()
    )
    st.markdown(f'<div class="miro-ribbon">{chips}</div>', unsafe_allow_html=True)


def _render_summary(result: dict[str, Any], ontology: MiroOntology) -> None:
    work = result["work"]
    dominant = work.get("dominant_level")
    level = ontology.level(dominant) if dominant else {}
    color = ontology.color(dominant) if dominant else "#5d6878"
    symbol = _level_symbol(dominant)
    columns = st.columns([1.35, 1, 1, 1])
    columns[0].metric("Доминирующий уровень", _level_label(ontology, dominant))
    columns[1].metric("Предложений", len(result.get("sentences", [])))
    columns[2].metric("Глав", len(result.get("chapters", [])))
    active_levels = sum(1 for value in work.get("spectrum", {}).values() if value > 0)
    columns[3].metric("Проявленных уровней", active_levels)

    theme_text = level.get("theme") or "В тексте недостаточно совпадений для определения уровня."
    st.markdown(
        '<div class="level-card">'
        '<div class="level-head">'
        f'<span class="glyph" style="background:{color}">{symbol}</span>'
        f"<h3>{_level_label(ontology, dominant, with_symbol=False)}</h3>"
        "</div>"
        f"<p>{theme_text}</p>"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_sentence_details(result: dict[str, Any], ontology: MiroOntology) -> None:
    sentences = result.get("sentences", [])
    if not sentences:
        st.info("В тексте не найдено предложений для анализа.")
        return
    for sentence in sentences:
        dominant = sentence.get("dominant_level")
        label = _level_label(ontology, dominant)
        with st.expander(f"{sentence['index'] + 1}. {label} — {sentence['text'][:90]}"):
            st.write(sentence["text"])
            _render_spectrum(sentence.get("levels", {}), ontology)


def _render_downloads(
    result: dict[str, Any],
    text: str,
    title: str,
    exporter: MiroExporter,
) -> None:
    safe_title = title.strip() or "miro_result"
    json_text = json.dumps(result, ensure_ascii=False, indent=2)
    csv_text = exporter.to_csv(result)
    html_text = exporter.to_html(result, text=text, title=safe_title)
    col_json, col_csv, col_html = st.columns(3)
    col_json.download_button(
        "Скачать JSON",
        data=json_text,
        file_name=f"{safe_title}.json",
        mime="application/json",
        use_container_width=True,
    )
    col_csv.download_button(
        "Скачать CSV",
        data=csv_text.encode("utf-8-sig"),
        file_name=f"{safe_title}.csv",
        mime="text/csv",
        use_container_width=True,
    )
    col_html.download_button(
        "Скачать HTML",
        data=html_text,
        file_name=f"{safe_title}.html",
        mime="text/html",
        use_container_width=True,
    )


def _build_graph_html(
    result: dict[str, Any],
    ontology: MiroOntology,
) -> tuple[str, dict[str, Any]]:
    graph_exporter = MiroGraphifyExporter(ontology=ontology)
    with NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as file:
        output_path = Path(file.name)
    try:
        stats = graph_exporter.write_graph_text(result, output_path, ontology=ontology)
        return output_path.read_text(encoding="utf-8"), stats
    finally:
        output_path.unlink(missing_ok=True)


def _render_hero(ontology: MiroOntology | None = None) -> None:
    if ontology is None:
        chips = [
            ("L1", "Красный", "#E53935"),
            ("L2", "Оранжевый", "#FB8C00"),
            ("L3", "Жёлтый", "#FDD835"),
            ("L4", "Зелёный", "#43A047"),
            ("L5", "Голубой", "#1E88E5"),
            ("L6", "Синий", "#3949AB"),
            ("L7", "Фиолетовый", "#8E24AA"),
        ]
    else:
        chips = [
            (lid, ontology.name(lid), ontology.color(lid))
            for lid in ontology.levels_ids()
        ]

    chip_html = "".join(
        f'<span class="hero-chip">'
        f'<span class="hero-glyph">{_level_symbol(lid)}</span>'
        f'<span class="hero-dot" style="background:{color}"></span>'
        f"{lid} {name}</span>"
        for lid, name, color in chips
    )
    st.markdown(
        f"""
        <section class="hero">
          <h1>МироВизор</h1>
          <p>
            Исследуйте смысловой спектр текста по семи уровням Миросложения —
            от основы и жизненной динамики к гармонии, связи, глубине и целостности.
          </p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_empty_state(ontology: MiroOntology | None = None) -> None:
    if ontology is None:
        items = [
            ("L1", "#E53935"),
            ("L2", "#FB8C00"),
            ("L3", "#FDD835"),
            ("L4", "#43A047"),
            ("L5", "#1E88E5"),
            ("L6", "#3949AB"),
            ("L7", "#8E24AA"),
        ]
    else:
        items = [(lid, ontology.color(lid)) for lid in ontology.levels_ids()]

    glyphs = "".join(
        f'<span style="background:{color}">{_level_symbol(lid)}</span>'
        for lid, color in items
    )
    st.markdown(
        f"""
        <div class="empty-state">
          <div class="empty-glyphs">{glyphs}</div>
          <strong>Готово к анализу</strong>
          <span>Вставьте текст или загрузите файл — появится спектр семи уровней
          Миросложения, цветная разметка и доминирующий смысловой слой.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def run() -> None:
    st.set_page_config(page_title="МироВизор", page_icon="🌈", layout="wide")

    st.session_state.setdefault("input_text", DEFAULT_TEXT)
    st.session_state.setdefault("document_title", "Новый анализ")
    st.session_state.setdefault("analysis_result", None)
    st.session_state.setdefault("ui_theme", "Светлая")

    theme = st.session_state.get("ui_theme", "Светлая")
    _apply_styles(theme)

    # Базовая легенда/герой до анализа — на русском пакете онтологии.
    try:
        base_ontology = MiroOntology.from_package(language="ru")
    except FileNotFoundError:
        base_ontology = None

    _render_hero(base_ontology)

    with st.sidebar:
        st.header("Параметры")
        theme_choice = st.radio(
            "Тема интерфейса",
            options=["Светлая", "Тёмная"],
            horizontal=True,
            key="ui_theme",
        )
        # Если пользователь сменил тему на этом прогоне — стили уже применены
        # с предыдущим session_state, поэтому перезапускаем сразу.
        if theme_choice != theme:
            st.rerun()

        language_mode = st.selectbox(
            "Язык текста",
            options=["auto", "ru", "en"],
            format_func=lambda value: {
                "auto": "Определить автоматически",
                "ru": "Русский",
                "en": "English",
            }[value],
        )
        use_embeddings = st.checkbox(
            "Расширенный семантический анализ",
            value=False,
            help="Использует sentence-transformers, если модель установлена. Первый запуск может быть долгим.",
        )
        st.divider()
        if base_ontology is not None:
            _render_sidebar_legend(base_ontology)
        else:
            st.caption("Онтология не найдена — легенда уровней недоступна.")
        st.divider()
        st.caption("Быстрый режим работает локально и не требует загрузки моделей.")
        if st.button("Очистить результат", use_container_width=True):
            st.session_state["analysis_result"] = None
            st.session_state.pop("graph_html", None)
            st.session_state.pop("graph_stats", None)

    tab_analysis, tab_sentences, tab_export, tab_graph = st.tabs(
        ["🔎 Анализ", "📚 Предложения", "📥 Экспорт", "🕸️ Карта текста"]
    )

    with tab_analysis:
        uploaded_file = st.file_uploader(
            "Загрузить текстовый файл",
            type=["txt", "md"],
            help="UTF-8, ANSI (Windows-1251), UTF-16 LE/BE — кодировка определяется автоматически.",
        )
        _load_uploaded_text(uploaded_file)
        st.text_input("Название", key="document_title")
        st.text_area(
            "Текст для анализа",
            key="input_text",
            height=300,
            placeholder="Вставьте сюда текст или загрузите файл…",
        )

        if st.button("Анализировать текст", type="primary", use_container_width=True):
            text = st.session_state["input_text"].strip()
            if not text:
                st.warning("Добавьте текст для анализа.")
            else:
                language = detect_language(text) if language_mode == "auto" else language_mode
                try:
                    with st.spinner("Определяю смысловой спектр…"):
                        marker = _build_marker(language, use_embeddings)
                        result = marker.mark_text(text, title=st.session_state["document_title"])
                    st.session_state["analysis_result"] = result
                    st.session_state["analysis_text"] = text
                    st.session_state["analysis_title"] = st.session_state["document_title"]
                    st.session_state["analysis_language"] = language
                    st.session_state.pop("graph_html", None)
                    st.session_state.pop("graph_stats", None)
                except Exception as exc:
                    st.error(f"Не удалось выполнить анализ: {exc}")

        result = st.session_state.get("analysis_result")
        if result:
            language = st.session_state.get("analysis_language", "ru")
            ontology = MiroOntology.from_package(language=language)
            exporter = MiroExporter(ontology=ontology)
            st.success(f"Анализ завершён · язык: {language.upper()}")
            _render_summary(result, ontology)
            st.subheader("Смысловой спектр")
            st.caption("Доля каждого уровня Миросложения во всём тексте.")
            _render_spectrum(result["work"].get("spectrum", {}), ontology)
            st.subheader("Цветная разметка")
            st.caption("Слова подсвечены цветом найденного уровня.")
            html_text = exporter.to_html(
                result,
                text=st.session_state["analysis_text"],
                title=st.session_state["analysis_title"],
            )
            st.iframe(html_text, height=480)
        else:
            _render_empty_state(base_ontology)

    with tab_sentences:
        result = st.session_state.get("analysis_result")
        if result:
            ontology = MiroOntology.from_package(
                language=st.session_state.get("analysis_language", "ru")
            )
            st.subheader("Разбор по предложениям")
            st.caption("Откройте предложение, чтобы увидеть распределение всех уровней.")
            _render_symbol_key(ontology)
            _render_sentence_details(result, ontology)
        else:
            st.info("Сначала выполните анализ текста во вкладке «Анализ».")

    with tab_export:
        result = st.session_state.get("analysis_result")
        if result:
            ontology = MiroOntology.from_package(
                language=st.session_state.get("analysis_language", "ru")
            )
            exporter = MiroExporter(ontology=ontology)
            st.subheader("Скачать результаты")
            st.write("JSON — полные данные, CSV — таблица предложений, HTML — готовый цветной отчёт.")
            _render_downloads(
                result,
                st.session_state["analysis_text"],
                st.session_state["analysis_title"],
                exporter,
            )
            with st.expander("Показать технические данные JSON"):
                st.json(result, expanded=False)
        else:
            st.info("Сначала выполните анализ текста во вкладке «Анализ».")

    with tab_graph:
        result = st.session_state.get("analysis_result")
        if not result:
            st.info("Сначала выполните анализ текста во вкладке «Анализ».")
        else:
            ontology = MiroOntology.from_package(
                language=st.session_state.get("analysis_language", "ru")
            )
            st.subheader("Интерактивная карта текста")
            st.caption("Карта связывает главы, предложения и обнаруженные уровни.")
            if st.button("Построить карту", type="primary"):
                try:
                    with st.spinner("Строю карту связей…"):
                        graph_html, graph_stats = _build_graph_html(result, ontology)
                    st.session_state["graph_html"] = graph_html
                    st.session_state["graph_stats"] = graph_stats
                except Exception as exc:
                    st.error(f"Не удалось построить карту: {exc}")

            graph_html = st.session_state.get("graph_html")
            graph_stats = st.session_state.get("graph_stats")
            if graph_html and graph_stats:
                col1, col2, col3 = st.columns(3)
                col1.metric("Узлов", graph_stats.get("nodes", 0))
                col2.metric("Связей", graph_stats.get("edges", 0))
                col3.metric("Сообществ", graph_stats.get("communities", 0))
                st.iframe(graph_html, height=650)
                st.download_button(
                    "Скачать карту HTML",
                    data=graph_html,
                    file_name="miro_text_map.html",
                    mime="text/html",
                )


def main() -> None:
    """Запустить пользовательскую панель через Streamlit runtime."""
    app_path = Path(__file__).resolve()
    command = [sys.executable, "-m", "streamlit", "run", str(app_path), *sys.argv[1:]]
    raise SystemExit(subprocess.call(command))


if __name__ == "__main__":
    run()

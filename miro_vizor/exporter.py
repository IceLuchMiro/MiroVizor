"""Экспорт разметки в JSON, CSV и HTML."""
from __future__ import annotations

import csv
import html
import json
from io import StringIO
from pathlib import Path
from typing import Any

from .ontology import MiroOntology

# ── Символы уровней Миросложения ──────────────────────────────────────
_LEVEL_SYMBOLS: dict[str, str] = {
    "L1": "\u2b21",   # ⬡  структура
    "L2": "\u223f",   # ∿  динамика
    "L3": "\u2726",   # ✦  воля
    "L4": "\u2756",   # ❖  гармония
    "L5": "\u25ce",   # ◎  коммуникация
    "L6": "\u2736",   # ✶  паттерны
    "L7": "\u25c9",   # ◉  целостность
}


def _symbol(level: str) -> str:
    """Вернуть символ для уровня или точку."""
    return _LEVEL_SYMBOLS.get(level, "\u2022")  # •


# ── Стили HTML-отчёта (разбиты на блоки) ──────────────────────────────
_CSS_BLOCKS: list[str] = [
    # --- база ---
    (
        "@import url('https://fonts.googleapis.com/css2"
        "?family=Manrope:wght@400;600;700&display=swap');\n"
        "* { box-sizing: border-box; margin: 0; padding: 0; }\n"
        "body {\n"
        "  font-family: 'Manrope', system-ui, -apple-system, sans-serif;\n"
        "  font-size: 17px;\n"
        "  max-width: 920px;\n"
        "  margin: 0 auto;\n"
        "  padding: 2.5em 1.5em;\n"
        "  line-height: 1.75;\n"
        "  color: #1a2233;\n"
        "  background: linear-gradient(135deg,"
        " #faf8f5 0%, #f0ece4 50%, #e8e4dc 100%);\n"
        "  min-height: 100vh;\n"
        "}\n"
        ".container { position: relative; z-index: 1; }\n"
    ),
    # --- фоновые слои L1–L7 ---
    (
        ".bg-layer {\n"
        "  position: fixed;\n"
        "  border-radius: 50%;\n"
        "  opacity: 0.06;\n"
        "  z-index: 0;\n"
        "  pointer-events: none;\n"
        "}\n"
        ".bg-layer-1 { width:500px;height:500px;"
        " background:radial-gradient(circle,#e74c3c,transparent 70%);"
        " top:-120px;left:-80px; }\n"
        ".bg-layer-2 { width:420px;height:420px;"
        " background:radial-gradient(circle,#e67e22,transparent 70%);"
        " top:60px;right:-60px; }\n"
        ".bg-layer-3 { width:380px;height:380px;"
        " background:radial-gradient(circle,#f39c12,transparent 70%);"
        " bottom:15%;left:-40px; }\n"
        ".bg-layer-4 { width:340px;height:340px;"
        " background:radial-gradient(circle,#27ae60,transparent 70%);"
        " bottom:-60px;right:10%; }\n"
        ".bg-layer-5 { width:300px;height:300px;"
        " background:radial-gradient(circle,#2980b9,transparent 70%);"
        " top:35%;right:-30px; }\n"
        ".bg-layer-6 { width:260px;height:260px;"
        " background:radial-gradient(circle,#8e44ad,transparent 70%);"
        " bottom:45%;left:25%; }\n"
        ".bg-layer-7 { width:220px;height:220px;"
        " background:radial-gradient(circle,#9b59b6,transparent 70%);"
        " top:55%;left:55%; }\n"
    ),
    # --- заголовки ---
    (
        "h1 {\n"
        "  font-size: 1.1em;\n"
        "  font-weight: 700;\n"
        "  letter-spacing: -0.02em;\n"
        "  margin-bottom: 0.3em;\n"
        "  background: linear-gradient(135deg,"
        " #e74c3c,#e67e22,#f39c12,#27ae60,#2980b9,#8e44ad,#9b59b6);\n"
        "  -webkit-background-clip: text;\n"
        "  -webkit-text-fill-color: transparent;\n"
        "  background-clip: text;\n"
        "}\n"
        "h2 { font-size:1.35em;font-weight:600;margin-top:1.6em;margin-bottom:.5em; }\n"
    ),
    # --- доминирующий уровень ---
    (
        ".dominant-card {\n"
        "  background: transparent;\n"
        "  border: none;\n"
        "  border-radius: 0;\n"
        "  padding: 1.4em 0;\n"
        "  margin: 1em 0;\n"
        "  box-shadow: none;\n"
        "  display: flex;\n"
        "  align-items: center;\n"
        "  gap: 1em;\n"
        "}\n"
        ".dominant-symbol {\n"
        "  font-size: 2.6em;\n"
        "  line-height: 1;\n"
        "}\n"
        ".dominant-info strong { font-size: 1.15em; }\n"
        ".dominant-info .level-name { color:var(--dom-color,#9b59b6);font-weight:700; }\n"
    ),
    # --- легенда уровней ---
    (
        ".legend {\n"
        "  display: flex;\n"
        "  flex-wrap: wrap;\n"
        "  gap: 0.5em;\n"
        "  margin: 1.2em 0;\n"
        "}\n"
        ".legend-item {\n"
        "  display: inline-flex;\n"
        "  align-items: center;\n"
        "  gap: 0.35em;\n"
        "  padding: 0.35em 0.75em;\n"
        "  border-radius: 999px;\n"
        "  color: #fff;\n"
        "  font-size: 0.85em;\n"
        "  font-weight: 600;\n"
        "  white-space: nowrap;\n"
        "  box-shadow: 0 2px 8px rgba(0,0,0,0.12);\n"
        "}\n"
        ".legend-symbol { font-size: 1.1em; }\n"
    ),
    # --- полоса спектра + ключ-полоска символов ---
    (
        ".work-bar {\n"
        "  display: flex;\n"
        "  height: 28px;\n"
        "  border-radius: 99px;\n"
        "  overflow: hidden;\n"
        "  margin: 1.2em 0;\n"
        "  box-shadow: 0 2px 12px rgba(0,0,0,0.08);\n"
        "}\n"
        ".bar-segment { height:100%; transition:min-width .2s; }\n"
        ".key-strip {\n"
        "  display: flex;\n"
        "  justify-content: center;\n"
        "  gap: 1.2em;\n"
        "  margin: 2em 0 1.5em;\n"
        "  opacity: 0.22;\n"
        "}\n"
        ".key-char {\n"
        "  font-size: 1.8em;\n"
        "  filter: drop-shadow(0 0 3px currentColor);\n"
        "}\n"
    ),
    # --- токены ---
    (
        ".token {\n"
        "  padding: .08em .2em;\n"
        "  border-radius: 5px;\n"
        "  cursor: help;\n"
        "  transition: background-color .15s;\n"
        "}\n"
        ".token:hover { background-color: inherit !important; }\n"
    ),
    # --- карточки предложений ---
    (
        ".sent-card {\n"
        "  background: transparent;\n"
        "  border: none;\n"
        "  border-radius: 0;\n"
        "  padding: 0;\n"
        "  margin: 0.2em 0;\n"
        "}\n"
        ".sent-header {\n"
        "  display: flex;\n"
        "  justify-content: space-between;\n"
        "  align-items: center;\n"
        "  margin-bottom: .5em;\n"
        "  font-size: .88em;\n"
        "  color: #666;\n"
        "}\n"
        ".sent-level-badge {\n"
        "  font-size: .95em;\n"
        "  font-weight: 700;\n"
        "  padding: .15em .6em;\n"
        "  border-radius: 6px;\n"
        "  color: #fff;\n"
        "}\n"
        ".muted { color: #888; }\n"
    ),
    # --- футер ---
    ".footer-note {\n"
    "  text-align: center;\n"
    "  color: #aaa;\n"
    "  font-size: .82em;\n"
    "  margin-top: 3em;\n"
    "  padding-top: 1.5em;\n"
    "  border-top: 1px solid rgba(0,0,0,0.06);\n"
    "}\n",
    # --- график уровней ---
    (
        ".chart-section {\n"
        "  width: 100%;\n"
        "  margin: 2em 0;\n"
        "  overflow: hidden;\n"
        "}\n"
        ".chart-title {\n"
        "  margin: 1.4em 0 .35em;\n"
        "  font-size: 1.05em;\n"
        "  font-weight: 700;\n"
        "  color: #1a2233;\n"
        "}\n"
        ".chart-box {\n"
        "  width: 100%;\n"
        "  min-height: 520px;\n"
        "  border: 1px solid rgba(26,34,51,0.18);\n"
        "  border-radius: 10px;\n"
        "  background: rgba(255,255,255,0.28);\n"
        "  overflow: hidden;\n"
        "}\n"
        "#miro-chart, #miro-spectrum-chart, #miro-token-chart {\n"
        "  width: 100%;\n"
        "  min-height: 520px;\n"
        "}\n"
    ),
]


def _html_style() -> str:
    """Собрать все CSS-блоки в одну строку."""
    return "\n".join(_CSS_BLOCKS)


# ── Экспортёр ──────────────────────────────────────────────────────────

class MiroExporter:
    """Сериализация результата маркировки в разные форматы."""

    def __init__(self, ontology: MiroOntology | None = None) -> None:
        self.ontology = ontology or MiroOntology.from_package()

    # ── JSON ───────────────────────────────────────────────────────

    def to_json(self, result: dict[str, Any]) -> str:
        return json.dumps(result, ensure_ascii=False, indent=2)

    def write_json(self, result: dict[str, Any], path: str | Path) -> None:
        Path(path).write_text(self.to_json(result), encoding="utf-8")

    # ── CSV ────────────────────────────────────────────────────────

    def to_csv(self, result: dict[str, Any]) -> str:
        """CSV: одна строка на предложение со спектром L1–L7."""
        buffer = StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        header = ["index", "chapter", "text", "dominant_level"] \
            + self.ontology.levels_ids()
        writer.writerow(header)
        for ch in result.get("chapters", []):
            ch_index = ch.get("index", 0)
            for sent in ch.get("sentences", []):
                spectrum = sent.get("levels", {})
                row = [
                    sent.get("index", ""),
                    ch_index,
                    sent.get("text", "").replace("\n", " "),
                    sent.get("dominant_level", ""),
                ] + [
                    round(spectrum.get(level, 0.0), 4)
                    for level in self.ontology.levels_ids()
                ]
                writer.writerow(row)
        return buffer.getvalue()

    def write_csv(self, result: dict[str, Any], path: str | Path) -> None:
        Path(path).write_text(
            self.to_csv(result), encoding="utf-8-sig",
        )

    # ── HTML ───────────────────────────────────────────────────────

    def to_html(
        self,
        result: dict[str, Any],
        text: str | None = None,
        title: str = "Маркировка Миросложения",
    ) -> str:
        """Цветная HTML-разметка текста по токенам."""
        sentences = result.get("sentences", [])
        spectrum = result.get("work", {}).get("spectrum", {})
        dominant = result.get("work", {}).get("dominant_level")

        levels_ids = self.ontology.levels_ids()
        colors = {lvl: self.ontology.color(lvl) for lvl in levels_ids}
        names = {lvl: self.ontology.name(lvl) for lvl in levels_ids}
        dom_color = colors.get(dominant or "", "#9b59b6")

        parts: list[str] = []

        # ── head ──
        parts.extend([
            "<!DOCTYPE html>\n<html lang=\"ru\">\n<head>\n",
            '<meta charset="UTF-8">\n',
            '<meta name="viewport" content="width=device-width,'
            ' initial-scale=1.0">\n',
            f"<title>{html.escape(title)}</title>\n",
            f"<style>\n{_html_style()}</style>\n</head>\n<body>\n",
        ])

        # ── фоновые слои L1–L7 ──
        for i in range(1, 8):
            parts.append(f'<div class="bg-layer bg-layer-{i}"></div>\n')

        parts.append('<div class="container">\n')
        parts.append(f"<h1>{html.escape(title)}</h1>\n")

        # ── доминирующий уровень ──
        if dominant and dominant in names:
            sym = _symbol(dominant)
            parts.append(
                f'<div class="dominant-card" style="--dom-color:{dom_color};">\n'
                f'  <span class="dominant-symbol">{sym}</span>\n'
                f'  <div class="dominant-info">\n'
                f'    <strong>Доминирующий уровень:</strong> '
                f'<span class="level-name">'
                f'{dominant} \u2014 {html.escape(names[dominant])}'
                f'</span>\n'
                f'  </div>\n'
                f'</div>\n'
            )

        # ── график уровней по предложениям ──
        chart_html = self._render_chart(
            result, levels_ids, colors, names, source_text=text,
        )
        if chart_html:
            parts.append(chart_html)

        # ── текстовая разметка ──
        if text is not None:
            parts.append(self._render_text_rich(text, sentences, colors))
        else:
            parts.append(
                "<p><em>Исходный текст не передан"
                " \u2014 цветная разметка недоступна.</em></p>\n",
            )

        # ── футер ──
        parts.append(
            '<div class="footer-note">'
            'Отчёт создан системой MiroVizor '
            '\u2022 Миросложение \u2014 метод анализа текста'
            ' по семи уровням смысла\n</div>\n',
        )
        parts.append("</div>\n</body>\n</html>")
        return "".join(parts)

    # ── рендер текста (карточки предложений) ─────────────────────────

    def _render_text_rich(
        self,
        text: str,
        sentences: list[dict[str, Any]],
        colors: dict[str, str],
    ) -> str:
        if not sentences:
            return f"<p>{html.escape(text)}</p>\n"

        # Карта токенов и предложений
        token_map: dict[tuple[int, int], tuple[str, int]] = {}
        sent_map: dict[int, dict[str, Any]] = {}
        for idx, sent in enumerate(sentences):
            si = sent.get("index", idx)
            sent_map[si] = sent
            for token in sent.get("tokens", []):
                level = token.get("level")
                if not level:
                    continue
                token_map[(token["start"], token["end"])] = (level, si)

        sorted_spans = sorted(token_map.items(), key=lambda x: x[0][0])

        # Группировка по предложениям
        sent_spans: dict[int, list] = {si: [] for si in sent_map}
        for (start, end), (level, si) in sorted_spans:
            if 0 <= start < end <= len(text):
                sent_spans[si].append((start, end, level))

        parts: list[str] = []
        pos = 0

        for si in sorted(sent_spans.keys()):
            spans = sorted(sent_spans[si], key=lambda x: x[0])
            if not spans:
                continue

            sent = sent_map.get(si, {})
            dom_lvl = sent.get("dominant_level", "?")
            sym = _symbol(dom_lvl)
            c = colors.get(dom_lvl, "#888")

            first_start = spans[0][0]
            last_end = spans[-1][1]

            # Текст между предложениями
            if first_start > pos:
                parts.append(
                    f'<p class="muted">'
                    f"{html.escape(text[pos:first_start].strip())}"
                    f"</p>\n",
                )
            elif first_start < pos:
                continue

            # Карточка предложения
            parts.append(
                f'<div class="sent-card">\n'
                f'  <div class="sent-header">\n'
                f'    <span>Предложение #{si + 1}</span>\n'
                f'    <span class="sent-level-badge"'
                f' style="background:{c}">'
                f"{sym} {dom_lvl}</span>\n"
                f"  </div>\n"
                f'  <div style="font-size:1.02em;">\n',
            )

            sp = first_start
            for start, end, level in spans:
                if start > sp:
                    parts.append(html.escape(text[sp:start]))
                word = text[start:end]
                c_tok = colors.get(level, "#888")
                tok_sym = _symbol(level)
                parts.append(
                    f'<span class="token"'
                    f' style="background-color:{c_tok}22;'
                    f' border-bottom:2px solid {c_tok};"'
                    f' title="{tok_sym} {level}">'
                    f"{html.escape(word)}</span>",
                )
                sp = end
            if sp < last_end and sp < len(text):
                parts.append(html.escape(text[sp:last_end]))

            parts.append("\n  </div>\n</div>\n")
            pos = last_end

        # Хвост
        if pos < len(text):
            tail = text[pos:].strip()
            if tail:
                parts.append(f'<p class="muted">{html.escape(tail)}</p>\n')

        return "".join(parts)

    # ── рендер текста (простой, для обратной совместимости) ──────────

    def _render_text(
        self,
        text: str,
        sentences: list[dict[str, Any]],
        colors: dict[str, str],
    ) -> str:
        """Покрыть исходный текст span-токенами с цветами уровней."""
        if not sentences:
            return f"<p>{html.escape(text)}</p>\n"

        token_map: dict[tuple[int, int], str] = {}
        for sent in sentences:
            for token in sent.get("tokens", []):
                level = token.get("level")
                if not level:
                    continue
                token_map[(token["start"], token["end"])] = level

        sorted_spans = sorted(token_map.items(), key=lambda x: x[0][0])
        parts: list[str] = ["<p>"]
        pos = 0
        for (start, end), level in sorted_spans:
            if start < pos:
                continue
            if start > pos:
                parts.append(html.escape(text[pos:start]))
            word = text[start:end]
            parts.append(
                f'<span class="token"'
                f' style="background-color:{colors[level]}33;'
                f' border-bottom:2px solid {colors[level]};"'
                f' title="{level}">'
                f"{html.escape(word)}</span>",
            )
            pos = end
        if pos < len(text):
            parts.append(html.escape(text[pos:]))
        parts.append("</p>\n")
        return "".join(parts)

    # ── график уровней по предложениям (Plotly) ───────────────────────

    def _render_chart(
        self,
        result: dict[str, Any],
        levels_ids: list[str],
        colors: dict[str, str],
        names: dict[str, str],
        source_text: str | None = None,
    ) -> str:
        """Интерактивные графики на масштабах от слова до книги."""
        sentences = result.get("sentences", [])
        if not sentences:
            return ""

        # Номер уровня берём из порядка онтологии, а не из второго символа
        # идентификатора: это поддерживает и расширенные ID вроде L10.
        level_num = {lvl: index + 1 for index, lvl in enumerate(levels_ids)}

        def best_level(values: dict[str, Any]) -> str | None:
            valid = {
                level: float(values.get(level, 0.0) or 0.0)
                for level in levels_ids
            }
            return max(valid, key=valid.get) if max(valid.values(), default=0.0) > 0 else None

        traces: list[dict[str, Any]] = []
        for level in levels_ids:
            xs: list[int] = []
            ys: list[int] = []
            texts: list[str] = []
            for sent in sentences:
                if sent.get("dominant_level") != level:
                    continue
                si = sent.get("index", 0) + 1
                xs.append(si)
                ys.append(level_num[level])
                sentence_text = sent.get("text", "").replace("\n", " ").strip()
                texts.append(
                    f"Предложение {si}<br>"
                    f"{html.escape(sentence_text)}<br>"
                    f"Уровень: {level} — {html.escape(names[level])}"
                )
            if not xs:
                continue
            traces.append({
                "x": xs,
                "y": ys,
                "text": texts,
                "mode": "markers",
                "name": f"{level} — {names[level]}",
                "marker": {
                    "size": 14,
                    "color": colors[level],
                    "opacity": 0.9,
                    "line": {"width": 1, "color": "#ffffff"},
                },
                "hovertemplate": "%{text}<extra></extra>",
            })

        # Непрерывная траектория доминирующих уровней. Отрезок окрашен
        # цветом уровня точки выхода, поэтому виден и переход L1 -> L2.
        dominant_points: list[dict[str, Any]] = []
        for sent in sentences:
            level = sent.get("dominant_level") or best_level(sent.get("levels", {}))
            if level in level_num:
                dominant_points.append({
                    "x": sent.get("index", 0) + 1,
                    "y": level_num[level],
                    "level": level,
                    "text": sent.get("text", "").replace("\\n", " ").strip(),
                })
        dominant_line_traces: list[dict[str, Any]] = []
        for previous, current in zip(dominant_points, dominant_points[1:]):
            dominant_line_traces.append({
                "x": [previous["x"], current["x"]],
                "y": [previous["y"], current["y"]],
                "mode": "lines",
                "line": {"color": colors[current["level"]], "width": 3},
                "hoverinfo": "skip",
                "showlegend": False,
            })
        traces = dominant_line_traces + traces

        # Второй режим: полный спектр каждого предложения.
        # Размер и прозрачность точки отражают силу уровня в предложении.
        spectrum_traces: list[dict[str, Any]] = []
        for level in levels_ids:
            xs: list[int] = []
            ys: list[int] = []
            sizes: list[float] = []
            opacities: list[float] = []
            texts: list[str] = []
            for sent in sentences:
                si = sent.get("index", 0) + 1
                value = float(sent.get("levels", {}).get(level, 0.0) or 0.0)
                if value <= 0:
                    continue
                xs.append(si)
                ys.append(level_num[level])
                sizes.append(8 + min(26, value * 18))
                opacities.append(min(0.95, 0.28 + value * 0.7))
                sentence_text = sent.get("text", "").replace("\n", " ").strip()
                texts.append(
                    f"Предложение {si}<br>"
                    f"{html.escape(sentence_text)}<br>"
                    f"{level} — {html.escape(names[level])}: {value:.3f}"
                )
            if xs:
                spectrum_traces.append({
                    "x": xs,
                    "y": ys,
                    "text": texts,
                    "mode": "lines+markers",
                    "name": f"{level} — {names[level]}",
                    "line": {
                        "color": colors[level],
                        "width": 2.5,
                        "shape": "linear",
                    },
                    "connectgaps": False,
                    "marker": {
                        "size": sizes,
                        "color": colors[level],
                        "opacity": opacities,
                        "line": {"width": 1, "color": "#ffffff"},
                    },
                    "hovertemplate": "%{text}<extra></extra>",
                    "showlegend": False,
                })

        # Точки для разных масштабов: слово, предложение, абзац, глава, книга.
        # Если у токена нет level, используем самый сильный score.
        def best_level(values: dict[str, Any]) -> str | None:
            valid = {
                level: float(values.get(level, 0.0) or 0.0)
                for level in levels_ids
            }
            return max(valid, key=valid.get) if max(valid.values(), default=0.0) > 0 else None

        token_points: list[dict[str, Any]] = []
        for sent in sentences:
            sentence_index = sent.get("index", 0) + 1
            for token in sent.get("tokens", []):
                level = token.get("level") or best_level(token.get("scores", {}))
                if level not in level_num:
                    continue
                token_points.append({
                    "level": level,
                    "sentence": sentence_index,
                    "word": str(token.get("text", "")),
                })

        scale_points: dict[str, list[dict[str, Any]]] = {"word": []}
        for number, point in enumerate(token_points, start=1):
            scale_points["word"].append({"x": number, **point})

        sentence_points: list[dict[str, Any]] = []
        for sent in sentences:
            level = sent.get("dominant_level") or best_level(sent.get("levels", {}))
            if level in level_num:
                sentence_points.append({
                    "x": len(sentence_points) + 1,
                    "level": level,
                    "word": sent.get("text", "").replace("\n", " ").strip(),
                    "sentence": sent.get("index", 0) + 1,
                })
        scale_points["sentence"] = sentence_points

        paragraph_groups: dict[int, list[dict[str, Any]]] = {}
        chapter_groups: dict[int, list[dict[str, Any]]] = {}
        for sent in sentences:
            level = sent.get("dominant_level") or best_level(sent.get("levels", {}))
            if level not in level_num:
                continue
            start = int(sent.get("start", 0))
            paragraph = (source_text or "")[:start].count("\n\n") + 1
            paragraph_groups.setdefault(paragraph, []).append({"level": level, "sent": sent})
            chapter = next(
                (int(ch.get("index", 0)) for ch in result.get("chapters", [])
                 if any(s is sent or s.get("index") == sent.get("index")
                        for s in ch.get("sentences", []))),
                1,
            )
            chapter_groups.setdefault(chapter, []).append({"level": level, "sent": sent})

        def grouped_points(groups: dict[int, list[dict[str, Any]]]) -> list[dict[str, Any]]:
            points: list[dict[str, Any]] = []
            for x, items in sorted(groups.items()):
                counts: dict[str, int] = {}
                for item in items:
                    counts[item["level"]] = counts.get(item["level"], 0) + 1
                level = max(counts, key=counts.get)
                points.append({
                    "x": len(points) + 1,
                    "level": level,
                    "word": " ".join(str(i["sent"].get("text", "")).strip() for i in items),
                    "sentence": items[0]["sent"].get("index", 0) + 1,
                })
            return points

        scale_points["paragraph"] = grouped_points(paragraph_groups)
        scale_points["chapter"] = grouped_points(chapter_groups)
        scale_points["book"] = grouped_points({1: [
            {"level": (result.get("work", {}).get("dominant_level")
                       or best_level(result.get("work", {}).get("spectrum", {}))
                       or levels_ids[0]),
             "sent": {"text": "Вся книга", "index": 0}},
        ]})

        # Один график с переключателем масштаба. Каждый отрезок
        # создаётся отдельным trace, поэтому его цвет точно соответствует
        # уровню точки выхода (второй точке отрезка).
        scale_labels = {
            "word": "Слово",
            "sentence": "Предложение",
            "paragraph": "Абзац",
            "chapter": "Глава",
            "book": "Книга",
        }
        token_traces: list[dict[str, Any]] = []
        token_trace_groups: dict[str, list[int]] = {}
        for scale, points in scale_points.items():
            group: list[int] = []
            if points:
                # Линия между каждой соседней парой, включая первую и вторую
                # точки. Нулевая длина отрезка допустима и не создаёт артефактов.
                for previous, current in zip(points, points[1:]):
                    group.append(len(token_traces))
                    token_traces.append({
                        "x": [previous["x"], current["x"]],
                        "y": [
                            level_num[previous["level"]],
                            level_num[current["level"]],
                        ],
                        "mode": "lines",
                        "line": {
                            "color": colors[current["level"]],
                            "width": 4,
                        },
                        "connectgaps": False,
                        "hoverinfo": "skip",
                        "showlegend": False,
                    })

                # Точки добавляются после линий, чтобы белая обводка была видна.
                group.append(len(token_traces))
                token_traces.append({
                    "x": [point["x"] for point in points],
                    "y": [level_num[point["level"]] for point in points],
                    "mode": "markers",
                    "name": scale_labels[scale],
                    "text": [
                        f"Масштаб: {scale_labels[scale]}<br>"
                        f"Позиция: {point['x']}<br>"
                        f"{html.escape(point['word'])}<br>"
                        f"Уровень: {point['level']} — "
                        f"{html.escape(names[point['level']])}"
                        for point in points
                    ],
                    "marker": {
                        "size": 13,
                        "color": [colors[point["level"]] for point in points],
                        "line": {"width": 2, "color": "#ffffff"},
                    },
                    "hovertemplate": "%{text}<extra></extra>",
                    "showlegend": False,
                })
            token_trace_groups[scale] = group

        if not traces and not spectrum_traces and not token_traces:
            return ""

        ytickvals = [level_num[lvl] for lvl in levels_ids]
        yticktext = [f"{lvl} — {names[lvl]}" for lvl in levels_ids]

        layout = {
            "title": {"text": "Доминирующий уровень по предложениям", "font": {"size": 16}},
            "xaxis": {
                "title": {"text": "Предложения", "font": {"size": 14}},
                "dtick": 1,
                "range": [0.5, max(1.5, len(sentences) + 0.5)],
                "showline": True,
                "linewidth": 2,
                "linecolor": "#1a2233",
                "ticks": "outside",
                "tickcolor": "#1a2233",
                "tickwidth": 1,
                "ticklen": 6,
                "gridcolor": "rgba(26,34,51,0.16)",
                "zeroline": False,
                "fixedrange": False,
            },
            "yaxis": {
                "title": {"text": "Уровни Миросложения", "font": {"size": 14}},
                "tickvals": ytickvals,
                "ticktext": yticktext,
                "range": [0.5, len(levels_ids) + 0.5],
                "showline": True,
                "linewidth": 2,
                "linecolor": "#1a2233",
                "ticks": "outside",
                "tickcolor": "#1a2233",
                "tickwidth": 1,
                "ticklen": 6,
                "gridcolor": "rgba(26,34,51,0.16)",
                "zeroline": False,
                "fixedrange": False,
            },
            "dragmode": "zoom",
            "margin": {"l": 130, "r": 30, "t": 60, "b": 70},
            "plot_bgcolor": "transparent",
            "paper_bgcolor": "transparent",
            "font": {
                "family": "Manrope, sans-serif",
                "size": 13,
                "color": "#1a2233",
            },
            "showlegend": True,
            "legend": {"orientation": "h", "y": -0.18},
        }
        spectrum_layout = dict(layout)
        spectrum_layout["title"] = {
            "text": "Полный спектр уровней по предложениям",
            "font": {"size": 16},
        }
        spectrum_layout["showlegend"] = False
        token_layout = dict(layout)
        token_layout["title"] = {
            "text": "Линейный график токенов Миросложения",
            "font": {"size": 16},
            "x": 0.03,
            "xanchor": "left",
            "y": 0.985,
            "yanchor": "top",
        }
        token_layout["showlegend"] = False
        # Оставляем отдельную строку под заголовок и отдельную строку
        # под кнопки масштаба, чтобы они не перекрывали друг друга.
        token_layout["margin"] = {"l": 130, "r": 30, "t": 125, "b": 70}
        if token_points:
            token_layout["xaxis"] = dict(layout["xaxis"])
            token_layout["xaxis"]["title"] = {
                "text": "Позиция выбранного масштаба",
                "font": {"size": 14},
            }
            token_layout["xaxis"]["dtick"] = max(1, len(token_points) // 20)
            token_layout["xaxis"]["range"] = [
                0.5, max(1.5, len(token_points) + 0.5),
            ]

        token_layout["updatemenus"] = [{
            "type": "buttons",
            "direction": "right",
            "x": 0,
            "y": 1.10,
            "xanchor": "left",
            "yanchor": "top",
            "pad": {"t": 4, "b": 4},
            "bgcolor": "rgba(255,255,255,0.72)",
            "bordercolor": "rgba(26,34,51,0.22)",
            "borderwidth": 1,
            "buttons": [],
        }]
        for scale, points in scale_points.items():
            visibility = [False] * len(token_traces)
            for trace_index in token_trace_groups.get(scale, []):
                visibility[trace_index] = True
            token_layout["updatemenus"][0]["buttons"].append({
                "label": scale_labels[scale],
                "method": "update",
                "args": [
                    {"visible": visibility},
                    {
                        "title": {
                            "text": f"Линейный график: {scale_labels[scale]}",
                            "font": {"size": 16},
                        },
                        "xaxis.range": [
                            0.5, max(1.5, len(points) + 0.5),
                        ],
                        "xaxis.dtick": max(1, len(points) // 20),
                    },
                ],
            })

        initial_visibility = [False] * len(token_traces)
        first_scale = next(iter(scale_points), None)
        if first_scale is not None:
            for trace_index in token_trace_groups.get(first_scale, []):
                initial_visibility[trace_index] = True
        for trace_index, trace in enumerate(token_traces):
            trace["visible"] = initial_visibility[trace_index]

        config = {
            "scrollZoom": True,
            "displaylogo": False,
            "responsive": True,
            "dragmode": "zoom",
            "modeBarButtonsToAdd": [
                "zoom2d",
                "pan2d",
                "autoScale2d",
                "resetScale2d",
            ],
        }

        data_json = json.dumps(traces, ensure_ascii=False)
        spectrum_data_json = json.dumps(spectrum_traces, ensure_ascii=False)
        token_data_json = json.dumps(token_traces, ensure_ascii=False)
        layout_json = json.dumps(layout, ensure_ascii=False)
        spectrum_layout_json = json.dumps(spectrum_layout, ensure_ascii=False)
        token_layout_json = json.dumps(token_layout, ensure_ascii=False)
        config_json = json.dumps(config, ensure_ascii=False)

        return (
            '<div class="chart-section">\n'
            '<div class="chart-title">Траектория доминирующих уровней</div>\n'
            '<div class="chart-box"><div id="miro-chart"></div></div>\n'
            '<div class="chart-title">Смешение и переходы уровней</div>\n'
            '<div class="chart-box"><div id="miro-spectrum-chart"></div></div>\n'
            '<div class="chart-title">Линейный график токенов</div>\n'
            '<div class="chart-box"><div id="miro-token-chart"></div></div>\n'
            '<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>\n'
            '<script>\n'
            f'var _traces = {data_json};\n'
            f'var _layout = {layout_json};\n'
            f'var _spectrumTraces = {spectrum_data_json};\n'
            f'var _spectrumLayout = {spectrum_layout_json};\n'
            f'var _tokenTraces = {token_data_json};\n'
            f'var _tokenLayout = {token_layout_json};\n'
            f'var _config = {config_json};\n'
            'Plotly.newPlot("miro-chart", _traces, _layout, _config);\n'
            'Plotly.newPlot("miro-spectrum-chart", _spectrumTraces, _spectrumLayout, _config);\n'
            'Plotly.newPlot("miro-token-chart", _tokenTraces, _tokenLayout, _config);\n'
            '</script>\n'
            '</div>\n'
        )

    # ── запись HTML на диск ──────────────────────────────────────────

    def write_html(
        self,
        result: dict[str, Any],
        path: str | Path,
        text: str | None = None,
        title: str = "Маркировка Миросложения",
    ) -> None:
        Path(path).write_text(
            self.to_html(result, text=text, title=title),
            encoding="utf-8",
        )

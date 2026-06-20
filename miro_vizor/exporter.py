"""Экспорт разметки в JSON, CSV и HTML."""
from __future__ import annotations

import csv
import html
import json
from io import StringIO
from pathlib import Path
from typing import Any

from .ontology import MiroOntology


class MiroExporter:
    """Сериализация результата маркировки в разные форматы."""

    def __init__(self, ontology: MiroOntology | None = None) -> None:
        self.ontology = ontology or MiroOntology.from_package()

    def to_json(self, result: dict[str, Any]) -> str:
        return json.dumps(result, ensure_ascii=False, indent=2)

    def write_json(self, result: dict[str, Any], path: str | Path) -> None:
        Path(path).write_text(self.to_json(result), encoding="utf-8")

    def to_csv(self, result: dict[str, Any]) -> str:
        """CSV с одной строкой на предложение: спектр L1–L7."""
        buffer = StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        header = ["index", "chapter", "text", "dominant_level"] + self.ontology.levels_ids()
        writer.writerow(header)
        chapters = result.get("chapters", [])
        for ch in chapters:
            ch_index = ch.get("index", 0)
            for sent in ch.get("sentences", []):
                spectrum = sent.get("levels", {})
                row = [
                    sent.get("index", ""),
                    ch_index,
                    sent.get("text", "").replace("\n", " "),
                    sent.get("dominant_level", ""),
                ] + [round(spectrum.get(level, 0.0), 4) for level in self.ontology.levels_ids()]
                writer.writerow(row)
        return buffer.getvalue()

    def write_csv(self, result: dict[str, Any], path: str | Path) -> None:
        Path(path).write_text(self.to_csv(result), encoding="utf-8-sig")

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
        colors = {level: self.ontology.color(level) for level in self.ontology.levels_ids()}
        names = {level: self.ontology.name(level) for level in self.ontology.levels_ids()}

        parts: list[str] = []
        parts.append(
            "<!DOCTYPE html>\n<html lang=\"ru\">\n<head>\n"
            '<meta charset="UTF-8">\n'
            f"<title>{html.escape(title)}</title>\n"
            "<style>\n"
            "body { font-family: Georgia, serif; font-size: 18px; max-width: 900px; margin: 2em auto; line-height: 1.7; color: #222; }\n"
            ".token { padding: 0.1em 0.15em; border-radius: 4px; cursor: help; }\n"
            ".legend { display: flex; flex-wrap: wrap; gap: 0.5em; margin: 1em 0; }\n"
            ".legend span { padding: 0.2em 0.6em; border-radius: 4px; color: #fff; font-size: 0.9em; }\n"
            ".work-bar { display: flex; height: 24px; border-radius: 4px; overflow: hidden; margin: 1em 0; }\n"
            ".bar-segment { height: 100%; }\n"
            "h1 { font-size: 1.8em; }\n" "h2 { font-size: 1.4em; }\n" "h3 { font-size: 1.2em; }\n"
            ".muted { color: #666; }\n"
            "</style>\n</head>\n<body>\n"
        )
        parts.append(f"<h1>{html.escape(title)}</h1>\n")
        parts.append(f"<p><strong>Доминирующий уровень:</strong> {dominant} — {names.get(dominant or '', '')}</p>\n")

        parts.append('<div class="legend">\n')
        for level in self.ontology.levels_ids():
            parts.append(
                f'<span style="background:{colors[level]}">'
                f"{level} {html.escape(names[level])}</span>\n"
            )
        parts.append("</div>\n")

        parts.append('<div class="work-bar">\n')
        for level in self.ontology.levels_ids():
            value = spectrum.get(level, 0.0)
            if value:
                parts.append(
                    f'<div class="bar-segment" style="width:{value*100:.2f}%; background:{colors[level]}" '
                    f'title="{level}: {value:.2f}"></div>\n'
                )
        parts.append("</div>\n")

        if text is not None:
            parts.append(self._render_text(text, sentences, colors))
        else:
            parts.append("<p><em>Исходный текст не передан — цветная разметка недоступна.</em></p>\n")

        parts.append("</body>\n</html>")
        return "".join(parts)

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

        sorted_spans = sorted(token_map.items(), key=lambda item: item[0][0])
        parts: list[str] = ["<p>"]
        pos = 0
        for (start, end), level in sorted_spans:
            if start < pos:
                continue
            if start > pos:
                parts.append(html.escape(text[pos:start]))
            word = text[start:end]
            parts.append(
                f'<span class="token" style="background-color: {colors[level]}33; '
                f'border-bottom: 2px solid {colors[level]};" '
                f'title="{level}">{html.escape(word)}</span>'
            )
            pos = end
        if pos < len(text):
            parts.append(html.escape(text[pos:]))
        parts.append("</p>\n")
        return "".join(parts)

    def write_html(
        self,
        result: dict[str, Any],
        path: str | Path,
        text: str | None = None,
        title: str = "Маркировка Миросложения",
    ) -> None:
        Path(path).write_text(self.to_html(result, text=text, title=title), encoding="utf-8")

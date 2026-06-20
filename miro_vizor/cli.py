"""Командная строка для маркировки текстов."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .exporter import MiroExporter
from .marker import MiroMarker
from .ontology import MiroOntology
from .graphify_adapter import MiroGraphifyExporter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Маркировка текстов по 7 уровням Миросложения.",
    )
    parser.add_argument("input", type=Path, help="Входной текстовый файл")
    parser.add_argument(
        "-o", "--output", type=Path, default=None, help="Файл для записи JSON (по умолчанию stdout)"
    )
    parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="Отключить векторную семантику (только прямое совпадение)",
    )
    parser.add_argument(
        "--ontology",
        type=Path,
        default=None,
        help="Путь к файлу онтологии (по умолчанию miro_ontology.json рядом с проектом)",
    )
    parser.add_argument(
        "--html", type=Path, default=None, help="Экспортировать цветную HTML-разметку"
    )
    parser.add_argument(
        "--csv", type=Path, default=None, help="Экспортировать CSV со спектром по предложениям"
    )
    parser.add_argument(
        "--language",
        type=str,
        default=None,
        help="Язык текста (ru/en). Если не указан, определяется автоматически.",
    )
    parser.add_argument(
        "--graph-code",
        type=Path,
        default=None,
        metavar="DIR",
        help="Построить граф из Python-кода в директории и сохранить HTML",
    )
    parser.add_argument(
        "--graph-output",
        type=Path,
        default=Path("graph.html"),
        help="Имя выходного HTML-файла для --graph-code (по умолчанию graph.html)",
    )
    parser.add_argument(
        "--graph-text",
        action="store_true",
        help="Построить граф уровней из размеченного текста (сохраняется в graph.html)",
    )
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"Файл не найден: {args.input}", file=sys.stderr)
        return 1

    ontology = MiroOntology.from_file(args.ontology) if args.ontology else None
    marker = MiroMarker(
        ontology=ontology,
        use_embeddings=not args.no_embeddings,
        language=args.language,
    )
    text = args.input.read_text(encoding="utf-8")
    result = marker.mark_text(text, title=args.input.name)

    exporter = MiroExporter(ontology=marker.ontology)

    out = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(out, encoding="utf-8")
        print(f"Сохранено JSON: {args.output}")
    else:
        print(out)

    if args.html:
        exporter.write_html(result, args.html, text=text, title=args.input.name)
        print(f"Сохранено HTML: {args.html}")

    if args.csv:
        exporter.write_csv(result, args.csv)
        print(f"Сохранено CSV: {args.csv}")

    graph_exporter = MiroGraphifyExporter(ontology=marker.ontology)

    if args.graph_code:
        stats = graph_exporter.write_graph_code(args.graph_code, args.graph_output)
        print(f"Граф кода сохранён: {args.graph_output}")
        print(f"  узлов: {stats['nodes']}, рёбер: {stats['edges']}, сообществ: {stats['communities']}")

    if args.graph_text:
        stats = graph_exporter.write_graph_text(result, args.graph_output, ontology=marker.ontology)
        print(f"Граф текста сохранён: {args.graph_output}")
        print(f"  узлов: {stats['nodes']}, рёбер: {stats['edges']}, сообществ: {stats['communities']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

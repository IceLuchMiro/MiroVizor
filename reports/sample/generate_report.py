#!/usr/bin/env python3
"""Генератор отчёта MiroVizor для sample.txt"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULT = ROOT / "result.json"
REPORT = ROOT / "report.md"

with RESULT.open("r", encoding="utf-8") as f:
    data = json.load(f)

work = data["work"]
proj_dir = ROOT.parent.parent
sample_text = (proj_dir / "sample.txt").read_text(encoding="utf-8")

LEVEL_NAMES = {
    "L1": "L1 — Выживание / тело / страх",
    "L2": "L2 — Сила / воля / конкуренция",
    "L3": "L3 — Порядок / рассудок / красота",
    "L4": "L4 — Связь / любовь / гармония",
    "L5": "L5 — Знание / творчество / рост",
    "L6": "L6 — Система / целостность / мудрость",
    "L7": "L7 — Единство / трансценденция / свет",
}

lines = [
    "# Отчёт MiroVizor: sample.txt",
    "",
    f"Дата анализа: `{__import__('datetime').datetime.now().isoformat(sep=' ', timespec='minutes')}`",
    "",
    "## Общая сводка",
    "",
    f"- **Доминантный уровень:** `{work['dominant_level']}` — {LEVEL_NAMES.get(work['dominant_level'], '')}",
    f"- **Всего предложений:** {len(data['sentences'])}",
    "",
    "### Спектр уровней",
    "",
    "| Уровень | Доля |",
    "|---|---|",
]
for level in ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]:
    value = work["spectrum"].get(level, 0.0)
    bar = "█" * int(value * 20)
    lines.append(f"| {LEVEL_NAMES[level]} | {value:.4f} {bar} |")

lines.extend([
    "",
    "### Распределение предложений по уровням",
    "",
])
counts = {}
for s in data["sentences"]:
    lvl = s.get("level", "none") or "none"
    counts[lvl] = counts.get(lvl, 0) + 1

lines.append("| Уровень | Количество предложений |")
lines.append("|---|---|")
for lvl in ["L1", "L2", "L3", "L4", "L5", "L6", "L7", "none"]:
    if lvl in counts:
        lines.append(f"| `{lvl}` | {counts[lvl]} |")

lines.extend([
    "",
    "## Детализация по предложениям",
    "",
    "| # | Уровень | Текст |",
    "|---|---|---|",
])
for i, s in enumerate(data["sentences"], start=1):
    lvl = s.get("level") or "—"
    text = s.get("text", "").replace("|", "\\|").replace("\n", " ")
    if len(text) > 200:
        text = text[:197] + "..."
    lines.append(f"| {i} | {lvl} | {text} |")

lines.extend([
    "",
    "## Интерпретация",
    "",
])

dom = work["dominant_level"]
if dom == "L3":
    lines.append("Текст построен в рационально-эстетической форме: автор задаёт вопросы цели, объясняет намерения, придаёт изящество изложению. Доминанта L3 говорит о порядке мысли, культурной мерности и сдержанной красоте.")
elif dom == "L4":
    lines.append("Доминанта L4 указывает на личное обращение, нежность, стремление к связи. Текст — это попытка преодолеть дистанцию и восстановить гармонию между автором и адресатом.")
elif dom == "L6":
    lines.append("Доминанта L6 свидетельствует о системном, философском видении. Автор мыслит целостно: его идея направлена на объединение смыслов и уровней бытия.")
elif dom == "L2":
    lines.append("Доминанта L2 — воля, напор, преодоление. В тексте слышна готовность к действию, борьбе за идею и преодолению сопротивления.")

lines.extend([
    "",
    "## Файлы",
    "",
    "- `result.json` — машиночитаемый профиль",
    "- `result.html` — цветная HTML-разметка",
    "- `result.csv` — таблица по предложениям",
    "",
    "---",
    "*Отчёт сгенерирован MiroVizor*",
])

REPORT.write_text("\n".join(lines), encoding="utf-8")
print(f"Отчёт сохранён: {REPORT}")

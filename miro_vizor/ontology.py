"""Загрузка и доступ к онтологии Миросложения."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# Единая палитра Миросложения: L1 → L7.
LEVEL_COLORS: dict[str, str] = {
    "L1": "#E53935",  # красный
    "L2": "#FB8C00",  # оранжевый
    "L3": "#FDD835",  # жёлтый
    "L4": "#43A047",  # зелёный
    "L5": "#1E88E5",  # голубой
    "L6": "#3949AB",  # синий
    "L7": "#8E24AA",  # фиолетовый
}


LEVEL_FIELDS = [
    "name",
    "description",
    "weight",
    "keywords",
    "categories",
    "theme",
    "synonyms",
    "term_weights",
    "category_weights",
]


class MiroOntology:
    """Обёртка над JSON-онтологией уровней L1–L7 + пользовательские уровни."""

    DEFAULT_LEVEL_WEIGHT = 1.0

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data
        self.levels: dict[str, dict[str, Any]] = data.get("levels", {})
        self.metadata: dict[str, Any] = data.get("metadata", {})
        self._index: dict[str, set[str]] = {}
        # term -> {level_id: weight}
        self._weights: dict[str, dict[str, float]] = {}
        # canonical -> {level_id: weight} для быстрого поиска синонимов
        self._synonyms: dict[str, dict[str, float]] = {}
        self._build_index()

    @classmethod
    def from_file(cls, path: str | Path) -> "MiroOntology":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(data)

    @classmethod
    def from_package(
        cls,
        filename: str = "miro_ontology.json",
        language: str | None = None,
    ) -> "MiroOntology":
        pkg_root = Path(__file__).resolve().parent
        project_root = pkg_root.parent

        candidates = [pkg_root]
        if project_root != pkg_root:
            candidates.append(project_root)

        searched: list[Path] = []

        for root in candidates:
            if language:
                lang_path = root / f"{Path(filename).stem}_{language}.json"
                if lang_path.exists():
                    return cls.from_file(lang_path)
                searched.append(lang_path)
            path = root / filename
            if path.exists():
                return cls.from_file(path)
            searched.append(path)

        raise FileNotFoundError(f"Онтология не найдена. Искали: {', '.join(str(p) for p in searched)}")

    def _build_index(self) -> None:
        """Индекс: лемма -> множество уровней, где она встречается."""
        self._index = {}
        self._weights = {}
        self._synonyms = {}
        for level_id, level in self.levels.items():
            level_weight = level.get("weight", self.DEFAULT_LEVEL_WEIGHT)
            category_weights = level.get("category_weights", {})
            term_weights = level.get("term_weights", {})
            synonyms = level.get("synonyms", {})

            def add(term: str, weight: float) -> None:
                key = term.lower()
                self._index.setdefault(key, set()).add(level_id)
                self._weights.setdefault(key, {})
                self._weights[key][level_id] = max(
                    self._weights[key].get(level_id, 0.0),
                    weight,
                )

            # категории с весами
            for category, words in level.get("categories", {}).items():
                cat_weight = category_weights.get(category, self.DEFAULT_LEVEL_WEIGHT)
                for word in words:
                    add(word, cat_weight)

            # ключевые слова с индивидуальными весами
            for word in level.get("keywords", []):
                w = term_weights.get(word, level_weight)
                add(word, w)

            # тема разбивается на термины
            for token in level.get("theme", "").lower().replace(",", " ").split():
                add(token, level_weight * 0.5)

            # синонимы
            for canonical, syns in synonyms.items():
                base_weight = term_weights.get(canonical, level_weight)
                for syn in syns:
                    syn_key = syn.lower()
                    self._synonyms.setdefault(syn_key, {})
                    self._synonyms[syn_key][level_id] = max(
                        self._synonyms[syn_key].get(level_id, 0.0),
                        base_weight,
                    )
                    # синоним тоже индексируется как термин
                    add(syn, base_weight)

    def levels_ids(self) -> list[str]:
        return list(self.levels.keys())

    def level(self, level_id: str) -> dict[str, Any]:
        return self.levels.get(level_id, {})

    def color(self, level_id: str) -> str:
        # Стандартные L1–L7 всегда сохраняют канонический порядок цветов.
        return LEVEL_COLORS.get(level_id) or self.level(level_id).get("color") or "#000000"

    def name(self, level_id: str) -> str:
        return self.level(level_id).get("name", level_id)

    def weight(self, lemma: str, level_id: str) -> float:
        """Вес термина внутри уровня (по умолчанию 1.0)."""
        return self._weights.get(lemma.lower(), {}).get(level_id, self.DEFAULT_LEVEL_WEIGHT)

    def synonym_weight(self, lemma: str, level_id: str) -> float | None:
        """Вес синонима, если лемма является синонимом канонического термина."""
        return self._synonyms.get(lemma.lower(), {}).get(level_id)

    def matches(self, lemma: str) -> set[str]:
        """Вернуть уровни, в которых встречается лемма или её синоним."""
        key = lemma.lower()
        result = set(self._index.get(key, []))
        result.update(self._synonyms.get(key, {}).keys())
        return result

    def all_terms(self) -> set[str]:
        return set(self._index.keys())

    def reference_phrases(self, level_id: str) -> list[str]:
        """Эталонные фразы для векторной семантики."""
        level = self.level(level_id)
        phrases: list[str] = []
        if "theme" in level:
            phrases.append(level["theme"])
        phrases.extend(level.get("keywords", []))
        for words in level.get("categories", {}).values():
            phrases.extend(words)
        return phrases

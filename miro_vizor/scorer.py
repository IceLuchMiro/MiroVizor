"""Подсчёт весов уровней для токенов и предложений."""
from __future__ import annotations

from typing import Any, Callable

from .embedder import MiroEmbedder
from .languages import build_lemmatizer
from .ontology import MiroOntology


class MiroScorer:
    """Прямое совпадение лемм + опциональная векторная семантика.

    Поддерживает взвешенные термины, синонимы и мультиязычность.
    """

    DIRECT_WEIGHT = 0.6
    EMBED_WEIGHT = 0.4

    def __init__(
        self,
        ontology: MiroOntology,
        lemmatizer: Callable[[str], str] | None = None,
        embedder: MiroEmbedder | None = None,
        language: str | None = None,
    ) -> None:
        self.ontology = ontology
        self.language = language or ontology.metadata.get("language", "ru")
        self._lemmatize = lemmatizer or build_lemmatizer(self.language)
        self.embedder = embedder

    def token_scores(self, word: str) -> dict[str, float]:
        """Вернуть нормализованный спектр по уровням для одного слова."""
        lemma = self._lemmatize(word)
        if not lemma:
            return {}
        lemma = lemma.lower()
        matches = self.ontology.matches(lemma)
        if not matches:
            return {}
        weighted: dict[str, float] = {}
        for level in matches:
            weight = self.ontology.weight(lemma, level)
            syn_weight = self.ontology.synonym_weight(lemma, level)
            if syn_weight is not None:
                weight = max(weight, syn_weight)
            weighted[level] = weight
        total = sum(weighted.values())
        if total == 0:
            return {}
        return {level: round(value / total, 4) for level, value in weighted.items()}

    def sentence_scores(self, text: str) -> dict[str, float]:
        """Гибридный score: прямое совпадение + эмбеддинг."""
        direct: dict[str, float] = {}
        words = text.split()
        for raw in words:
            word = raw.strip(".,!?;:\"'()[]«»—–-").lower()
            if not word:
                continue
            scores = self.token_scores(word)
            for level, value in scores.items():
                direct[level] = direct.get(level, 0.0) + value

        if self.embedder is not None and self.embedder.available:
            embed = self.embedder.text_scores(text)
            # Нормализуем оба компонента
            direct_total = sum(direct.values()) or 1.0
            embed_total = sum(abs(v) for v in embed.values()) or 1.0
            combined: dict[str, float] = {}
            for level in self.ontology.levels_ids():
                d = direct.get(level, 0.0) / direct_total
                e = max(0.0, embed.get(level, 0.0)) / embed_total
                combined[level] = self.DIRECT_WEIGHT * d + self.EMBED_WEIGHT * e
            return self._normalize(combined)

        return self._normalize(direct)

    @staticmethod
    def _normalize(scores: dict[str, float]) -> dict[str, float]:
        if not scores:
            return {}
        total = sum(scores.values())
        if total == 0:
            return {}
        return {level: round(value / total, 4) for level, value in scores.items()}

    @staticmethod
    def dominant(scores: dict[str, float]) -> str | None:
        if not scores:
            return None
        return max(scores.items(), key=lambda item: item[1])[0]

"""Векторная семантика с опциональным fallback."""
from __future__ import annotations

from typing import Any

import numpy as np

from .ontology import MiroOntology


class MiroEmbedder:
    """Эмбеддинги уровней с кэшированием.

    Если sentence-transformers не установлен — используется zero fallback.
    """

    def __init__(self, ontology: MiroOntology, model_name: str | None = None) -> None:
        self.ontology = ontology
        self.model_name = model_name or "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        self._model: Any = None
        self._level_embeddings: dict[str, np.ndarray] = {}
        self._available = False
        self._init_model()

    def _init_model(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._model = SentenceTransformer(self.model_name)
            self._available = True
        except Exception:  # pragma: no cover
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def embed(self, texts: list[str]) -> np.ndarray:
        if self._available and self._model is not None:
            return self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        # Fallback: случайные нормализованные векторы для детерминированного поведения
        rng = np.random.default_rng(42)
        vectors = rng.normal(size=(len(texts), 384)).astype(np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-9
        return vectors / norms

    def level_embedding(self, level_id: str) -> np.ndarray:
        if level_id not in self._level_embeddings:
            phrases = self.ontology.reference_phrases(level_id)
            if not phrases:
                self._level_embeddings[level_id] = self.embed([""])[0]
            else:
                embeddings = self.embed(phrases)
                self._level_embeddings[level_id] = embeddings.mean(axis=0)
        return self._level_embeddings[level_id]

    def similarity(self, text: str, level_id: str) -> float:
        if not text.strip():
            return 0.0
        vec = self.embed([text])[0]
        lvl = self.level_embedding(level_id)
        return float(np.dot(vec, lvl) / (np.linalg.norm(vec) * np.linalg.norm(lvl) + 1e-9))

    def text_scores(self, text: str) -> dict[str, float]:
        """Вернуть эмбеддинг-скоры по всем уровням."""
        return {level_id: self.similarity(text, level_id) for level_id in self.ontology.levels_ids()}

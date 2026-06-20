"""Основной класс маркировки текста уровнями Миросложения."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .embedder import MiroEmbedder
from .ontology import MiroOntology
from .scorer import MiroScorer
from .tokenizer import MiroTokenizer, Sentence


class MiroMarker:
    """Маркировка труда → глав → предложений → токенов."""

    def __init__(
        self,
        ontology: MiroOntology | None = None,
        use_embeddings: bool = True,
        language: str | None = None,
    ) -> None:
        self.ontology = ontology or MiroOntology.from_package(language=language)
        self.language = language or self.ontology.metadata.get("language", "ru")
        self.tokenizer = MiroTokenizer(language=self.language)
        embedder = MiroEmbedder(self.ontology) if use_embeddings else None
        self.scorer = MiroScorer(
            self.ontology,
            embedder=embedder,
            language=self.language,
        )

    def mark_text(self, text: str, title: str = "") -> dict[str, Any]:
        chapters_data = self.tokenizer.split_chapters(text)
        if not chapters_data:
            chapters_data = [("", text)]

        chapters: list[dict[str, Any]] = []
        all_sentences: list[dict[str, Any]] = []
        work_totals: dict[str, float] = {}

        for ch_index, (header, body) in enumerate(chapters_data, start=1):
            body_start = text.index(body, text.index(header) + len(header)) if header else 0
            sentences = self.tokenizer.split_sentences(body, offset=body_start)
            ch_sentences: list[dict[str, Any]] = []
            ch_totals: dict[str, float] = {}

            for sent_index, sentence in enumerate(sentences):
                sent_result = self._mark_sentence(
                    sentence,
                    global_index=len(all_sentences) + sent_index,
                )
                ch_sentences.append(sent_result)
                all_sentences.append(sent_result)
                for level, value in sent_result["levels"].items():
                    ch_totals[level] = ch_totals.get(level, 0.0) + value

            chapter_spectrum = self.scorer._normalize(ch_totals)
            chapter: dict[str, Any] = {
                "index": ch_index,
                "title": header,
                "dominant_level": self.scorer.dominant(chapter_spectrum),
                "spectrum": self._fill_spectrum(chapter_spectrum),
                "sentences": ch_sentences,
            }
            chapters.append(chapter)
            for level, value in ch_totals.items():
                work_totals[level] = work_totals.get(level, 0.0) + value

        work_spectrum = self.scorer._normalize(work_totals)
        return {
            "work": {
                "title": title,
                "dominant_level": self.scorer.dominant(work_spectrum),
                "spectrum": self._fill_spectrum(work_spectrum),
            },
            "chapters": chapters,
            "sentences": all_sentences,
        }

    def _mark_sentence(self, sentence: Sentence, global_index: int) -> dict[str, Any]:
        tokens: list[dict[str, Any]] = []
        for token in sentence.tokens:
            scores = self.scorer.token_scores(token.text)
            tokens.append({
                "text": token.text,
                "start": token.start + sentence.start,
                "end": token.end + sentence.start,
                "level": self.scorer.dominant(scores),
                "scores": self._fill_spectrum(scores),
            })
        levels = self.scorer.sentence_scores(sentence.text)
        return {
            "index": global_index,
            "text": sentence.text,
            "start": sentence.start,
            "end": sentence.end,
            "dominant_level": self.scorer.dominant(levels),
            "levels": self._fill_spectrum(levels),
            "tokens": tokens,
        }

    def _fill_spectrum(self, scores: dict[str, float]) -> dict[str, float]:
        """Дополнить спектр нулями для всех уровней и сохранить порядок L1–L7."""
        return {level: round(scores.get(level, 0.0), 4) for level in self.ontology.levels_ids()}

    def mark_file(self, path: str | Path) -> dict[str, Any]:
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        return self.mark_text(text, title=path.name)

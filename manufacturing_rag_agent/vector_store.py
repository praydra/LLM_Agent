from __future__ import annotations

import math
from collections import Counter

from .documents import tokenize
from .schema import Chunk, RetrievalResult


class TfidfVectorStore:
    """Small in-memory TF-IDF search index.

    This is not meant to replace a production vector DB. It gives the MVP a
    dependency-free retrieval layer and a stable interface that can later be
    swapped for Chroma, FAISS, pgvector, OpenSearch, or an embedding API.
    """

    def __init__(self, chunks: list[Chunk]) -> None:
        if not chunks:
            raise ValueError("At least one chunk is required")

        self.chunks = chunks
        self.idf = self._build_idf(chunks)
        self.vectors = [self._vectorize(chunk.text) for chunk in chunks]

    def search(self, query: str, top_k: int = 4, min_score: float = 0.0) -> list[RetrievalResult]:
        query_vector = self._vectorize(query)
        scored: list[RetrievalResult] = []

        for chunk, vector in zip(self.chunks, self.vectors):
            score = _cosine(query_vector, vector)
            if score >= min_score:
                scored.append(RetrievalResult(chunk=chunk, score=score))

        scored.sort(key=lambda result: result.score, reverse=True)
        return scored[:top_k]

    def _build_idf(self, chunks: list[Chunk]) -> dict[str, float]:
        document_frequency: Counter[str] = Counter()
        for chunk in chunks:
            document_frequency.update(set(tokenize(chunk.text)))

        total = len(chunks)
        return {
            term: math.log((1 + total) / (1 + df)) + 1.0
            for term, df in document_frequency.items()
        }

    def _vectorize(self, text: str) -> dict[str, float]:
        terms = tokenize(text)
        if not terms:
            return {}

        counts = Counter(terms)
        max_count = max(counts.values())
        vector = {
            term: (count / max_count) * self.idf.get(term, 1.0)
            for term, count in counts.items()
        }
        norm = math.sqrt(sum(weight * weight for weight in vector.values()))
        if norm == 0:
            return {}
        return {term: weight / norm for term, weight in vector.items()}


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0

    if len(left) > len(right):
        left, right = right, left
    return sum(weight * right.get(term, 0.0) for term, weight in left.items())

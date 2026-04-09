from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from camp_casey_app.domain.models import RAGChunk
from camp_casey_app.utils.text import normalize_text, tokenize_for_search


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _norm(vector: list[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))


class RAGRepository:
    def __init__(self, chunks_path: Path, index_path: Path, openai_service: Any | None = None):
        self.chunks_path = chunks_path
        self.index_path = index_path
        self.openai_service = openai_service
        self._chunks = self._load_chunks()
        self._vectors = self._load_vectors()

    def _load_chunks(self) -> list[RAGChunk]:
        if not self.chunks_path.exists():
            return []
        chunks: list[RAGChunk] = []
        for line in self.chunks_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            chunks.append(RAGChunk.model_validate(json.loads(line)))
        return chunks

    def _load_vectors(self) -> dict[str, list[float]]:
        if not self.index_path.exists():
            return {}
        payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        vectors = payload.get("vectors", [])
        if isinstance(vectors, dict):
            return {key: [float(value) for value in vector] for key, vector in vectors.items()}
        mapping: dict[str, list[float]] = {}
        for item in vectors:
            if isinstance(item, dict) and item.get("chunk_id") and item.get("embedding"):
                mapping[item["chunk_id"]] = [float(value) for value in item["embedding"]]
        return mapping

    @property
    def chunks(self) -> list[RAGChunk]:
        return self._chunks

    def retrieve(self, query: str, *, top_k: int = 4, filters: dict[str, Any] | None = None) -> list[RAGChunk]:
        query_tokens = tokenize_for_search(query)
        normalized_query = normalize_text(query)

        candidates = self._chunks
        if filters:
            filtered: list[RAGChunk] = []
            for chunk in candidates:
                include = True
                for key, expected in filters.items():
                    if chunk.metadata.get(key) != expected:
                        include = False
                        break
                if include:
                    filtered.append(chunk)
            candidates = filtered

        if self.openai_service and self.openai_service.is_available() and self._vectors:
            try:
                query_vector = self.openai_service.embed_texts([query])[0]
                query_norm = _norm(query_vector) or 1.0
                scored = []
                for chunk in candidates:
                    vector = self._vectors.get(chunk.chunk_id)
                    if not vector:
                        continue
                    similarity = _dot(query_vector, vector) / ((query_norm * _norm(vector)) or 1.0)
                    scored.append((similarity, chunk))
                if scored:
                    scored.sort(key=lambda item: item[0], reverse=True)
                    return [chunk for _, chunk in scored[:top_k]]
            except Exception:
                pass

        scored_lexical = []
        for chunk in candidates:
            overlap = len(set(query_tokens) & set(chunk.lexical_tokens))
            fuzzy = fuzz.WRatio(normalized_query, normalize_text(f"{chunk.title} {chunk.text}"))
            score = overlap * 30 + fuzzy
            scored_lexical.append((score, chunk))
        scored_lexical.sort(key=lambda item: item[0], reverse=True)
        return [chunk for score, chunk in scored_lexical[:top_k] if score > 20]

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from camp_casey_app.ai.openai_client import OpenAIService
from camp_casey_app.config import get_settings
from camp_casey_app.domain.models import RAGChunk


def batched(items: list, batch_size: int):
    for index in range(0, len(items), batch_size):
        yield items[index:index + batch_size]


def main() -> None:
    settings = get_settings()
    chunks_path = settings.rag_chunks_path
    index_path = settings.rag_index_path
    chunks = [
        RAGChunk.model_validate(json.loads(line))
        for line in chunks_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    openai_service = OpenAIService(settings)

    if not openai_service.is_available() or not chunks:
        payload = {
            "model": None,
            "embeddings_available": False,
            "vectors": [],
            "reason": "OPENAI_API_KEY not configured or no chunks available",
        }
        index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    vectors = []
    for chunk_batch in batched(chunks, 64):
        embeddings = openai_service.embed_texts([chunk.text for chunk in chunk_batch])
        for chunk, embedding in zip(chunk_batch, embeddings):
            vectors.append({"chunk_id": chunk.chunk_id, "embedding": embedding})

    payload = {
        "model": settings.openai_embedding_model,
        "embeddings_available": True,
        "vectors": vectors,
    }
    index_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"chunks": len(chunks), "embedded": len(vectors), "model": settings.openai_embedding_model}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

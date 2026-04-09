from __future__ import annotations


def test_rag_retrieval_smoke(container):
    results = container.rag_repository.retrieve("보산역 인천", top_k=3)
    assert results
    assert any(result.kind.startswith("train") for result in results)

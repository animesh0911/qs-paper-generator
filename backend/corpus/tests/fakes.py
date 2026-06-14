"""Deterministic corpus adapters used by embedding integration tests.

The fixed adapter makes provider-neutral embedding behavior observable without
network access, model SDKs, or generated values.
"""

from __future__ import annotations

from corpus.embeddings import EmbeddingProfile


class FixedEmbeddingClient:
    def __init__(
        self,
        vectors: dict[str, tuple[float, ...]],
        *,
        model: str = "fixed-vector-test",
        version: str = "v1",
        dimensions: int = 3,
        fail_on_call: int | None = None,
    ):
        self.profile = EmbeddingProfile(
            model=model,
            version=version,
            dimensions=dimensions,
        )
        self.vectors = vectors
        self.fail_on_call = fail_on_call
        self.calls: list[tuple[str, ...]] = []

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        self.calls.append(texts)
        if self.fail_on_call == len(self.calls):
            raise RuntimeError("configured fixed embedding failure")
        return tuple(self.vectors[text] for text in texts)

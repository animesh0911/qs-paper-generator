"""Provider-neutral embedding population for RetrievalChunks.

The corpus module owns vector profile metadata, output validation, and
idempotent batch persistence. Callers inject an EmbeddingClient; this module
does not import or configure a provider SDK.

Patterns / invariants:
- Stored vectors always match the client's declared dimensions.
- Completed model/version matches are skipped without calling the client.
- Each validated batch commits independently so retries resume completed work.

Where it fits:
- Called by: corpus management commands and tests.
- Calls into: an injected EmbeddingClient.
- Persisted via: corpus.models.RetrievalChunk.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from django.db import transaction

from .models import RetrievalChunk, TextbookDocument


@dataclass(frozen=True)
class EmbeddingProfile:
    model: str
    version: str
    dimensions: int

    def __post_init__(self):
        if not self.model.strip():
            raise ValueError("model must not be blank.")
        if not self.version.strip():
            raise ValueError("version must not be blank.")
        if len(self.model) > 200:
            raise ValueError("model must not exceed 200 characters.")
        if len(self.version) > 100:
            raise ValueError("version must not exceed 100 characters.")
        if self.dimensions < 1:
            raise ValueError("dimensions must be positive.")


class EmbeddingClient(Protocol):
    profile: EmbeddingProfile

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]: ...


@dataclass(frozen=True)
class EmbeddingPopulationRequest:
    document: TextbookDocument
    client: EmbeddingClient
    batch_size: int = 32


@dataclass(frozen=True)
class EmbeddingPopulationResult:
    document: TextbookDocument
    populated_count: int
    skipped_count: int


class RetrievalChunkEmbeddingPopulator:
    """Populate one document's chunks in independently committed batches."""

    def populate(
        self, request: EmbeddingPopulationRequest
    ) -> EmbeddingPopulationResult:
        if request.batch_size < 1:
            raise ValueError("batch_size must be positive.")

        profile = request.client.profile
        chunks = request.document.retrieval_chunks.order_by("stable_chunk_id")
        pending = list(
            chunks.exclude(
                embedding__isnull=False,
                embedding_model=profile.model,
                embedding_version=profile.version,
                embedding_dimensions=profile.dimensions,
            )
        )
        skipped_count = chunks.count() - len(pending)
        populated_count = 0

        for offset in range(0, len(pending), request.batch_size):
            batch = pending[offset : offset + request.batch_size]
            vectors = request.client.embed(tuple(chunk.text for chunk in batch))
            validate_embedding_vectors(vectors, len(batch), profile.dimensions)
            for chunk, vector in zip(batch, vectors, strict=True):
                chunk.embedding = vector
                chunk.embedding_model = profile.model
                chunk.embedding_version = profile.version
                chunk.embedding_dimensions = profile.dimensions
            with transaction.atomic():
                RetrievalChunk.objects.bulk_update(
                    batch,
                    [
                        "embedding",
                        "embedding_model",
                        "embedding_version",
                        "embedding_dimensions",
                    ],
                )
            populated_count += len(batch)

        return EmbeddingPopulationResult(
            document=request.document,
            populated_count=populated_count,
            skipped_count=skipped_count,
        )


def validate_embedding_vectors(
    vectors: tuple[tuple[float, ...], ...],
    expected_count: int,
    dimensions: int,
) -> None:
    if len(vectors) != expected_count:
        raise ValueError("EmbeddingClient returned the wrong vector count.")
    for vector in vectors:
        if len(vector) != dimensions:
            raise ValueError("EmbeddingClient returned the wrong dimensions.")
        if not all(math.isfinite(value) for value in vector):
            raise ValueError("EmbeddingClient returned a non-finite value.")
        if not any(value != 0.0 for value in vector):
            raise ValueError("EmbeddingClient returned a zero-norm vector.")

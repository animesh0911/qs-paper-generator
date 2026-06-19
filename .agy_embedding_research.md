# Embedding Model Evaluation Report for NCERT Science Retrieval (Issue #174)

This report outlines embedding model candidates, local evaluation setups, licensing suitability, and database architecture recommendations for populating `RetrievalChunk` embeddings for the `jesc104` ("Carbon and its Compounds") corpus.

---

## 1. Candidate Embedding Models Deep-Dive

We evaluate and compare the leading open-source/free models for local deployment, prioritizing those optimized for retrieval (MTEB), long context support, and local execution on Apple Silicon (MPS) or CPU.

### A. BGE Family (BAAI)
*   **BAAI/bge-large-en-v1.5** (335M parameters, ~1.34 GB)
    *   *Strengths*: Long-standing top performer on English retrieval benchmarks. Extremely stable and standard.
    *   *Query Instructions*: While it supports instruction tuning, the `v1.5` release was optimized to perform exceptionally well even without explicit query instructions.
    *   *Dimensions*: 1024
    *   *License*: MIT (commercial-friendly).
*   **BAAI/bge-m3** (567M parameters, ~2.27 GB)
    *   *Strengths*: A highly versatile multilingual model supporting dense, sparse (lexical), and multi-vector (ColBERT-like) retrieval.
    *   *Query Instructions*: Does not require query prefixes.
    *   *Dimensions*: 1024
    *   *License*: MIT (commercial-friendly).

### B. GTE / Qwen Family (Alibaba NLP)
*   **Alibaba-NLP/gte-Qwen2-1.5B-instruct** (1.5B parameters, ~3.0 GB)
    *   *Strengths*: An LLM-based embedding model built on top of Qwen2. It sits near the top of the MTEB leaderboard, offering state-of-the-art conceptual matching, complex logic understanding, and chemical formula relationship tracing.
    *   *Query Instructions*: Requires query prefixes/instructions (e.g., passing `prompt_name="query"` in sentence-transformers).
    *   *Dimensions*: 1536
    *   *License*: Apache 2.0 (commercial-friendly).

### C. Nomic Family
*   **nomic-ai/nomic-embed-text-v1.5** (137M parameters, ~0.55 GB)
    *   *Strengths*: Natively supports a long context window of 8,192 tokens. It supports **Matryoshka Representation Learning (MRL)**, enabling dimension truncation down to 512, 256, 128, or 64 with negligible quality loss.
    *   *Query Instructions*: Requires prefixes: `search_query: ` for queries, and `search_document: ` for documents.
    *   *Dimensions*: 768 (default), flexible down to 256 or 128.
    *   *License*: Apache 2.0 (commercial-friendly).

### D. Snowflake Family
*   **Snowflake/snowflake-arctic-embed-m-v1.5** (109M parameters, ~0.44 GB)
    *   *Strengths*: Designed specifically for high-efficiency enterprise RAG. It also supports MRL dimension truncation, making it extremely lightweight and cost-effective.
    *   *Query Instructions*: Requires query prefix (e.g., `Represent this sentence for searching relevant passages: `).
    *   *Dimensions*: 768, flexible down to 256.
    *   *License*: Apache 2.0 (commercial-friendly).

### E. Jina Family
*   **jina-embeddings-v2-base-en** (137M parameters, ~0.55 GB)
    *   *Strengths*: An early pioneer in open-source 8k context length embeddings. Excellent performance for document chunks.
    *   *Query Instructions*: No prefix required.
    *   *Dimensions*: 768
    *   *License*: Apache 2.0 (commercial-friendly).
    *   *Note on v3*: While `jina-embeddings-v3` is superior in quality and supports Matryoshka, it is licensed under **CC-BY-NC 4.0** (non-commercial only). To avoid commercial licensing fees for the app, we recommend sticking to `v2-base-en` or other Apache/MIT models.

### F. Mixedbread Family
*   **mixedbread-ai/mxbai-embed-large-v1** (335M parameters, ~1.34 GB)
    *   *Strengths*: Built for state-of-the-art English retrieval. Supports MRL truncation.
    *   *Query Instructions*: Requires query prefix: `Represent this sentence for searching relevant passages: `.
    *   *Dimensions*: 1024
    *   *License*: Apache 2.0 (commercial-friendly).

---

## 2. Comparative Analysis Matrix

| Model Candidate | Parameter Size / Disk | Default Dimensions | Matryoshka Support | License | Query Prefix Requirement | Quality Expectations (Textbook Science) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **nomic-embed-text-v1.5** | 137M / ~0.55 GB | 768 | Yes (64-768) | Apache 2.0 | `search_query: ` | **High**: Excellent structure search, lightweight, 8k context helps. |
| **bge-large-en-v1.5** | 335M / ~1.34 GB | 1024 | No | MIT | None | **High**: Reliable standard, strong English lexical-semantic bridge. |
| **gte-Qwen2-1.5B-instruct** | 1.5B / ~3.00 GB | 1536 | No | Apache 2.0 | Yes (Instruct prompt) | **Exceptional**: Superior scientific reasoner, best at chemistry syntax. |
| **snowflake-arctic-embed-m-v1.5** | 109M / ~0.44 GB | 768 | Yes (256-768) | Apache 2.0 | Yes (Arctic prompt) | **Medium-High**: Highly optimized for short/medium text retrieval. |
| **jina-embeddings-v2-base-en** | 137M / ~0.55 GB | 768 | No | Apache 2.0 | None | **Medium**: Good baseline, but outperformed by newer models. |
| **mxbai-embed-large-v1** | 335M / ~1.34 GB | 1024 | Yes (256-1024) | Apache 2.0 | Yes (Mxbai prompt) | **High**: Very strong general English retrieval quality. |

---

## 3. Local Runtime Feasibility on Apple Silicon & CPU

For a database of only **153 chunks** (the entire `jesc104` PDF corpus chunks), local execution is **fully feasible** and extremely fast:
*   **Throughput**: Inference on a local CPU or Apple Silicon GPU (using the PyTorch `mps` device backend via `sentence-transformers`) will complete in under 2 seconds for smaller models (<500M params) and under 8 seconds for the 1.5B Qwen model.
*   **Operational Tooling Options**:
    1.  **Sentence-Transformers (Recommended)**: Extremely easy Python integration. Automatically detects and leverages `device="mps"` on Apple Silicon.
    2.  **Ollama**: Ideal for offloading model compilation and running a background microservice. Models like `nomic-embed-text` and `bge-m3` are officially supported and run via an OpenAI-compatible API on `localhost:11434`.

---

## 4. Production API / Provider Comparison Candidates

To establish a performance ceiling for evaluation, we recommend including a production comparison candidate using a hosted API provider.
*   **OpenAI text-embedding-3-large**
    *   *Dimensions*: 3072 (supports Matryoshka truncation to 1024 or 768 to match local model baselines).
    *   *Quality*: Golden baseline for semantic search.
    *   *Cost*: $0.00013 per 1k tokens (costs less than $0.01 for the entire evaluation pipeline).
*   **Google Gemini text-embedding-004**
    *   *Dimensions*: 768.
    *   *Quality*: Excellent multilingual support and deep conceptual alignment.
    *   *Cost*: Extremely cheap or covered by Google AI Studio free tier.

---

## 5. Repo-Specific Design Questions

### Which `RetrievalChunk` fields should be embedded?
*   **Only `text`** should be embedded.
*   *Rationale*: The `text` field in `RetrievalChunk` is a pre-composed string built in `RetrievalChunkBuilder._upsert` (lines 311–321):
    ```python
    text = f"{heading_context}\n{body}" if body else heading_context
    ```
    This field already encapsulates the parent headings, active landmark context (e.g. Activity names, Question sections), and the actual element body text.
    Database columns like `page_start`, `content_types`, and `citation` are metadata. Generating embeddings from these fields would introduce semantic noise (e.g. embedding page numbers or JSON structures) and deteriorate retrieval accuracy.

### Should image-only chunks be embedded?
*   **Yes, image-only chunks should be embedded.**
*   *Rationale*:
    1.  **Retrieval Visibility**: If left unembedded (with `embedding = None`), they are completely omitted from all vector-based retrieves.
    2.  **Semantic Context via Headings**: Image-only chunks without text or captions default to having `text = heading_context` (the parent section/topic title). Embedding this allows the chunk to be returned when a query closely matches the section heading (e.g., retrieving the diagram for "Bonding in Carbon" when the user asks about carbon bonding).
    3.  **Check Constraint Integrity**: The database schema enforces a constraint (`retrieval_chunk_embedding_profile_complete`) requiring all embedding profile fields to be populated together or empty together. Having a subset of chunks in a document without embeddings breaks document-level retrieval symmetry.
    4.  **Future-Proofing**: Embedding them now sets a clear baseline. When future work implements multimodal captioning or OCR to populate `element.text`, the embedding pipeline will automatically process the richer description without requiring database schema or code modifications.

---

## 6. Recommended First Evaluation Set (3-5 Models + 1 Provider)

To evaluate the dense retrieval quality against the lexical-only baseline on the `jesc104` evaluation set, we recommend the following evaluation set:

1.  **nomic-embed-text-v1.5** (768d, Apache 2.0)
    *   *Why*: Best-in-class lightweight local model, long-context support, and supports Matryoshka dimension truncation (we can test both 768d and 256d configurations).
2.  **BAAI/bge-large-en-v1.5** (1024d, MIT)
    *   *Why*: Standard industry benchmark with zero prefix complexity.
3.  **Alibaba-NLP/gte-Qwen2-1.5B-instruct** (1536d, Apache 2.0)
    *   *Why*: Heavyweight candidate representing the quality ceiling for complex scientific and chemical reasoning.
4.  **Snowflake/snowflake-arctic-embed-m-v1.5** (768d, Apache 2.0)
    *   *Why*: Extremely efficient retrieval-centric model (109M params), suitable for low-resource environments.
5.  **OpenAI text-embedding-3-large** (1024d/768d truncated, Provider Candidate)
    *   *Why*: Establishes the hosted provider benchmark for cost/quality analysis.

---

## 7. Next Implementation Steps for Codex

To implement the evaluation gate and populate the database without violating Rule 13, Codex should execute the following steps:

1.  **Update `CONTEXT.md`**: Define the schema and names of the selected embedding profiles.
2.  **Implement concrete `EmbeddingClient` classes**:
    *   Create `SentenceTransformersEmbeddingClient` in `backend/corpus/embeddings.py` (or a dedicated `embeddings_client.py`) utilizing PyTorch's `mps` device.
    *   Create `OllamaEmbeddingClient` to enable easy local microservice deployment.
3.  **Create Django Migration for Production Indexes**:
    *   Write a migration that creates partial HNSW indexes on `corpus_retrievalchunk` matching the selected evaluation model dimensions. For example:
      ```python
      # Migration definition for Nomic's 768 dimensions
      from pgvector.django import HnswIndex
      # Add HNSW Cosine Index for selected profile:
      HnswIndex(
          name="retrieval_chunk_nomic_v1_5_hnsw",
          fields=["embedding"],
          opclasses=["vector_cosine_ops"],
          condition=Q(
              embedding_model="nomic-embed-text-v1.5",
              embedding_version="v1.5",
              embedding_dimensions=768
          )
      )
      ```
4.  **Create `populate_textbook_embeddings` Management Command**:
    *   Write a Django command to populate the database. It should accept `--model` and instantiate the correct `EmbeddingClient` before invoking `RetrievalChunkEmbeddingPopulator`.
5.  **Extend `benchmark_textbook_retrieval`**:
    *   Integrate `PostgresVectorTextbookRetriever` alongside the existing `PostgresTextbookRetriever`.
    *   Implement **Reciprocal Rank Fusion (RRF)** for hybrid retrieval scoring (lexical + dense) as planned for Issue #175.
    *   Output comparative stats (Lexical vs. Dense vs. Hybrid) on the `jesc104_lexical_retrieval_evaluation.json` suite.

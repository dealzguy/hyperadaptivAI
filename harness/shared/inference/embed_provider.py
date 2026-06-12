"""LiteLLM-backed embedding provider — routes to local Ollama only.

Default model is nomic-embed-text at 768 dimensions (pgvector column size).
See docs/MEMORY.md for embedding dimension rationale.
TODO(liquid: embedding dimension and model — first real corpus, Phase E)
"""
from __future__ import annotations

import os

import litellm

from harness.shared.contracts.infer import _guard_model_id

OLLAMA_BASE_URL: str = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

# Default embedding model — 768-dim, matches knowledge_doc.embedding column.
DEFAULT_EMBED_MODEL = "ollama/nomic-embed-text"


async def embed(
    texts: list[str],
    model_id: str = DEFAULT_EMBED_MODEL,
) -> list[list[float]]:
    """Return one embedding vector per input text.  Rejects cloud model IDs."""
    _guard_model_id(model_id)

    resp = await litellm.aembedding(
        model=model_id,
        input=texts,
        api_base=OLLAMA_BASE_URL,
        num_retries=0,
    )
    return [item["embedding"] for item in resp.data]

import numpy as np
from openai import OpenAI

from ..core.config import settings


# Initialize OpenAI client
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def get_embedding(text: str) -> np.ndarray:
    """
    Get embedding for a text string using OpenAI API.

    Args:
        text: Text to embed

    Returns:
        Normalized embedding vector as numpy array
    """
    client = _get_client()

    response = client.embeddings.create(
        model=settings.embedding_model,
        input=text.strip()
    )

    embedding = np.array(response.data[0].embedding, dtype=np.float32)

    # Normalize for cosine similarity (FAISS IndexFlatIP)
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm

    return embedding

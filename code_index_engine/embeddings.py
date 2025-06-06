import hashlib
import numpy as np
from typing import List


def embed_text(text: str, dim: int = 32) -> List[float]:
    """Generate a deterministic embedding vector from text using SHA256."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    # Repeat digest to cover dim*4 bytes (float32)
    while len(digest) < dim * 4:
        digest += hashlib.sha256(digest).digest()
    floats = np.frombuffer(digest[: dim * 4], dtype=np.uint32)
    normalized = floats / floats.max()
    return normalized.astype(float).tolist()

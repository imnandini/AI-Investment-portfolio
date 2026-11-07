"""Offline feature vectors by default; optional locally provisioned semantic model."""
import hashlib
import math
import re
from functools import lru_cache
from typing import Protocol
from app.core.config import Settings

STOP = set("the a an of and or is are was were to in for on at with from what how does did it this that company report annual".split())


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP and len(t) > 1]


class EmbeddingProvider(Protocol):
    model: str
    def embed(self, text: str) -> list[float]: ...


class HashEmbedding:
    # This is a lexical feature embedding, never advertised as semantic understanding.
    model = "hash-lexical-v1-384"

    def embed(self, text):
        vector = [0.0] * 384
        for token in tokens(text):
            digest = hashlib.sha256(token.encode()).digest()
            vector[int.from_bytes(digest[:4], "big") % 384] += 1 if digest[4] % 2 else -1
        norm = math.sqrt(sum(v*v for v in vector)) or 1
        return [v / norm for v in vector]


class SentenceEmbedding:
    def __init__(self, path):
        from sentence_transformers import SentenceTransformer
        self.encoder = SentenceTransformer(path, local_files_only=True, trust_remote_code=False)
        self.model = f"sentence-transformers:{path}"
        if self.encoder.get_sentence_embedding_dimension() != 384:
            raise ValueError("Embedding model must produce 384 dimensions.")

    def embed(self, text):
        return self.encoder.encode(text, normalize_embeddings=True).tolist()


@lru_cache(maxsize=4)
def _provider(kind, path):
    if kind == "none":
        return None
    return SentenceEmbedding(path) if kind == "sentence_transformers" else HashEmbedding()


def create_embeddings(settings: Settings):
    return _provider(settings.embedding_provider, settings.embedding_model_path)

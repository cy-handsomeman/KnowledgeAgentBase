from functools import lru_cache

from sentence_transformers import SentenceTransformer

from core.settings import settings

QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(settings.embedding_model)


class EmbeddingService:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = _get_model().encode(texts, normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        vector = _get_model().encode([QUERY_PREFIX + text], normalize_embeddings=True)[0]
        return vector.tolist()

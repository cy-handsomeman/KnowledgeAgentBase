from functools import lru_cache
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from core.settings import settings

COLLECTION_NAME = "document_chunks"


@lru_cache(maxsize=1)
def _get_collection():
    Path(settings.chroma_dir).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=settings.chroma_dir,
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    return client.get_or_create_collection(name=COLLECTION_NAME)


def upsert_chunks(
    ids: list[str],
    contents: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict],
) -> None:
    _get_collection().upsert(
        ids=ids,
        documents=contents,
        embeddings=embeddings,
        metadatas=metadatas,
    )


def delete_document_vectors(document_id: int) -> None:
    _get_collection().delete(where={"document_id": document_id})


def count_vectors() -> int:
    return _get_collection().count()


def search_chunks(
    query_embedding: list[float],
    knowledge_base_id: int,
    limit: int = 5,
) -> list[dict]:
    results = _get_collection().query(
        query_embeddings=[query_embedding],
        n_results=limit,
        where={"knowledge_base_id": knowledge_base_id},
    )

    matches = []
    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    for index, chunk_id in enumerate(ids):
        matches.append(
            {
                "vector_id": chunk_id,
                "content": documents[index],
                "metadata": metadatas[index],
                "distance": distances[index],
            }
        )
    return matches

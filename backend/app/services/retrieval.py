from sqlalchemy.orm import Session

from models.document import Document, DocumentChunk
from schemas.search import SearchMatch
from services.embedding import EmbeddingService
from services.permissions import can_access_document
from services.vector_store import search_chunks

TOP_K = 5


def retrieve_matches(
    db: Session,
    user_id: int,
    knowledge_base_id: int,
    question: str,
    limit: int = TOP_K,
) -> list[SearchMatch]:
    query_vector = EmbeddingService().embed_query(question)
    raw_matches = search_chunks(query_vector, knowledge_base_id, limit=limit)

    matches = []
    for item in raw_matches:
        metadata = item["metadata"] or {}
        chunk_id = metadata.get("chunk_id")
        if chunk_id is None:
            continue

        chunk = db.get(DocumentChunk, int(chunk_id))
        if chunk is None:
            continue

        document = db.get(Document, chunk.document_id)
        if document is None or document.knowledge_base_id != knowledge_base_id:
            continue

        if not can_access_document(db, user_id, document.id):
            continue

        distance = float(item["distance"])
        # Embeddings are unit-normalized and Chroma's default L2 distance is
        # squared Euclidean distance, so cosine similarity is 1 - distance / 2.
        score = max(0.0, min(1.0, 1 - distance / 2))

        matches.append(
            SearchMatch(
                document_id=document.id,
                document_title=document.title,
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                content=item["content"],
                score=round(score, 4),
            )
        )

    return matches

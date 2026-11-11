CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def split_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def chunk_pages(pages: list[tuple[int, str]]) -> list[tuple[str, int | None]]:
    result = []
    for page_number, text in pages:
        for chunk in split_text(text):
            result.append((chunk, page_number))
    return result

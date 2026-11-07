import re


def chunk_pages(pages: list[tuple[int, str]], size: int = 1600, overlap: int = 200):
    """Keep pages and short paragraphs/tables together; split oversized blocks at line boundaries."""
    if size < 1 or not 0 <= overlap < size:
        raise ValueError("Invalid chunk size or overlap.")
    for page, text in pages:
        text = text.replace("\x00", "")
        start = 0
        ordinal = 0
        while start < len(text):
            end = min(start + size, len(text))
            if end < len(text):
                boundary = text.rfind("\n\n", start + size // 2, end)
                if boundary < 0:
                    boundary = text.rfind("\n", start + size // 2, end)
                if boundary >= 0:
                    end = boundary
            passage = text[start:end].strip()
            if passage:
                yield page, ordinal, passage
                ordinal += 1
            if end == len(text):
                break
            start = max(start + 1, end - overlap)

from typing import List

def split_text(text: str, chunk_size=1000, overlap: int=100) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
        return chunks


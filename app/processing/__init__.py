"""
Document Processing

Text splitting and chunking utilities:
- split_text: Basic character-based splitting
- SemanticChunker: Semantic similarity-based chunking
"""
from app.processing.text_splitter import split_text
from app.processing.semantic_chunker import SemanticChunker, SemanticChunk

__all__ = [
    'split_text',
    'SemanticChunker',
    'SemanticChunk',
]

"""
Semantic Chunker

Creates document chunks based on semantic similarity rather than
fixed character counts. This produces more coherent chunks that
respect topic boundaries.

Uses a lightweight embedding model for fast local inference during chunking.
"""
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
import hashlib
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SemanticChunk:
    """A semantically coherent chunk of text"""
    text: str
    chunk_id: str
    page_numbers: List[int]  # Pages this chunk spans
    element_types: List[str]  # Types of elements in this chunk
    metadata: Dict[str, Any] = field(default_factory=dict)
    document_id: Optional[int] = None  # For Qdrant deletion
    text_hash: str = field(init=False)

    def __post_init__(self):
        self.text_hash = hashlib.sha256(self.text.encode()).hexdigest()


class SemanticChunker:
    """
    Chunks documents based on semantic similarity between elements.

    Algorithm:
    1. Get embeddings for each element
    2. Compute similarity between consecutive elements
    3. Split when similarity drops below threshold
    4. Merge small chunks with neighbors
    5. Split large chunks at sentence boundaries
    """

    def __init__(
        self,
        similarity_threshold: float = 0.65,
        min_chunk_size: int = 200,
        max_chunk_size: int = 1500,
        model_name: str = "all-MiniLM-L6-v2",  # Fast local model for chunking
    ):
        """
        Initialize the semantic chunker.

        Args:
            similarity_threshold: Split when cosine similarity drops below this
            min_chunk_size: Minimum characters per chunk (merge smaller)
            max_chunk_size: Maximum characters per chunk (split larger)
            model_name: Sentence transformers model for similarity
        """
        self.similarity_threshold = similarity_threshold
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        """Lazy load the sentence transformer model"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading chunking model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
            except ImportError:
                raise ImportError("sentence-transformers required for semantic chunking")
        return self._model

    def chunk_elements(
        self,
        elements: List[Any],  # List of DocumentElement
        file_name: str,
        document_id: Optional[int] = None,
    ) -> List[SemanticChunk]:
        """
        Chunk document elements semantically.

        Args:
            elements: List of DocumentElement from UnstructuredPDFLoader
            file_name: Original filename for chunk IDs
            document_id: Database document ID for Qdrant reference

        Returns:
            List of SemanticChunk objects
        """
        if not elements:
            return []

        # Extract texts and metadata
        texts = [e.text for e in elements]
        pages = [e.page_number or 1 for e in elements]
        types = [e.element_type for e in elements]

        # Get embeddings for all elements
        logger.info(f"Computing embeddings for {len(texts)} elements")
        embeddings = self.model.encode(texts, show_progress_bar=False)

        # Find split points based on similarity
        split_indices = self._find_split_points(embeddings)
        split_indices.append(len(elements))  # Add end point

        # Create chunks from splits
        chunks = []
        start_idx = 0
        chunk_num = 0

        for end_idx in split_indices:
            if start_idx >= end_idx:
                continue

            # Combine elements into chunk
            chunk_texts = texts[start_idx:end_idx]
            chunk_pages = list(set(pages[start_idx:end_idx]))
            chunk_types = list(set(types[start_idx:end_idx]))

            combined_text = "\n\n".join(chunk_texts)

            # Handle chunk size constraints
            if len(combined_text) < self.min_chunk_size and chunks:
                # Merge with previous chunk
                prev_chunk = chunks[-1]
                merged_text = prev_chunk.text + "\n\n" + combined_text
                if len(merged_text) <= self.max_chunk_size:
                    chunks[-1] = SemanticChunk(
                        text=merged_text,
                        chunk_id=prev_chunk.chunk_id,
                        page_numbers=sorted(set(prev_chunk.page_numbers + chunk_pages)),
                        element_types=list(set(prev_chunk.element_types + chunk_types)),
                        document_id=document_id,
                    )
                    start_idx = end_idx
                    continue

            # Split large chunks
            if len(combined_text) > self.max_chunk_size:
                sub_chunks = self._split_large_chunk(
                    combined_text, chunk_pages, chunk_types,
                    file_name, chunk_num, document_id
                )
                chunks.extend(sub_chunks)
                chunk_num += len(sub_chunks)
            else:
                chunk_id = f"{file_name}_semantic_{chunk_num}"
                chunks.append(SemanticChunk(
                    text=combined_text,
                    chunk_id=chunk_id,
                    page_numbers=sorted(chunk_pages),
                    element_types=chunk_types,
                    document_id=document_id,
                ))
                chunk_num += 1

            start_idx = end_idx

        logger.info(f"Created {len(chunks)} semantic chunks from {len(elements)} elements")
        return chunks

    def chunk_text(
        self,
        text: str,
        file_name: str,
        page_number: int = 1,
        document_id: Optional[int] = None,
    ) -> List[SemanticChunk]:
        """
        Chunk plain text semantically (for simpler use cases).

        Splits text into sentences, then groups by similarity.

        Args:
            text: Plain text to chunk
            file_name: Filename for chunk IDs
            page_number: Page number for metadata
            document_id: Database document ID

        Returns:
            List of SemanticChunk objects
        """
        # Split into sentences
        sentences = self._split_into_sentences(text)
        if not sentences:
            return []

        # Get embeddings
        embeddings = self.model.encode(sentences, show_progress_bar=False)

        # Find split points
        split_indices = self._find_split_points(embeddings)
        split_indices.append(len(sentences))

        # Create chunks
        chunks = []
        start_idx = 0
        chunk_num = 0

        for end_idx in split_indices:
            if start_idx >= end_idx:
                continue

            chunk_text = " ".join(sentences[start_idx:end_idx])

            # Handle size constraints
            if len(chunk_text) > self.max_chunk_size:
                sub_chunks = self._split_large_chunk(
                    chunk_text, [page_number], ["NarrativeText"],
                    file_name, chunk_num, document_id
                )
                chunks.extend(sub_chunks)
                chunk_num += len(sub_chunks)
            elif len(chunk_text) >= self.min_chunk_size or not chunks:
                chunk_id = f"{file_name}_semantic_{chunk_num}"
                chunks.append(SemanticChunk(
                    text=chunk_text,
                    chunk_id=chunk_id,
                    page_numbers=[page_number],
                    element_types=["NarrativeText"],
                    document_id=document_id,
                ))
                chunk_num += 1
            elif chunks:
                # Merge with previous
                prev = chunks[-1]
                chunks[-1] = SemanticChunk(
                    text=prev.text + " " + chunk_text,
                    chunk_id=prev.chunk_id,
                    page_numbers=prev.page_numbers,
                    element_types=prev.element_types,
                    document_id=document_id,
                )

            start_idx = end_idx

        return chunks

    def _find_split_points(self, embeddings) -> List[int]:
        """
        Find indices where semantic similarity drops below threshold.

        Args:
            embeddings: numpy array of embeddings

        Returns:
            List of split point indices
        """
        import numpy as np

        if len(embeddings) < 2:
            return []

        split_points = []

        for i in range(1, len(embeddings)):
            # Cosine similarity between consecutive elements
            similarity = np.dot(embeddings[i-1], embeddings[i]) / (
                np.linalg.norm(embeddings[i-1]) * np.linalg.norm(embeddings[i])
            )

            if similarity < self.similarity_threshold:
                split_points.append(i)

        return split_points

    def _split_large_chunk(
        self,
        text: str,
        page_numbers: List[int],
        element_types: List[str],
        file_name: str,
        chunk_num: int,
        document_id: Optional[int],
    ) -> List[SemanticChunk]:
        """
        Split a chunk that exceeds max_chunk_size at sentence boundaries.

        Args:
            text: Text to split
            page_numbers: Pages this text spans
            element_types: Element types in this text
            file_name: For chunk IDs
            chunk_num: Starting chunk number
            document_id: Database document ID

        Returns:
            List of SemanticChunk objects
        """
        sentences = self._split_into_sentences(text)
        chunks = []
        current_text = ""
        sub_num = 0

        for sentence in sentences:
            if len(current_text) + len(sentence) + 1 > self.max_chunk_size:
                if current_text:
                    chunk_id = f"{file_name}_semantic_{chunk_num}_{sub_num}"
                    chunks.append(SemanticChunk(
                        text=current_text.strip(),
                        chunk_id=chunk_id,
                        page_numbers=page_numbers,
                        element_types=element_types,
                        document_id=document_id,
                    ))
                    sub_num += 1
                current_text = sentence
            else:
                current_text = current_text + " " + sentence if current_text else sentence

        # Add remaining text
        if current_text.strip():
            chunk_id = f"{file_name}_semantic_{chunk_num}_{sub_num}"
            chunks.append(SemanticChunk(
                text=current_text.strip(),
                chunk_id=chunk_id,
                page_numbers=page_numbers,
                element_types=element_types,
                document_id=document_id,
            ))

        return chunks

    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences.

        Args:
            text: Text to split

        Returns:
            List of sentences
        """
        import re

        # Split on sentence-ending punctuation followed by space or newline
        # Handles abbreviations better than simple split
        sentences = re.split(r'(?<=[.!?])\s+', text)

        # Filter empty and very short sentences
        return [s.strip() for s in sentences if len(s.strip()) > 10]

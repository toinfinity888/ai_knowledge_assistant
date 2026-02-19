"""
Unstructured PDF Loader

Uses Unstructured.io for advanced PDF parsing with:
- Table extraction (preserved as markdown)
- Heading hierarchy preservation
- Better handling of complex layouts

This loader is used for new document uploads via the admin interface.
The original pdf_loader.py is kept for backwards compatibility.
"""
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field
import hashlib
import logging

from app.models.text_chunk import TextChunk
from app.loaders.base import BaseLoader

logger = logging.getLogger(__name__)


@dataclass
class DocumentElement:
    """Represents a parsed element from the document"""
    text: str
    element_type: str  # 'Title', 'NarrativeText', 'Table', 'ListItem', etc.
    page_number: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class UnstructuredPDFLoader(BaseLoader):
    """
    PDF loader using Unstructured.io for advanced parsing.

    Features:
    - Extracts tables as markdown
    - Preserves document structure (headings, sections)
    - Better handling of multi-column layouts
    - Extracts metadata (titles, headings hierarchy)
    """

    def __init__(
        self,
        strategy: str = "hi_res",
        infer_table_structure: bool = True,
        include_page_breaks: bool = True,
        chunking_strategy: Optional[str] = None,  # None = don't chunk in unstructured
        max_characters: int = 1500,
        overlap: int = 150,
    ):
        """
        Initialize the loader.

        Args:
            strategy: Parsing strategy ('hi_res', 'fast', 'ocr_only', 'auto')
            infer_table_structure: Whether to extract table structure
            include_page_breaks: Whether to track page boundaries
            chunking_strategy: 'by_title' or None (we use our own semantic chunker)
            max_characters: Max chars per chunk if using built-in chunking
            overlap: Overlap between chunks if using built-in chunking
        """
        self.strategy = strategy
        self.infer_table_structure = infer_table_structure
        self.include_page_breaks = include_page_breaks
        self.chunking_strategy = chunking_strategy
        self.max_characters = max_characters
        self.overlap = overlap

    def load(self, path: Path) -> List[TextChunk]:
        """
        Load a PDF and return text chunks.

        For single file uploads, use load_with_metadata() for richer output.

        Args:
            path: Path to PDF file or directory

        Returns:
            List of TextChunk objects
        """
        path = Path(path)

        if path.is_dir():
            chunks = []
            for pdf_path in path.rglob("*.pdf"):
                chunks.extend(self._load_single_file(pdf_path))
            return chunks
        else:
            return self._load_single_file(path)

    def _load_single_file(self, pdf_path: Path) -> List[TextChunk]:
        """Load a single PDF file"""
        try:
            from unstructured.partition.pdf import partition_pdf
        except ImportError:
            logger.error("unstructured[pdf] not installed. Run: pip install 'unstructured[pdf]'")
            raise ImportError("unstructured[pdf] required for PDF parsing")

        logger.info(f"Loading PDF with Unstructured: {pdf_path.name}")

        try:
            # Parse PDF with Unstructured
            elements = partition_pdf(
                filename=str(pdf_path),
                strategy=self.strategy,
                infer_table_structure=self.infer_table_structure,
                include_page_breaks=self.include_page_breaks,
            )

            last_modified = datetime.fromtimestamp(pdf_path.stat().st_mtime)
            file_name = pdf_path.name
            chunks = []

            # Group elements by page for chunk IDs
            current_page = 1
            chunk_index = 0

            for element in elements:
                # Track page numbers
                if hasattr(element, 'metadata') and hasattr(element.metadata, 'page_number'):
                    current_page = element.metadata.page_number or current_page

                # Get text content
                text = str(element).strip()
                if not text:
                    continue

                # Handle tables specially - convert to markdown
                element_type = type(element).__name__
                if element_type == 'Table':
                    text = self._table_to_markdown(element)

                # Create chunk
                chunk_id = f"{file_name}_p{current_page}_chunk{chunk_index}"
                chunk = TextChunk(
                    text=text,
                    source=pdf_path,
                    page=current_page,
                    chunk_id=chunk_id,
                    file_name=file_name,
                    last_modified=last_modified,
                    file_type='pdf'
                )
                chunks.append(chunk)
                chunk_index += 1

            logger.info(f"Extracted {len(chunks)} chunks from {pdf_path.name}")
            return chunks

        except Exception as e:
            logger.error(f"Error loading PDF {pdf_path.name}: {e}")
            raise

    def load_with_elements(self, path: Path) -> List[DocumentElement]:
        """
        Load PDF and return structured elements (for semantic chunking).

        This method returns richer element data that can be used by
        the semantic chunker to create better chunk boundaries.

        Args:
            path: Path to PDF file

        Returns:
            List of DocumentElement with type and metadata
        """
        try:
            from unstructured.partition.pdf import partition_pdf
        except ImportError:
            raise ImportError("unstructured[pdf] required")

        path = Path(path)
        logger.info(f"Loading PDF elements: {path.name}")

        elements = partition_pdf(
            filename=str(path),
            strategy=self.strategy,
            infer_table_structure=self.infer_table_structure,
            include_page_breaks=self.include_page_breaks,
        )

        result = []
        for element in elements:
            element_type = type(element).__name__

            # Get text
            if element_type == 'Table':
                text = self._table_to_markdown(element)
            else:
                text = str(element).strip()

            if not text:
                continue

            # Extract metadata
            metadata = {}
            if hasattr(element, 'metadata'):
                meta = element.metadata
                if hasattr(meta, 'page_number'):
                    metadata['page_number'] = meta.page_number
                if hasattr(meta, 'coordinates'):
                    metadata['coordinates'] = meta.coordinates
                if hasattr(meta, 'parent_id'):
                    metadata['parent_id'] = meta.parent_id

            result.append(DocumentElement(
                text=text,
                element_type=element_type,
                page_number=metadata.get('page_number'),
                metadata=metadata
            ))

        logger.info(f"Extracted {len(result)} elements from {path.name}")
        return result

    def _table_to_markdown(self, table_element) -> str:
        """
        Convert a table element to markdown format.

        Args:
            table_element: Unstructured Table element

        Returns:
            Markdown-formatted table string
        """
        # Try to get HTML and convert to markdown
        if hasattr(table_element, 'metadata') and hasattr(table_element.metadata, 'text_as_html'):
            html = table_element.metadata.text_as_html
            if html:
                return self._html_table_to_markdown(html)

        # Fallback to plain text
        return str(table_element)

    def _html_table_to_markdown(self, html: str) -> str:
        """
        Convert HTML table to markdown format.

        Args:
            html: HTML table string

        Returns:
            Markdown table string
        """
        try:
            from html.parser import HTMLParser

            class TableParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.rows = []
                    self.current_row = []
                    self.current_cell = ""
                    self.in_cell = False

                def handle_starttag(self, tag, attrs):
                    if tag in ('td', 'th'):
                        self.in_cell = True
                        self.current_cell = ""

                def handle_endtag(self, tag):
                    if tag in ('td', 'th'):
                        self.in_cell = False
                        self.current_row.append(self.current_cell.strip())
                    elif tag == 'tr':
                        if self.current_row:
                            self.rows.append(self.current_row)
                        self.current_row = []

                def handle_data(self, data):
                    if self.in_cell:
                        self.current_cell += data

            parser = TableParser()
            parser.feed(html)

            if not parser.rows:
                return html

            # Build markdown table
            lines = []
            for i, row in enumerate(parser.rows):
                lines.append("| " + " | ".join(row) + " |")
                if i == 0:  # Add header separator
                    lines.append("| " + " | ".join(["---"] * len(row)) + " |")

            return "\n".join(lines)

        except Exception as e:
            logger.warning(f"Failed to convert table to markdown: {e}")
            return html

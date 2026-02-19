"""
Document Service

Handles document upload, processing, and management for the knowledge base.

Workflow:
1. upload_document() - Save file to disk, create DB record
2. process_document() - Parse PDF, chunk, embed, store in Qdrant
3. get_documents() - List documents with pagination
4. delete_document() - Remove from DB and Qdrant
"""
import os
import uuid
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

from app.models.document import Document, DocumentStatus
from app.database.postgresql_session import get_db_session
from app.loaders.unstructured_loader import UnstructuredPDFLoader
from app.processing.semantic_chunker import SemanticChunker
from app.models.embedded import EmbeddedChunk

logger = logging.getLogger(__name__)

# Default upload directory
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads/documents"))


class DocumentService:
    """
    Service for managing knowledge base documents.

    Handles the full lifecycle of documents:
    - Upload and storage
    - Parsing and chunking
    - Embedding and vector storage
    - Listing and deletion
    """

    def __init__(
        self,
        upload_dir: Path = UPLOAD_DIR,
        embedder=None,
        vector_store=None,
    ):
        """
        Initialize the document service.

        Args:
            upload_dir: Directory for storing uploaded files
            embedder: Embedding model (injected for testing)
            vector_store: Vector store (injected for testing)
        """
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

        self._embedder = embedder
        self._vector_store = vector_store

        # Lazy-loaded components
        self._pdf_loader = None
        self._chunker = None

    @property
    def pdf_loader(self):
        """Lazy load PDF loader"""
        if self._pdf_loader is None:
            self._pdf_loader = UnstructuredPDFLoader(
                strategy="hi_res",
                infer_table_structure=True,
            )
        return self._pdf_loader

    @property
    def chunker(self):
        """Lazy load semantic chunker"""
        if self._chunker is None:
            self._chunker = SemanticChunker(
                similarity_threshold=0.65,
                min_chunk_size=200,
                max_chunk_size=1500,
            )
        return self._chunker

    @property
    def embedder(self):
        """Get embedder (lazy load if not injected)"""
        if self._embedder is None:
            from app.embedding.openai_embedder import OpenAIEmbedder
            from app.config.openai_config import OpenAISetting
            settings = OpenAISetting()
            self._embedder = OpenAIEmbedder(settings)
        return self._embedder

    @property
    def vector_store(self):
        """Get vector store (lazy load if not injected)"""
        if self._vector_store is None:
            from app.vector_store.qdrant_vector_store import QdrantVectorStore
            from app.config.qdrant_config import QdrantSetting
            settings = QdrantSetting()
            self._vector_store = QdrantVectorStore(settings)
        return self._vector_store

    def upload_document(
        self,
        file_content: bytes,
        original_filename: str,
        company_id: int,
        user_id: Optional[int] = None,
        mime_type: str = "application/pdf",
    ) -> Document:
        """
        Upload a document and create a database record.

        Args:
            file_content: Raw file bytes
            original_filename: User's original filename
            company_id: Company ID for multi-tenant isolation
            user_id: Optional user ID for audit
            mime_type: MIME type of the file

        Returns:
            Document record (status=pending)

        Raises:
            ValueError: If file is invalid
        """
        # Validate
        if not file_content:
            raise ValueError("Empty file content")
        if not original_filename.lower().endswith('.pdf'):
            raise ValueError("Only PDF files are supported")

        # Generate unique filename
        file_uuid = str(uuid.uuid4())
        stored_filename = f"{file_uuid}.pdf"
        file_path = self.upload_dir / str(company_id) / stored_filename

        # Create company directory if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Save file
        logger.info(f"Saving document: {original_filename} -> {file_path}")
        with open(file_path, "wb") as f:
            f.write(file_content)

        # Create database record
        with get_db_session() as db:
            document = Document(
                company_id=company_id,
                filename=stored_filename,
                original_filename=original_filename,
                file_size=len(file_content),
                mime_type=mime_type,
                status=DocumentStatus.PENDING,
                created_by_user_id=user_id,
                created_at=datetime.utcnow(),
            )
            db.add(document)
            db.commit()
            db.refresh(document)

            logger.info(f"Created document record: id={document.id}, filename={original_filename}")
            return document

    def process_document(self, document_id: int) -> Document:
        """
        Process a pending document: parse, chunk, embed, store.

        Args:
            document_id: Database document ID

        Returns:
            Updated Document record

        Raises:
            ValueError: If document not found
            Exception: If processing fails
        """
        with get_db_session() as db:
            document = db.query(Document).filter(Document.id == document_id).first()
            if not document:
                raise ValueError(f"Document {document_id} not found")

            # Update status
            document.status = DocumentStatus.PROCESSING
            db.commit()

            try:
                # Get file path
                file_path = self.upload_dir / str(document.company_id) / document.filename

                if not file_path.exists():
                    raise FileNotFoundError(f"File not found: {file_path}")

                logger.info(f"Processing document: {document.original_filename}")

                # Parse PDF with Unstructured
                elements = self.pdf_loader.load_with_elements(file_path)
                logger.info(f"Extracted {len(elements)} elements from PDF")

                # Semantic chunking
                chunks = self.chunker.chunk_elements(
                    elements=elements,
                    file_name=document.original_filename,
                    document_id=document.id,
                )
                logger.info(f"Created {len(chunks)} semantic chunks")

                # Embed chunks
                embedded_chunks = self._embed_chunks(
                    chunks=chunks,
                    company_id=document.company_id,
                    document_id=document.id,
                    source_path=file_path,
                    original_filename=document.original_filename,
                )
                logger.info(f"Embedded {len(embedded_chunks)} chunks")

                # Store in Qdrant
                self.vector_store.upsert_with_document_id(
                    chunks=embedded_chunks,
                    document_id=document.id,
                )
                logger.info(f"Stored {len(embedded_chunks)} vectors in Qdrant")

                # Update document record
                document.status = DocumentStatus.COMPLETED
                document.chunk_count = len(embedded_chunks)
                document.processed_at = datetime.utcnow()
                document.error_message = None
                db.commit()

                logger.info(f"Document processed successfully: id={document.id}")
                return document

            except Exception as e:
                logger.error(f"Error processing document {document_id}: {e}")
                document.status = DocumentStatus.FAILED
                document.error_message = str(e)[:1000]  # Truncate error message
                db.commit()
                raise

    def _embed_chunks(
        self,
        chunks: List[Any],  # SemanticChunk
        company_id: int,
        document_id: int,
        source_path: Path,
        original_filename: str,
    ) -> List[EmbeddedChunk]:
        """
        Embed semantic chunks.

        Args:
            chunks: List of SemanticChunk objects
            company_id: Company ID for multi-tenancy
            document_id: Document ID for deletion
            source_path: Path to source file
            original_filename: Original user-provided filename

        Returns:
            List of EmbeddedChunk objects
        """
        embedded = []

        for chunk in chunks:
            # Get embedding
            from app.models.query import Query
            query = Query(text=chunk.text)
            embedding = self.embedder.embed_query(query).embedding

            embedded_chunk = EmbeddedChunk(
                id=chunk.chunk_id,
                embedding=embedding,
                text=chunk.text,
                source=source_path,
                file_name=original_filename,  # Use original filename for display
                page=chunk.page_numbers[0] if chunk.page_numbers else None,
                file_type="pdf",
                text_hash=chunk.text_hash,
                company_id=company_id,
                document_id=document_id,
            )
            embedded.append(embedded_chunk)

        return embedded

    def get_documents(
        self,
        company_id: int,
        page: int = 1,
        per_page: int = 20,
        status: Optional[DocumentStatus] = None,
    ) -> Tuple[List[Document], int]:
        """
        Get documents for a company with pagination.

        Args:
            company_id: Company ID
            page: Page number (1-indexed)
            per_page: Items per page
            status: Optional status filter

        Returns:
            Tuple of (documents list, total count)
        """
        with get_db_session() as db:
            query = db.query(Document).filter(Document.company_id == company_id)

            if status:
                query = query.filter(Document.status == status)

            # Get total count
            total = query.count()

            # Get paginated results
            documents = (
                query
                .order_by(Document.created_at.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
                .all()
            )

            return documents, total

    def get_document(self, document_id: int, company_id: int) -> Optional[Document]:
        """
        Get a single document by ID.

        Args:
            document_id: Document ID
            company_id: Company ID for access control

        Returns:
            Document or None
        """
        with get_db_session() as db:
            return db.query(Document).filter(
                Document.id == document_id,
                Document.company_id == company_id,
            ).first()

    def delete_document(self, document_id: int, company_id: int) -> bool:
        """
        Delete a document and its vectors.

        Args:
            document_id: Document ID
            company_id: Company ID for access control

        Returns:
            True if deleted, False if not found

        Raises:
            Exception: If deletion fails
        """
        with get_db_session() as db:
            document = db.query(Document).filter(
                Document.id == document_id,
                Document.company_id == company_id,
            ).first()

            if not document:
                return False

            logger.info(f"Deleting document: id={document_id}, filename={document.original_filename}")

            # Delete vectors from Qdrant
            try:
                deleted_count = self.vector_store.delete_by_document_id(
                    document_id=document_id,
                    company_id=company_id,
                )
                logger.info(f"Deleted {deleted_count} vectors from Qdrant")
            except Exception as e:
                logger.error(f"Error deleting vectors: {e}")
                # Continue with file/DB deletion even if vector deletion fails

            # Delete file from disk
            file_path = self.upload_dir / str(company_id) / document.filename
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted file: {file_path}")

            # Delete database record
            db.delete(document)
            db.commit()

            logger.info(f"Document deleted: id={document_id}")
            return True

    def reprocess_document(self, document_id: int, company_id: int) -> Document:
        """
        Reprocess a failed document.

        Args:
            document_id: Document ID
            company_id: Company ID for access control

        Returns:
            Updated Document

        Raises:
            ValueError: If document not found or not in failed state
        """
        with get_db_session() as db:
            document = db.query(Document).filter(
                Document.id == document_id,
                Document.company_id == company_id,
            ).first()

            if not document:
                raise ValueError(f"Document {document_id} not found")

            if document.status != DocumentStatus.FAILED:
                raise ValueError(f"Document {document_id} is not in failed state")

            # Reset to pending
            document.status = DocumentStatus.PENDING
            document.error_message = None
            db.commit()

        # Process again
        return self.process_document(document_id)


# Singleton instance
_document_service: Optional[DocumentService] = None


def get_document_service() -> DocumentService:
    """Get the document service singleton."""
    global _document_service
    if _document_service is None:
        _document_service = DocumentService()
    return _document_service

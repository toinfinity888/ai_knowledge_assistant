"""
Document Loaders

Provides loaders for different document types:
- PDFLoader: Basic PDF loader using PyMuPDF (legacy)
- UnstructuredPDFLoader: Advanced PDF loader with table support
- JsonLoader: JSON document loader
"""
from app.loaders.base import BaseLoader
from app.loaders.pdf_loader import PDFLoader
from app.loaders.json_loader import JsonLoader
from app.loaders.unstructured_loader import UnstructuredPDFLoader, DocumentElement

__all__ = [
    'BaseLoader',
    'PDFLoader',
    'JsonLoader',
    'UnstructuredPDFLoader',
    'DocumentElement',
]

from pathlib import Path
from app.logging.logger import logger
from app.processing.text_splitter import split_text
import fitz # PyMuPDF
from ai_knowledge_assistant.app.models.text_chunk import TextChunk
from app.loaders.base import BaseLoader
from datetime import datetime
from typing import List, Union
class PDFLoader(BaseLoader):
    def load(self, path: str | Path) -> List[TextChunk]:
        path = Path(path)
        chunks = []

        if path.is_dir():
            pdf_files = path.rglob("*.pdf")
        else:
            pdf_files = [path] if path.is_file() and path.suffix.lower() == ".pdf" else []

        for pdf_path in pdf_files:
            try:
                doc = fitz.open(pdf_path)
                last_modified = datetime.fromtimestamp(pdf_path.stat().st_mtime)
                file_name = pdf_path.name
                file_type = 'pdf'

                for page_num, page in enumerate(doc, start=1):
                    text = page.get_text().strip()
                    if not text:
                        continue

                    for i, subtext in enumerate(split_text(text, chunk_size=1000, overlap=100)):
                        chunk_id = f"{file_name}_p{page_num}_chunk{i}"
                        chunk = TextChunk(
                            text=subtext,
                            source=pdf_path,
                            page=page_num,
                            chunk_id=chunk_id,
                            file_name=file_name,
                            last_modified=last_modified,
                            file_type=file_type
                        )
                        chunks.append(chunk)
            except Exception as e:
                logger.error(f"Error while loading PDF file {pdf_path.name}: {e}")
        return chunks

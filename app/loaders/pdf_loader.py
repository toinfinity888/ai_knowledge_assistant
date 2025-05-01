from pathlib import Path
from core.logger import logger
import fitz # PyMuPDF
from processing.text_chunk import TextChunk
from loaders.base import BaseLoader
from datetime import datetime
from typing import List

class PDFLoader(BaseLoader):
    def load(self, path: Path) -> List[TextChunk]:
        chunks = []
        try:
            doc = fitz.open(path)
            last_modified = datetime.fromtimestamp(path.stat().st_mtime)
            file_name = path.name
            file_type = 'pdf'

            for page_num, page in enumerate(doc, start=1):
                text = page.get_text().strip()
                if not text:
                    continue

                chunk_id = f"{file_name}_p{page_num}"
                chunk = TextChunk(
                    text=text,
                    source=path,
                    page=page_num,
                    chunk_id=chunk_id,
                    file_name=file_name,
                    last_modified=last_modified,
                    file_type=file_type
                )
                chunks.append(chunk)
        except Exception as e:
            logger.error(f"Error while loading PDF file {path.name}: {e}")

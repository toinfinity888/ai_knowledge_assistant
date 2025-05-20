from app.loaders.base import BaseLoader
from app.logging.logger import logger
from app.models.text_chunk import TextChunk
from pathlib import Path
from datetime import datetime
from typing import List, Union
import json

def split_into_chunks(text: str, max_length: int = 500) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_length
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end
    return chunks

class JsonLoader(BaseLoader):
    def load(self, path: Union[str, Path]) -> List[TextChunk]:
        path = Path(path)
        chunks: List[TextChunk] = []

        if path.is_dir():
            files = path.rglob("*.json")
        elif path.is_file() and path.suffix.lower() == ".json":
            files = [path]
        else:
            logger.warning(f"Path {path} is not a valid JSON file or directory.")
            return []

        for file_path in files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                    if not isinstance(data, list):
                        raise ValueError("Expected a JSON list of strings")

                    full_text = "\n".join([str(item) for item in data])
                    split_texts = split_into_chunks(full_text)
                    last_modified = datetime.fromtimestamp(file_path.stat().st_mtime)
                    file_name = file_path.name
                    file_type = "json"

                    for idx, text in enumerate(split_texts):
                        chunk_id = f"{file_name}_c{idx}"
                        chunk = TextChunk(
                            text=text,
                            source=file_path,
                            page=None,
                            chunk_id=chunk_id,
                            file_name=file_name,
                            last_modified=last_modified,
                            file_type=file_type
                        )
                        chunks.append(chunk)

            except Exception as e:
                logger.error(f"Error while loading JSON file {file_path.name}: {e}")

        return chunks
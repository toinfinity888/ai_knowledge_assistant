from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from datetime import datetime
import hashlib

@dataclass
class TextChunk:
    text: str
    source: Path                        # Path to the file
    page: Optional[int] = None          # Page in PDF
    chunk_id: Optional[str] = None      # ID unique of chunk

    # Metadata
    file_name: str                      # File name
    last_modified: Optional[datetime] = None    # Time of last change
    file_type: Optional[str] = None             # 'pdf', 'json', etr.
    text_hash: str = field(init=False)

    def __post_init__(self):
        self.text_hash = hashlib.sha256(self.text.encode()).hexdigest()
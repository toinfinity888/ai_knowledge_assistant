from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from datetime import datetime
import hashlib

@dataclass
class TextChunkForMvp:
    text: str
    source: Optional[Path]                      # Path to the file
    file_name: Optional[str] = None     # File name
    page: Optional[int] = None          # Page in PDF
    chunk_id: Optional[str] = None      # ID unique of chunk
    last_modified: Optional[datetime] = None    # Time of last change
    file_type: Optional[str] = None             # 'pdf', 'json', etr.
    text_hash: str = field(init=False)
    score: Optional[float] = None

    def __post_init__(self):
        self.text_hash = hashlib.sha256(self.text.encode()).hexdigest()
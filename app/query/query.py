from dataclasses import dataclass, Field
from typing import List, Optional
from datetime import datetime

@dataclass
class Query():
    text: str
    user_id: str = 'anonymous'
    filters: Optional[List[str]] = None
    mode: Optional[str] = 'Default'  # 'Simple', 'Deep', 'debug' etc.
    timestamp: datetime = datetime.utcnow()


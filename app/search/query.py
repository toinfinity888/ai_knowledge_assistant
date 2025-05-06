from dataclasses import dataclass, Field
from typing import List, Optional
from datetime import datetime

@dataclass
class Query():
    text: str
    filters: Optional[List[str]] = None
    user_id: str
    mode: Optional[str] = 'Default'  # 'Simple', 'Deep', 'debug' etc.
    timestamp: datetime = datetime.utcnow()


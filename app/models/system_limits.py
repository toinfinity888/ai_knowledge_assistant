"""
System Limits Model
Stores platform-wide limits for API usage and user management
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON
from app.models.base import Base


class SystemLimits(Base):
    """System-wide limits configuration"""
    __tablename__ = 'system_limits'

    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(JSON, nullable=False, default={})
    description = Column(String(500), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(Integer, nullable=True)  # user_id who last updated

    # Default limits structure:
    # {
    #     "daily": 1000,
    #     "weekly": 5000,
    #     "monthly": 20000,
    #     "enabled": true
    # }

    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'value': self.value,
            'description': self.description,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


# Default limits configuration
DEFAULT_LIMITS = {
    'openai_tokens': {
        'description': 'OpenAI API token usage limits',
        'value': {
            'daily': 100000,
            'weekly': 500000,
            'monthly': 2000000,
            'enabled': True
        }
    },
    'openai_requests': {
        'description': 'OpenAI API request count limits',
        'value': {
            'daily': 1000,
            'weekly': 5000,
            'monthly': 20000,
            'enabled': True
        }
    },
    'twilio_minutes': {
        'description': 'Twilio voice call minutes limits',
        'value': {
            'daily': 60,
            'weekly': 300,
            'monthly': 1000,
            'enabled': True
        }
    },
    'twilio_calls': {
        'description': 'Twilio call count limits',
        'value': {
            'daily': 50,
            'weekly': 250,
            'monthly': 1000,
            'enabled': True
        }
    },
    'users_per_company': {
        'description': 'Maximum users per company',
        'value': {
            'max': 50,
            'enabled': True
        }
    },
    'deepgram_minutes': {
        'description': 'Deepgram transcription minutes limits',
        'value': {
            'daily': 120,
            'weekly': 600,
            'monthly': 2000,
            'enabled': True
        }
    }
}

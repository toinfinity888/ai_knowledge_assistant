"""
Limits Service
Manages system-wide usage limits for APIs and resources
"""
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.system_limits import SystemLimits, DEFAULT_LIMITS
from app.database.postgresql_session import get_db_session

logger = logging.getLogger(__name__)


class LimitsService:
    """Service for managing system limits"""

    def get_all_limits(self, db: Session) -> Dict[str, Any]:
        """Get all limits with defaults for missing ones"""
        limits = {}

        # Get all stored limits
        stored = db.query(SystemLimits).all()
        stored_dict = {l.key: l for l in stored}

        # Merge with defaults
        for key, default in DEFAULT_LIMITS.items():
            if key in stored_dict:
                limits[key] = {
                    'value': stored_dict[key].value,
                    'description': stored_dict[key].description or default['description'],
                    'updated_at': stored_dict[key].updated_at.isoformat() if stored_dict[key].updated_at else None
                }
            else:
                limits[key] = {
                    'value': default['value'],
                    'description': default['description'],
                    'updated_at': None
                }

        return limits

    def get_limit(self, db: Session, key: str) -> Optional[Dict[str, Any]]:
        """Get a specific limit"""
        stored = db.query(SystemLimits).filter(SystemLimits.key == key).first()

        if stored:
            return {
                'value': stored.value,
                'description': stored.description,
                'updated_at': stored.updated_at.isoformat() if stored.updated_at else None
            }
        elif key in DEFAULT_LIMITS:
            return {
                'value': DEFAULT_LIMITS[key]['value'],
                'description': DEFAULT_LIMITS[key]['description'],
                'updated_at': None
            }

        return None

    def update_limit(
        self,
        db: Session,
        key: str,
        value: Dict[str, Any],
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Update a limit value"""
        stored = db.query(SystemLimits).filter(SystemLimits.key == key).first()

        description = DEFAULT_LIMITS.get(key, {}).get('description', '')

        if stored:
            stored.value = value
            stored.updated_by = user_id
        else:
            stored = SystemLimits(
                key=key,
                value=value,
                description=description,
                updated_by=user_id
            )
            db.add(stored)

        db.commit()
        db.refresh(stored)

        logger.info(f"Updated limit '{key}': {value}")

        return {
            'key': key,
            'value': stored.value,
            'description': stored.description,
            'updated_at': stored.updated_at.isoformat() if stored.updated_at else None
        }

    def update_all_limits(
        self,
        db: Session,
        limits: Dict[str, Dict[str, Any]],
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Update multiple limits at once"""
        result = {}

        for key, value in limits.items():
            if key in DEFAULT_LIMITS:
                result[key] = self.update_limit(db, key, value, user_id)

        return result

    def reset_to_defaults(self, db: Session) -> Dict[str, Any]:
        """Reset all limits to defaults"""
        # Delete all stored limits
        db.query(SystemLimits).delete()
        db.commit()

        logger.info("Reset all limits to defaults")

        return self.get_all_limits(db)

    def check_limit(self, db: Session, key: str, current_usage: int) -> Dict[str, Any]:
        """Check if usage is within limits"""
        limit_data = self.get_limit(db, key)

        if not limit_data:
            return {'allowed': True, 'reason': 'No limit configured'}

        value = limit_data['value']

        if not value.get('enabled', True):
            return {'allowed': True, 'reason': 'Limit disabled'}

        # Check against the appropriate period
        # This is a simplified check - in production you'd track actual usage
        for period in ['daily', 'weekly', 'monthly', 'max']:
            if period in value:
                if current_usage >= value[period]:
                    return {
                        'allowed': False,
                        'reason': f'{period.capitalize()} limit reached ({value[period]})',
                        'limit': value[period],
                        'current': current_usage
                    }

        return {'allowed': True, 'reason': 'Within limits'}


# Singleton instance
_limits_service: Optional[LimitsService] = None


def get_limits_service() -> LimitsService:
    """Get the limits service singleton"""
    global _limits_service
    if _limits_service is None:
        _limits_service = LimitsService()
    return _limits_service

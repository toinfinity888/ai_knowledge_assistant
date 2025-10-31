"""
Twilio Configuration for Two-Way Calling
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class TwilioSettings(BaseSettings):
    """Twilio configuration settings"""

    account_sid: str = Field(..., description="Twilio Account SID")
    auth_token: str = Field(..., description="Twilio Auth Token")
    phone_number: str = Field(..., description="Twilio phone number for outbound calls")

    # WebSocket settings for audio streaming
    websocket_url: Optional[str] = Field(None, description="Public URL for Twilio WebSocket callbacks")

    # API settings
    api_key_sid: Optional[str] = Field(None, description="Twilio API Key SID")
    api_key_secret: Optional[str] = Field(None, description="Twilio API Key Secret")

    # TwiML application settings
    twiml_app_sid: Optional[str] = Field(None, description="TwiML Application SID")

    class Config:
        env_file = '/Users/saraevsviatoslav/Documents/ai_knowledge_assistant/.env'
        env_prefix = "TWILIO_"
        extra = 'allow'
        case_sensitive = False


def get_twilio_settings() -> TwilioSettings:
    """Get Twilio settings instance"""
    return TwilioSettings()

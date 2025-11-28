"""
Configuration settings for the AI Scrum Master Agent Service
"""

import os
from typing import Optional

class Config:
    """Configuration class for the agent service"""
    
    # Service settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8001"))
    
    # Backend API settings
    DEFAULT_BACKEND_API_URL: str = os.getenv("BACKEND_API_URL", "http://localhost:8001")
    
    # Lemonfox.ai API settings
    LEMONFOX_API_KEY: Optional[str] = os.getenv("LEMONFOX_API_KEY")
    LEMONFOX_API_URL: str = "https://api.lemonfox.ai/v1/audio/transcriptions"
    
    # Agent settings
    BOT_NAME: str = os.getenv("BOT_NAME", "AI-Agent")
    DEFAULT_HEADLESS: bool = os.getenv("HEADLESS", "false").lower() == "true"
    
    # Audio settings
    AUDIO_CHUNK_DURATION: int = int(os.getenv("AUDIO_CHUNK_DURATION", "100"))  # 5 minutes
    AUDIO_SAMPLE_RATE: int = int(os.getenv("AUDIO_SAMPLE_RATE", "44100"))
    
    # Visual parsing settings
    CAPTION_SEND_INTERVAL: int = int(os.getenv("CAPTION_SEND_INTERVAL", "100"))  # 5 minutes
    CAPTION_BUFFER_SIZE: int = int(os.getenv("CAPTION_BUFFER_SIZE", "50"))
    
    # Timeout settings
    SELENIUM_TIMEOUT: int = int(os.getenv("SELENIUM_TIMEOUT", "20"))
    API_TIMEOUT: int = int(os.getenv("API_TIMEOUT", "10"))
    WHISPER_TIMEOUT: int = int(os.getenv("WHISPER_TIMEOUT", "60"))
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# Global config instance
config = Config()
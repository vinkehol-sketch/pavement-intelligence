"""Configuración centralizada."""
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PI_", env_file=".env", case_sensitive=False)
    env: str = "development"
    debug: bool = True
    db_url: str = "sqlite:///./data/pavement_intelligence.db"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    yolo_model_path: str = "data/models/yolov8n.pt"

_settings = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

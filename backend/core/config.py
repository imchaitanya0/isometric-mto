"""Application settings loaded from environment variables."""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    max_file_size_mb: int = Field(default=20, alias="MAX_FILE_SIZE_MB")

    @property
    def has_api_key(self) -> bool:
        return bool(self.gemini_api_key.strip())

    model_config = {"env_file": ".env", "populate_by_name": True, "extra": "ignore"}


settings = Settings()

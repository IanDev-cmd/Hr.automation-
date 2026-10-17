"""Environment configuration for the HR desk."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load deployment settings from the process environment."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    project_name: str = Field(default="HR.aUtomata", alias="PROJECT_NAME")
    version: str = Field(default="1.0.0", alias="VERSION")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    apps_script_webhook_url: str = Field(default="", alias="APPS_SCRIPT_WEBHOOK_URL")
    hr_webhook_token: str = Field(default="", alias="HR_WEBHOOK_TOKEN")
    database_url: str = Field(default="", alias="DATABASE_URL")
    cors_origins: str = Field(
        default="http://127.0.0.1:8765,http://localhost:8765",
        alias="CORS_ORIGINS",
    )

    def origin_list(self) -> list[str]:
        origins = [item.strip() for item in self.cors_origins.split(",") if item.strip()]
        return origins or ["http://127.0.0.1:8765"]


def get_settings() -> Settings:
    return Settings()

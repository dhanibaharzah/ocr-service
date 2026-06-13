from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_key: str = ""
    default_lang: str = "ind+eng"
    max_file_size_mb: int = 10
    cors_origins: str = "*"


settings = Settings()

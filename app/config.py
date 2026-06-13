from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_key: str = ""
    default_lang: str = "ind+eng"
    max_file_size_mb: int = 10
    max_pdf_pages: int = 20
    max_verify_pages: int = 5
    verify_pdf_dpi: int = 150
    ocr_pdf_dpi: int = 200
    cors_origins: str = "*"
    debug: bool = False


settings = Settings()

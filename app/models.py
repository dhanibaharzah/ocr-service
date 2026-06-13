from pydantic import BaseModel, Field


class WordDetail(BaseModel):
    text: str
    confidence: float = Field(ge=0, le=100)


class OcrResponse(BaseModel):
    text: str
    confidence: float = Field(ge=0, le=100, description="Average word confidence")
    word_count: int
    words: list[WordDetail]


class VerifyResponse(BaseModel):
    verified: bool
    confidence: float = Field(ge=0, le=100)
    match_score: float = Field(ge=0, le=100, description="How closely expected text matches OCR output")
    details: str | None = None
    extracted_text: str | None = Field(
        default=None,
        description="OCR output; included only when DEBUG=true",
    )
    pages_scanned: int | None = Field(
        default=None,
        description="Number of PDF pages OCR scanned (verify only)",
    )
    page_matched: int | None = Field(
        default=None,
        description="1-based page number where expected text matched (verify only)",
    )
    total_pages: int | None = Field(
        default=None,
        description="Total pages in the uploaded PDF (verify only)",
    )

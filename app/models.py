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
    extracted_text: str
    match_score: float = Field(ge=0, le=100, description="How closely expected text matches OCR output")
    details: str | None = None

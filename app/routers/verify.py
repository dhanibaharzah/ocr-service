from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile, status

from app.config import settings
from app.models import OcrResponse, VerifyResponse
from app.services.documents import read_document
from app.services.ocr import run_ocr, verify_text

router = APIRouter(prefix="/api/v1", tags=["ocr"])


def _check_api_key(x_api_key: str | None) -> None:
    if not settings.api_key:
        return
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


@router.post("/ocr", response_model=OcrResponse)
async def extract_text(
    file: UploadFile = File(...),
    lang: str = Form(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> OcrResponse:
    """Extract text from an image or PDF and return average word confidence."""
    _check_api_key(x_api_key)
    document_bytes, content_type = await read_document(file)
    return run_ocr(document_bytes, lang or settings.default_lang, content_type)


@router.post("/verify", response_model=VerifyResponse, response_model_exclude_none=True)
async def verify_document(
    file: UploadFile = File(...),
    expected_text: str = Form(..., description="Text that should appear in the document"),
    lang: str = Form(default=None),
    min_confidence: float = Form(default=60.0, ge=0, le=100),
    min_match_score: float = Form(default=70.0, ge=0, le=100),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> VerifyResponse:
    """Verify that expected text is found in the OCR result with sufficient confidence."""
    _check_api_key(x_api_key)
    expected = expected_text.strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="expected_text is required",
        )

    document_bytes, content_type = await read_document(file)
    return verify_text(
        document_bytes,
        expected,
        lang or settings.default_lang,
        content_type,
        min_confidence,
        min_match_score,
        settings.debug,
    )

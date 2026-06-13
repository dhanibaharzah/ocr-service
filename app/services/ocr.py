from __future__ import annotations

import io
import re
from difflib import SequenceMatcher

from PIL import Image, ImageOps
import pytesseract
from pytesseract import Output

from app.models import OcrResponse, VerifyResponse, WordDetail


def preprocess_image(image_bytes: bytes, max_width: int = 1600) -> Image.Image:
    image = Image.open(io.BytesIO(image_bytes))
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")

    if image.width > max_width:
        ratio = max_width / image.width
        new_size = (max_width, int(image.height * ratio))
        image = image.resize(new_size, Image.Resampling.LANCZOS)

    return image


def _normalize_text(text: str) -> str:
    cleaned = text.upper()
    cleaned = re.sub(r"[^\w\s]", " ", cleaned, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _extract_words(image: Image.Image, lang: str) -> list[WordDetail]:
    data = pytesseract.image_to_data(image, lang=lang, output_type=Output.DICT)
    words: list[WordDetail] = []

    for i, raw_text in enumerate(data["text"]):
        text = raw_text.strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            continue
        if conf < 0:
            continue
        words.append(WordDetail(text=text, confidence=conf))

    return words


def run_ocr(image_bytes: bytes, lang: str) -> OcrResponse:
    image = preprocess_image(image_bytes)
    text = pytesseract.image_to_string(image, lang=lang)
    words = _extract_words(image, lang)

    if words:
        confidence = round(sum(w.confidence for w in words) / len(words), 2)
    else:
        confidence = 0.0

    return OcrResponse(
        text=text.strip(),
        confidence=confidence,
        word_count=len(words),
        words=words,
    )


def _token_match_score(expected: str, ocr_text: str) -> float:
    expected_norm = _normalize_text(expected)
    ocr_norm = _normalize_text(ocr_text)

    if not expected_norm:
        return 0.0
    if expected_norm in ocr_norm:
        return 100.0

    expected_tokens = expected_norm.split()
    if not expected_tokens:
        return 0.0

    found = sum(1 for token in expected_tokens if token in ocr_norm)
    token_ratio = found / len(expected_tokens)

    fuzzy_ratio = SequenceMatcher(None, expected_norm, ocr_norm).ratio()
    return round(max(token_ratio, fuzzy_ratio) * 100, 2)


def verify_text(
    image_bytes: bytes,
    expected_text: str,
    lang: str,
    min_confidence: float,
    min_match_score: float,
) -> VerifyResponse:
    ocr_result = run_ocr(image_bytes, lang)
    match_score = _token_match_score(expected_text, ocr_result.text)

    verified = (
        ocr_result.confidence >= min_confidence
        and match_score >= min_match_score
    )

    details = None
    if not verified:
        reasons: list[str] = []
        if ocr_result.confidence < min_confidence:
            reasons.append(
                f"OCR confidence {ocr_result.confidence}% below threshold {min_confidence}%"
            )
        if match_score < min_match_score:
            reasons.append(
                f"Match score {match_score}% below threshold {min_match_score}%"
            )
        details = "; ".join(reasons)

    return VerifyResponse(
        verified=verified,
        confidence=ocr_result.confidence,
        extracted_text=ocr_result.text,
        match_score=match_score,
        details=details,
    )

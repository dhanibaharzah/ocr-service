from __future__ import annotations

import io
import re
from difflib import SequenceMatcher

from PIL import Image, ImageEnhance, ImageOps
import pytesseract
from pytesseract import Output

from app.models import OcrResponse, VerifyResponse, WordDetail
from app.services.documents import load_document_pages

# Document-style layout; works better for ID cards than Tesseract defaults.
TESSERACT_CONFIG = "--psm 6"
# Sparse text helps capture multi-line fields such as split KTP names.
SPARSE_TESSERACT_CONFIG = "--psm 11"
# Downscale very large uploads, then upscale so small text (e.g. NIK) stays readable.
MAX_OCR_WIDTH = 1600
MIN_OCR_WIDTH = 2400
# Ignore low-confidence tokens when averaging; decorative fonts often report conf=0.
MIN_WORD_CONFIDENCE = 30


def preprocess_pil(
    image: Image.Image,
    max_width: int = MAX_OCR_WIDTH,
    min_width: int = MIN_OCR_WIDTH,
) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")

    if image.width > max_width:
        ratio = max_width / image.width
        new_size = (max_width, int(image.height * ratio))
        image = image.resize(new_size, Image.Resampling.LANCZOS)

    image = image.convert("L")
    image = ImageEnhance.Contrast(image).enhance(2.0)
    image = ImageEnhance.Sharpness(image).enhance(2.0)

    if min_width and image.width < min_width:
        ratio = min_width / image.width
        image = image.resize(
            (min_width, int(image.height * ratio)),
            Image.Resampling.LANCZOS,
        )

    return image


def preprocess_image(
    image_bytes: bytes,
    max_width: int = MAX_OCR_WIDTH,
    min_width: int = MIN_OCR_WIDTH,
) -> Image.Image:
    image = Image.open(io.BytesIO(image_bytes))
    return preprocess_pil(image, max_width=max_width, min_width=min_width)


def _normalize_text(text: str) -> str:
    cleaned = text.upper()
    cleaned = re.sub(r"[^\w\s]", " ", cleaned, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _run_tesseract(
    image: Image.Image,
    lang: str,
    config: str = TESSERACT_CONFIG,
) -> tuple[str, list[WordDetail]]:
    """Single Tesseract pass — extracts text and word confidence together."""
    data = pytesseract.image_to_data(
        image,
        lang=lang,
        config=config,
        output_type=Output.DICT,
    )
    words: list[WordDetail] = []
    line_parts: dict[tuple[int, int, int], list[str]] = {}

    for i, raw_text in enumerate(data["text"]):
        text = raw_text.strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            continue
        if conf >= 0:
            words.append(WordDetail(text=text, confidence=conf))
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        line_parts.setdefault(key, []).append(text)

    lines = [" ".join(line_parts[key]) for key in sorted(line_parts)]
    return "\n".join(lines), words


def _average_confidence(words: list[WordDetail]) -> float:
    reliable = [w.confidence for w in words if w.confidence >= MIN_WORD_CONFIDENCE]
    if not reliable:
        return 0.0
    return round(sum(reliable) / len(reliable), 2)


def _digits_only_pass(image: Image.Image) -> str:
    config = f"{TESSERACT_CONFIG} -c tessedit_char_whitelist=0123456789"
    return pytesseract.image_to_string(image, lang="eng", config=config)


def _sparse_text_pass(image: Image.Image, lang: str) -> str:
    return pytesseract.image_to_string(image, lang=lang, config=SPARSE_TESSERACT_CONFIG)


def _enrich_match_text(
    processed: Image.Image,
    primary_text: str,
    expected_text: str,
    lang: str,
    min_match_score: float,
) -> str:
    """Run a second OCR pass only when the primary pass did not match well enough."""
    if _token_match_score(expected_text, primary_text) >= min_match_score:
        return primary_text
    if _is_numeric(expected_text):
        return f"{primary_text}\n{_digits_only_pass(processed)}"
    return f"{primary_text}\n{_sparse_text_pass(processed, lang)}"


def _ocr_page(image: Image.Image, lang: str) -> tuple[str, list[WordDetail]]:
    processed = preprocess_pil(image)
    return _run_tesseract(processed, lang)


def run_ocr(document_bytes: bytes, lang: str, content_type: str) -> OcrResponse:
    pages = load_document_pages(document_bytes, content_type)
    page_texts: list[str] = []
    all_words: list[WordDetail] = []

    for page in pages:
        text, words = _ocr_page(page, lang)
        if text.strip():
            page_texts.append(text.strip())
        all_words.extend(words)

    return OcrResponse(
        text="\n\n".join(page_texts),
        confidence=_average_confidence(all_words),
        word_count=len(all_words),
        words=all_words,
    )


def _is_numeric(text: str) -> bool:
    stripped = text.strip()
    return bool(stripped) and stripped.isdigit()


def _digit_match_score(expected: str, ocr_text: str) -> float:
    expected_digits = re.sub(r"\D", "", expected)
    if not expected_digits:
        return 0.0

    ocr_digits = re.sub(r"\D", "", ocr_text)
    if expected_digits in ocr_digits:
        return 100.0

    n = len(expected_digits)
    if len(ocr_digits) < n:
        best = SequenceMatcher(None, expected_digits, ocr_digits).ratio()
    else:
        best = max(
            SequenceMatcher(None, expected_digits, ocr_digits[i : i + n]).ratio()
            for i in range(len(ocr_digits) - n + 1)
        )
    return round(best * 100, 2)


def _best_token_fuzzy_ratio(expected_token: str, ocr_tokens: list[str]) -> float:
    if expected_token in ocr_tokens:
        return 1.0
    if not ocr_tokens:
        return 0.0
    return max(
        SequenceMatcher(None, expected_token, ocr_token).ratio()
        for ocr_token in ocr_tokens
    )


def _text_match_score(expected: str, ocr_text: str) -> float:
    expected_norm = _normalize_text(expected)
    ocr_norm = _normalize_text(ocr_text)

    if not expected_norm:
        return 0.0
    if expected_norm in ocr_norm:
        return 100.0

    expected_tokens = expected_norm.split()
    ocr_tokens = ocr_norm.split()
    if not expected_tokens:
        return 0.0

    exact_ratio = sum(1 for token in expected_tokens if token in ocr_norm) / len(
        expected_tokens
    )
    fuzzy_token_ratio = sum(
        _best_token_fuzzy_ratio(token, ocr_tokens) for token in expected_tokens
    ) / len(expected_tokens)
    fuzzy_ratio = SequenceMatcher(None, expected_norm, ocr_norm).ratio()

    return round(max(exact_ratio, fuzzy_token_ratio, fuzzy_ratio) * 100, 2)


def _token_match_score(expected: str, ocr_text: str) -> float:
    if _is_numeric(expected):
        return _digit_match_score(expected, ocr_text)

    return _text_match_score(expected, ocr_text)


def verify_text(
    document_bytes: bytes,
    expected_text: str,
    lang: str,
    content_type: str,
    min_confidence: float,
    min_match_score: float,
    debug: bool = False,
) -> VerifyResponse:
    pages = load_document_pages(document_bytes, content_type)
    page_texts: list[str] = []
    match_texts: list[str] = []
    all_words: list[WordDetail] = []

    for page in pages:
        processed = preprocess_pil(page)
        text, words = _run_tesseract(processed, lang)
        all_words.extend(words)

        if text.strip():
            page_texts.append(text.strip())

        match_texts.append(
            _enrich_match_text(
                processed,
                text,
                expected_text,
                lang,
                min_match_score,
            )
        )

    confidence = _average_confidence(all_words)
    combined_match_text = "\n\n".join(match_texts)
    match_score = _token_match_score(expected_text, combined_match_text)

    verified = (
        confidence >= min_confidence
        and match_score >= min_match_score
    )

    details = None
    if not verified:
        reasons: list[str] = []
        if confidence < min_confidence:
            reasons.append(
                f"OCR confidence {confidence}% below threshold {min_confidence}%"
            )
        if match_score < min_match_score:
            reasons.append(
                f"Match score {match_score}% below threshold {min_match_score}%"
            )
        details = "; ".join(reasons)

    return VerifyResponse(
        verified=verified,
        confidence=confidence,
        match_score=match_score,
        details=details,
        extracted_text="\n\n".join(page_texts) if debug else None,
    )

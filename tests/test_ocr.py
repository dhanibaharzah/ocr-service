from app.services.ocr import (
    _digit_match_score,
    _is_numeric,
    _token_match_score,
)


def test_is_numeric():
    assert _is_numeric("3175020901970005")
    assert not _is_numeric("NIK 3175020901970005")
    assert not _is_numeric("")


def test_digit_match_score_exact():
    assert _digit_match_score("3175020901970005", "NIK 3175020901970005") == 100.0
    assert _digit_match_score(
        "3175020901970005",
        "noise 3175020901970005 more noise",
    ) == 100.0


def test_digit_match_score_fuzzy():
    score = _digit_match_score("3175020901970005", "3475020901970005")
    assert score >= 93.0


def test_token_match_score_uses_digit_matching():
    assert _token_match_score("3175020901970005", "3475020901970005") >= 93.0
    assert _token_match_score("JOHN DOE", "hello JOHN DOE world") == 100.0


def test_text_match_score_fuzzy_name_tokens():
    ocr_text = "MOHAMMAD HUSEIN RAMADHANE\nBAHARZAH"
    score = _token_match_score("Mohammad Husein Ramadhani Baharzah", ocr_text)
    assert score >= 85.0


def test_verify_response_debug_toggle():
    from app.services.ocr import verify_text

    from PIL import Image, ImageDraw
    import io

    img = Image.new("RGB", (400, 120), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 40), "JOHN DOE", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()

    off = verify_text(data, "JOHN DOE", "eng", "image/png", 0, 50, debug=False)
    on = verify_text(data, "JOHN DOE", "eng", "image/png", 0, 50, debug=True)

    assert off.extracted_text is None
    assert on.extracted_text is not None
    assert "JOHN" in on.extracted_text.upper()

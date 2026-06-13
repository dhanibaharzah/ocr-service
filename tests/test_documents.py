import io

import fitz
from fastapi import HTTPException
from PIL import Image, ImageDraw
import pytest

from app.services.documents import (
    iter_document_pages,
    load_document_pages,
    pdf_to_images,
    resolve_content_type,
)


def _make_test_image(text: str = "JOHN DOE") -> bytes:
    img = Image.new("RGB", (400, 120), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 40), text, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_test_pdf(text: str = "NIK 3201234567890123") -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_resolve_content_type_from_extension():
    assert resolve_content_type(None, "scan.pdf") == "application/pdf"
    assert resolve_content_type(None, "ktp.png") == "image/png"
    assert resolve_content_type("application/pdf", "scan.pdf") == "application/pdf"


def test_resolve_content_type_rejects_unknown():
    with pytest.raises(HTTPException) as exc:
        resolve_content_type(None, "file.docx")
    assert exc.value.status_code == 400


def test_load_document_pages_image():
    pages = load_document_pages(_make_test_image(), "image/png")
    assert len(pages) == 1
    assert pages[0].mode == "RGB"


def test_load_document_pages_pdf():
    pages = load_document_pages(_make_test_pdf(), "application/pdf")
    assert len(pages) == 1
    assert pages[0].mode == "RGB"


def test_pdf_to_images_rejects_invalid_bytes():
    with pytest.raises(HTTPException) as exc:
        pdf_to_images(b"not a pdf", max_pages=10)
    assert exc.value.status_code == 400


def _make_multi_page_pdf(texts: list[str]) -> bytes:
    doc = fitz.open()
    for text in texts:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_iter_document_pages_stops_at_max_pages():
    pdf = _make_multi_page_pdf(["PAGE1", "PAGE2", "PAGE3"])
    scanned = list(
        iter_document_pages(pdf, "application/pdf", max_pages=2)
    )
    assert len(scanned) == 2
    assert scanned[0][:2] == (1, 3)
    assert scanned[1][0] == 2

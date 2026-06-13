from __future__ import annotations

import io
from collections.abc import Iterator

import fitz
from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps

from app.config import settings

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/tiff",
}
ALLOWED_PDF_TYPES = {"application/pdf"}
ALLOWED_CONTENT_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_PDF_TYPES

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
PDF_EXTENSIONS = {".pdf"}


def resolve_content_type(content_type: str | None, filename: str | None) -> str:
    if content_type in ALLOWED_CONTENT_TYPES:
        return content_type

    if filename:
        lower = filename.lower()
        if any(lower.endswith(ext) for ext in PDF_EXTENSIONS):
            return "application/pdf"
        if any(lower.endswith(ext) for ext in IMAGE_EXTENSIONS):
            if lower.endswith((".jpg", ".jpeg")):
                return "image/jpeg"
            if lower.endswith(".png"):
                return "image/png"
            if lower.endswith(".webp"):
                return "image/webp"
            return "image/tiff"

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported file type. Use JPEG, PNG, WebP, TIFF, or PDF.",
    )


def _open_image(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    image = ImageOps.exif_transpose(image)
    return image.convert("RGB")


def _open_pdf(data: bytes) -> fitz.Document:
    try:
        return fitz.open(stream=data, filetype="pdf")
    except fitz.FileDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or corrupted PDF file.",
        ) from exc


def pdf_page_count(pdf_bytes: bytes) -> int:
    doc = _open_pdf(pdf_bytes)
    try:
        return doc.page_count
    finally:
        doc.close()


def _render_pdf_page(doc: fitz.Document, page_index: int, dpi: int) -> Image.Image:
    page = doc.load_page(page_index)
    pix = page.get_pixmap(dpi=dpi)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def pdf_to_images(
    pdf_bytes: bytes,
    max_pages: int,
    dpi: int | None = None,
) -> list[Image.Image]:
    doc = _open_pdf(pdf_bytes)
    try:
        if doc.page_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PDF has no pages.",
            )
        if doc.page_count > max_pages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"PDF has too many pages. Max {max_pages} pages.",
            )

        render_dpi = dpi or settings.ocr_pdf_dpi
        return [
            _render_pdf_page(doc, index, render_dpi)
            for index in range(doc.page_count)
        ]
    finally:
        doc.close()


def iter_document_pages(
    data: bytes,
    content_type: str,
    *,
    max_pages: int | None = None,
    dpi: int | None = None,
) -> Iterator[tuple[int, int, Image.Image]]:
    """Yield (page_number, total_pages, image) one page at a time."""
    if content_type in ALLOWED_PDF_TYPES:
        doc = _open_pdf(data)
        try:
            total_pages = doc.page_count
            if total_pages == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="PDF has no pages.",
                )
            if total_pages > settings.max_pdf_pages:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"PDF has too many pages. Max {settings.max_pdf_pages} pages."
                    ),
                )

            scan_limit = min(total_pages, max_pages or settings.max_verify_pages)
            render_dpi = dpi or settings.verify_pdf_dpi
            for index in range(scan_limit):
                yield index + 1, total_pages, _render_pdf_page(doc, index, render_dpi)
        finally:
            doc.close()
        return

    yield 1, 1, _open_image(data)


def load_document_pages(data: bytes, content_type: str) -> list[Image.Image]:
    if content_type in ALLOWED_PDF_TYPES:
        return pdf_to_images(data, max_pages=settings.max_pdf_pages)

    return [_open_image(data)]


async def read_document(file: UploadFile) -> tuple[bytes, str]:
    content_type = resolve_content_type(file.content_type, file.filename)

    data = await file.read()
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Max {settings.max_file_size_mb}MB.",
        )
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file",
        )

    return data, content_type

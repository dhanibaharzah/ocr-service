from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers.verify import router as verify_router

app = FastAPI(
    title="OCR Verification Service",
    description="Tesseract-based OCR API for document text extraction and verification",
    version="1.0.0",
)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(verify_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

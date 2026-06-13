import io

from PIL import Image
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _make_test_image(text: str = "JOHN DOE") -> bytes:
    from PIL import ImageDraw, ImageFont

    img = Image.new("RGB", (400, 120), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 40), text, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_verify_endpoint_accepts_request():
    image = _make_test_image("NIK 3201234567890123")
    response = client.post(
        "/api/v1/verify",
        files={"file": ("test.png", image, "image/png")},
        data={
            "expected_text": "3201234567890123",
            "min_confidence": 0,
            "min_match_score": 50,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "verified" in body
    assert "confidence" in body
    assert "match_score" in body

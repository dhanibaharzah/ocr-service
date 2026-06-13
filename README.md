# OCR Verification Service

API verifikasi dokumen berbasis **Tesseract OCR**, dioptimalkan untuk deploy di **Google Cloud Run**.

## Mengapa GCP Cloud Run (bukan Vercel / Cloudflare Workers)?

| Platform | Tesseract native | Cocok untuk OCR API? | Catatan |
|----------|------------------|----------------------|---------|
| **GCP Cloud Run** | ✅ via Docker | ✅ **Recommended** | Install `tesseract-ocr` di container, scale-to-zero, free tier generous |
| **Vercel** | ❌ tidak ada binary | ⚠️ Hanya via tesseract.js (WASM) | Banyak issue bundling WASM, cold start lambat, timeout 10s (Hobby), memory terbatas |
| **Cloudflare Workers** | ❌ | ❌ **Tidak didukung** | Tidak bisa spawn Worker threads; tesseract.js gagal (`Worker is not defined`); WASM limit ~1MB; single-threaded |

Proyek `connectpreneur` sudah membuktikan workaround Vercel (tesseract.js + traineddata lokal + timeout), tapi tetap fragile. Service standalone di Cloud Run jauh lebih stabil dan cepat.

### GCP Free Tier (Cloud Run, region Tier-1: `us-central1`, `us-east1`, `us-west1`)

Per billing account / bulan (2025):

- **180.000 vCPU-seconds** (~50 jam @ 1 vCPU)
- **360.000 GiB-seconds** memory
- **2 juta requests**

Untuk OCR ringan (beberapa ratus request/hari), biaya bisa **$0** selama dalam limit.

---

## API Endpoints

### `GET /health`

Health check.

### `POST /api/v1/ocr`

Ekstrak teks dari gambar.

**Request:** `multipart/form-data`

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `file` | ✅ | — | JPEG, PNG, WebP, TIFF, PDF (max 10MB, PDF max 10 pages) |
| `lang` | ❌ | `ind+eng` | Tesseract language pack |

**Response:**

```json
{
  "text": "extracted text...",
  "confidence": 87.5,
  "word_count": 42,
  "words": [{ "text": "JOHN", "confidence": 92.1 }]
}
```

### `POST /api/v1/verify`

Verifikasi apakah teks yang diharapkan ada di dokumen.

**Request:** `multipart/form-data`

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `file` | ✅ | — | Gambar atau PDF dokumen |
| `expected_text` | ✅ | — | Teks/nama/NIK yang harus ditemukan |
| `lang` | ❌ | `ind+eng` | Language pack |
| `min_confidence` | ❌ | `60` | Threshold confidence OCR (0-100) |
| `min_match_score` | ❌ | `70` | Threshold kecocokan teks (0-100) |

**Response:**

```json
{
  "verified": true,
  "confidence": 85.2,
  "extracted_text": "...",
  "match_score": 95.0,
  "details": null
}
```

### Authentication

Set env `API_KEY` di Cloud Run. Client kirim header:

```
X-API-Key: your-secret-api-key
```

Jika `API_KEY` kosong, auth dinonaktifkan (hanya untuk dev lokal).

---

## Local Development

### Prerequisites

- Python 3.12+
- Tesseract: `brew install tesseract tesseract-lang` (macOS)

### Run

```bash
cd ocr-service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest httpx

cp .env.example .env
uvicorn app.main:app --reload --port 8080
```

Docs: http://localhost:8080/docs

### Docker (recommended, matches production)

```bash
docker build -t ocr-service .
docker run -p 8080:8080 -e API_KEY=dev-key ocr-service
```

### Test

```bash
pytest tests/ -v
```

### Example curl

```bash
curl -X POST http://localhost:8080/api/v1/verify \
  -H "X-API-Key: dev-key" \
  -F "file=@ktp.jpg" \
  -F "expected_text=BUDI SANTOSO" \
  -F "min_confidence=60" \
  -F "min_match_score=70"
```

---

## Deploy to GCP Cloud Run

### 1. Setup GCP

```bash
# Login & set project
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Enable billing on project (required even for free tier)
```

### 2. Deploy

```bash
chmod +x deploy/cloud-run.sh

PROJECT_ID=your-project-id \
REGION=us-central1 \
API_KEY=your-production-api-key \
./deploy/cloud-run.sh
```

Script akan:

1. Enable APIs (Cloud Run, Cloud Build, Artifact Registry)
2. Build Docker image via Cloud Build
3. Deploy ke Cloud Run (scale-to-zero, 1Gi RAM, 120s timeout)

### 3. Integrasi dari web lain

```typescript
const form = new FormData()
form.append("file", imageFile)
form.append("expected_text", "BUDI SANTOSO")

const res = await fetch("https://ocr-service-xxx.run.app/api/v1/verify", {
  method: "POST",
  headers: { "X-API-Key": process.env.OCR_API_KEY! },
  body: form,
})

const { verified, confidence, match_score } = await res.json()
```

Untuk `connectpreneur`, ganti inline tesseract.js dengan call ke service ini.

---

## Architecture

```
Client (Web X) ──POST /api/v1/verify──▶ Cloud Run
                                           │
                                           ├─ FastAPI
                                           ├─ Pillow (preprocess)
                                           └─ Tesseract (native binary)
```

Cloud Run scale-to-zero saat idle → biaya ~$0 untuk traffic rendah.

---

## License

MIT

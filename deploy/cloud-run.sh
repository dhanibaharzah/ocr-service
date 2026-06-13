#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   PROJECT_ID=my-gcp-project REGION=us-central1 ./deploy/cloud-run.sh
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Billing enabled on GCP project
#   - APIs: run, cloudbuild, artifactregistry

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-ocr-service}"
REPO_NAME="${REPO_NAME:-ocr-repo}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
API_KEY="${API_KEY:-}"

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:${IMAGE_TAG}"

echo "==> Setting gcloud project"
gcloud config set project "${PROJECT_ID}"

echo "==> Enabling required APIs"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com

echo "==> Creating Artifact Registry (ignore error if exists)"
gcloud artifacts repositories create "${REPO_NAME}" \
  --repository-format=docker \
  --location="${REGION}" \
  --description="OCR service images" \
  2>/dev/null || true

echo "==> Building and pushing image"
gcloud builds submit --tag "${IMAGE}" .

DEPLOY_ARGS=(
  run deploy "${SERVICE_NAME}"
  --image "${IMAGE}"
  --region "${REGION}"
  --platform managed
  --allow-unauthenticated
  --memory 1Gi
  --cpu 1
  --timeout 120
  --concurrency 5
  --max-instances 3
  --min-instances 0
  --port 8080
)

if [[ -n "${API_KEY}" ]]; then
  DEPLOY_ARGS+=(--set-env-vars "API_KEY=${API_KEY}")
fi

echo "==> Deploying to Cloud Run"
gcloud "${DEPLOY_ARGS[@]}"

echo "==> Done"
gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format='value(status.url)'

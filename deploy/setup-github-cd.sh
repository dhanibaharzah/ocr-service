#!/usr/bin/env bash
set -euo pipefail

# One-time setup: connect GitHub Actions to GCP via Workload Identity Federation.
#
# Usage:
#   GITHUB_REPO=dhanibaharzah/ocr-service ./deploy/setup-github-cd.sh
#
# After running, add the printed secrets to GitHub:
#   Settings → Secrets and variables → Actions

PROJECT_ID="${PROJECT_ID:-orbitcreation-co-id}"
GITHUB_REPO="${GITHUB_REPO:?Set GITHUB_REPO (e.g. dhanibaharzah/ocr-service)}"
SA_NAME="${SA_NAME:-github-actions-deployer}"
POOL_ID="${POOL_ID:-github-pool}"
PROVIDER_ID="${PROVIDER_ID:-github-provider}"

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "==> Project: ${PROJECT_ID} (${PROJECT_NUMBER})"
echo "==> GitHub repo: ${GITHUB_REPO}"

echo "==> Enabling APIs"
gcloud services enable \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  --project="${PROJECT_ID}"

echo "==> Creating service account (ignore error if exists)"
gcloud iam service-accounts create "${SA_NAME}" \
  --display-name="GitHub Actions deployer" \
  --project="${PROJECT_ID}" \
  2>/dev/null || true

echo "==> Granting IAM roles to ${SA_EMAIL}"
for ROLE in \
  roles/run.admin \
  roles/artifactregistry.admin \
  roles/cloudbuild.builds.editor \
  roles/iam.serviceAccountUser \
  roles/storage.admin \
  roles/serviceusage.serviceUsageConsumer; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" \
    --quiet
done

echo "==> Creating Workload Identity Pool (ignore error if exists)"
gcloud iam workload-identity-pools create "${POOL_ID}" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --display-name="GitHub Actions" \
  2>/dev/null || true

echo "==> Creating OIDC provider (ignore error if exists)"
gcloud iam workload-identity-pools providers create-oidc "${PROVIDER_ID}" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --workload-identity-pool="${POOL_ID}" \
  --display-name="GitHub" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  2>/dev/null || true

echo "==> Allowing GitHub repo to impersonate service account"
gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --project="${PROJECT_ID}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${GITHUB_REPO}"

WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"

echo ""
echo "=========================================="
echo "Add these GitHub repository secrets:"
echo "https://github.com/${GITHUB_REPO}/settings/secrets/actions"
echo "=========================================="
echo ""
echo "GCP_WORKLOAD_IDENTITY_PROVIDER"
echo "${WIF_PROVIDER}"
echo ""
echo "GCP_SERVICE_ACCOUNT"
echo "${SA_EMAIL}"
echo ""
echo "OCR_API_KEY"
echo "(your production API key — same value as in .env)"
echo ""
echo "After adding secrets, push to main to trigger deploy."

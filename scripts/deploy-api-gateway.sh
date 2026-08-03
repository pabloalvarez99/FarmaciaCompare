#!/usr/bin/env bash
# Build and deploy the API gateway to Cloud Run.
#
#   ./scripts/deploy-api-gateway.sh [TAG]
#
# Reads the Cloud SQL password from .env.production (gitignored) so no secret
# ever lands in the repo or in shell history.
set -euo pipefail

PROJECT=farmacia-compare-prod
REGION=southamerica-west1
INSTANCE=farmacia-compare-db
SERVICE=api-gateway
CONN="${PROJECT}:${REGION}:${INSTANCE}"
TAG="${1:-$(git rev-parse --short HEAD 2>/dev/null || echo manual)}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/farmacia/${SERVICE}:${TAG}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env.production ]]; then
  echo "Missing .env.production with the Cloud SQL DATABASE_URL." >&2
  exit 1
fi

# The public-IP URL in .env.production is for running scrapers from a laptop.
# Cloud Run reaches the database through the /cloudsql unix socket instead, so
# rebuild the URL with the same credentials and a socket host.
PUBLIC_URL="$(grep '^DATABASE_URL=' .env.production | cut -d= -f2-)"
CREDS="$(sed -E 's#^postgresql://([^@]+)@.*#\1#' <<<"$PUBLIC_URL")"
SOCKET_URL="postgresql://${CREDS}@localhost/farmaciacompare?host=/cloudsql/${CONN}"

echo "==> Building ${IMAGE}"
gcloud builds submit --config=cloudbuild.yaml \
  --project="$PROJECT" --region="$REGION" \
  --substitutions=SHORT_SHA="$TAG"

echo "==> Deploying ${SERVICE}"
gcloud run deploy "$SERVICE" \
  --project="$PROJECT" --region="$REGION" \
  --image="$IMAGE" \
  --add-cloudsql-instances="$CONN" \
  --set-env-vars="DATABASE_URL=${SOCKET_URL},NODE_ENV=production${CORS_ORIGINS:+,CORS_ORIGINS=$CORS_ORIGINS}" \
  --allow-unauthenticated \
  --memory=512Mi --cpu=1 --min-instances=0 --max-instances=3 --timeout=60 \
  --quiet

gcloud run services describe "$SERVICE" \
  --project="$PROJECT" --region="$REGION" --format='value(status.url)'

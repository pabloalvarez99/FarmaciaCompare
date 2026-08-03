#!/usr/bin/env bash
# Build the scraper image, deploy it as a Cloud Run Job and (re)create the
# Cloud Scheduler triggers that keep prices fresh.
#
#   ./scripts/deploy-scraper-job.sh [TAG]
#
# Idempotent: safe to re-run. Reads the Cloud SQL password from .env.production
# (gitignored) so no secret ever lands in the repo or in shell history.
#
# Manual runs after deploying:
#   gcloud run jobs execute scraper --project=farmacia-compare-prod \
#     --region=southamerica-west1 --args=scrape,farmex --wait
set -euo pipefail

PROJECT=farmacia-compare-prod
REGION=southamerica-west1
INSTANCE=farmacia-compare-db
JOB=scraper
CONN="${PROJECT}:${REGION}:${INSTANCE}"
TAG="${1:-$(git rev-parse --short HEAD 2>/dev/null || echo manual)}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/farmacia/${JOB}:${TAG}"

# Cloud Scheduler is NOT offered in southamerica-west1 (Santiago) — the closest
# location is southamerica-east1 (Sao Paulo). The trigger is a plain HTTPS call
# to the Cloud Run Admin API, so a cross-region scheduler is fine.
#   gcloud scheduler locations list --project=farmacia-compare-prod
SCHED_REGION=southamerica-east1
SCHED_SA_NAME=scraper-scheduler
SCHED_SA="${SCHED_SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
RUN_URI="https://run.googleapis.com/v2/projects/${PROJECT}/locations/${REGION}/jobs/${JOB}:run"
TZ_NAME="America/Santiago"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env.production ]]; then
  echo "Missing .env.production with the Cloud SQL DATABASE_URL." >&2
  exit 1
fi

# .env.production points at the public IP (for laptop runs). Inside Cloud Run
# the database is reached through the /cloudsql unix socket instead, so rebuild
# the URL with the same credentials and a socket host.
PUBLIC_URL="$(grep '^DATABASE_URL=' .env.production | cut -d= -f2-)"
CREDS="$(sed -E 's#^postgresql://([^@]+)@.*#\1#' <<<"$PUBLIC_URL")"
SOCKET_URL="postgresql://${CREDS}@localhost/farmaciacompare?host=/cloudsql/${CONN}"

echo "==> Enabling APIs (no-op if already enabled)"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com sqladmin.googleapis.com \
  cloudscheduler.googleapis.com --project="$PROJECT" --quiet

echo "==> Building ${IMAGE}"
gcloud builds submit --config=cloudbuild-scraper.yaml \
  --project="$PROJECT" --region="$REGION" \
  --substitutions=SHORT_SHA="$TAG"

# One job, many schedules: each Cloud Scheduler trigger overrides the container
# args, so `scrape farmex`, `scrape-all`, etc. all reuse this deployment.
echo "==> Deploying Cloud Run Job ${JOB}"
gcloud run jobs deploy "$JOB" \
  --project="$PROJECT" --region="$REGION" \
  --image="$IMAGE" \
  --args=scrape-all \
  --set-cloudsql-instances="$CONN" \
  --set-env-vars="DATABASE_URL=${SOCKET_URL}" \
  --memory=2Gi --cpu=1 \
  --tasks=1 --parallelism=1 --max-retries=1 \
  --task-timeout=7200s \
  --quiet

echo "==> Service account for the Scheduler triggers"
if ! gcloud iam service-accounts describe "$SCHED_SA" --project="$PROJECT" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SCHED_SA_NAME" \
    --project="$PROJECT" \
    --display-name="Cloud Scheduler -> scraper job" --quiet
  sleep 10   # IAM needs a moment before the new SA can be referenced
fi
# roles/run.invoker is NOT enough: the triggers pass containerOverrides, which
# needs run.jobs.runWithOverrides. That permission lives in
# roles/run.jobsExecutorWithOverrides (or the much broader roles/run.developer).
# With only run.invoker the Scheduler attempt fails with code 7 PERMISSION_DENIED.
gcloud run jobs add-iam-policy-binding "$JOB" \
  --project="$PROJECT" --region="$REGION" \
  --member="serviceAccount:${SCHED_SA}" \
  --role=roles/run.jobsExecutorWithOverrides --quiet >/dev/null

# name|cron|container args (comma separated)
#
# Cadence follows registry.py interval_hours, staggered so two chains never
# hammer the db-f1-micro instance at once, and shifted so the heavy full-catalog
# walks (farmex ~22k, salcobrand ~12k products) sit outside Chilean peak hours.
#   interval_hours=6  -> 4x/day
#   interval_hours=12 -> 2x/day
# cruz_verde also gets a cheap --fast search refresh between full walks.
SCHEDULES=(
  "scraper-sync-pharmacies|0 4 * * *|sync-pharmacies"
  "scraper-farmex|20 1,7,13,19 * * *|scrape,farmex"
  "scraper-salcobrand|0 2,8,14,20 * * *|scrape,salcobrand"
  "scraper-curie|40 2,8,14,20 * * *|scrape,curie"
  "scraper-farmaloop|10 3,9,15,21 * * *|scrape,farmaloop"
  "scraper-dr-simi|40 3,9,15,21 * * *|scrape,dr_simi"
  "scraper-cruz-verde-full|10 5,17 * * *|scrape,cruz_verde"
  "scraper-cruz-verde-fast|10 11,23 * * *|scrape,cruz_verde,--fast"
  "scraper-ahumada|40 5,17 * * *|scrape,ahumada"
)

echo "==> Cloud Scheduler triggers"
for row in "${SCHEDULES[@]}"; do
  IFS='|' read -r name cron args <<<"$row"

  # Turn "scrape,farmex" into ["scrape","farmex"] for the Cloud Run v2 API.
  json_args="[\"${args//,/\",\"}\"]"
  body="{\"overrides\":{\"containerOverrides\":[{\"args\":${json_args}}]}}"

  # `create http` takes --headers; `update http` only knows --update-headers.
  verb=create
  headers_flag=--headers
  if gcloud scheduler jobs describe "$name" \
      --project="$PROJECT" --location="$SCHED_REGION" >/dev/null 2>&1; then
    verb=update
    headers_flag=--update-headers
  fi

  gcloud scheduler jobs "$verb" http "$name" \
    --project="$PROJECT" --location="$SCHED_REGION" \
    --schedule="$cron" --time-zone="$TZ_NAME" \
    --uri="$RUN_URI" --http-method=POST \
    "${headers_flag}=Content-Type=application/json" \
    --message-body="$body" \
    --oauth-service-account-email="$SCHED_SA" \
    --attempt-deadline=180s \
    --max-retry-attempts=1 \
    --quiet >/dev/null
  echo "    ${verb}d ${name}  [${cron}]  args=${args}"
done

echo
echo "==> Done. Job:"
gcloud run jobs describe "$JOB" --project="$PROJECT" --region="$REGION" \
  --format='value(name, spec.template.spec.template.spec.containers[0].image)'
echo "==> Schedules:"
gcloud scheduler jobs list --project="$PROJECT" --location="$SCHED_REGION" \
  --format='table(name.basename(), schedule, state)'

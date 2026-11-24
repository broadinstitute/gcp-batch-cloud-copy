#!/bin/bash

set -euo pipefail

URL=$(python3 -c "import json, os; print(json.loads(os.environ['URLS'])[int(os.environ['BATCH_TASK_INDEX'])])")

echo "Setting MD5 hash for $URL ($((BATCH_TASK_INDEX+1)) of $((BATCH_TASK_COUNT)))"
gcloud config set storage/parallel_composite_upload_enabled False # to ensure MD5 is set

# download from GCS to temp file
tmpfile=$(mktemp)
gcloud storage cp "$URL" "$tmpfile" \
  --billing-project="$GCP_PROJECT_ID" \
  --quiet

gcloud storage cp "$tmpfile" "$URL" \
  --billing-project="$GCP_PROJECT_ID" \
  --quiet

rm -f "$tmpfile"
echo "Reupload complete for $URL"

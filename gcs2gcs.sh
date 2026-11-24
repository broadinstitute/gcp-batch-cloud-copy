#!/bin/bash

set -euo pipefail

URL_SRC=$(python3 -c "import json, os; print(json.loads(os.environ['URL_MAPPING'])[int(os.environ['BATCH_TASK_INDEX'])]['url_src'])")
URL_DEST=$(python3 -c "import json, os; print(json.loads(os.environ['URL_MAPPING'])[int(os.environ['BATCH_TASK_INDEX'])]['url_dest'])")

echo "Copying from $URL_SRC to $URL_DEST ($((BATCH_TASK_INDEX+1)) of $((BATCH_TASK_COUNT)))"
gcloud config set storage/parallel_composite_upload_enabled False # for AnVIL uploads

gcloud storage cp "$URL_SRC" "$URL_DEST" \
  --billing-project="$GCP_PROJECT_ID" \
  --quiet

echo "Copy complete for $URL_SRC"

#!/bin/bash

set -euo pipefail

GCS_URL=$(python3 -c "import json, os; print(json.loads(os.environ['URL_MAPPING'])[int(os.environ['BATCH_TASK_INDEX'])]['url_gcs'])")
S3_URL=$(python3 -c "import json, os; print(json.loads(os.environ['URL_MAPPING'])[int(os.environ['BATCH_TASK_INDEX'])]['url_s3'])")

echo "Copying from $GCS_URL to $S3_URL ($((BATCH_TASK_INDEX+1)) of $((BATCH_TASK_COUNT)))"

# If a role is given, configure the AWS CLI to assume it from long-lived base keys.
# The CLI then re-assumes the role to refresh its (1h) credentials mid-upload.
if [[ -n "${AWS_ROLE_ARN_TO_ASSUME:-}" ]]; then
  AWS_SHARED_CREDENTIALS_FILE=$(mktemp)
  AWS_CONFIG_FILE=$(mktemp)
  export AWS_SHARED_CREDENTIALS_FILE AWS_CONFIG_FILE
  chmod 600 "$AWS_SHARED_CREDENTIALS_FILE" "$AWS_CONFIG_FILE"

  cat > "$AWS_SHARED_CREDENTIALS_FILE" <<CREDS
[base]
aws_access_key_id = ${BASE_AWS_ACCESS_KEY_ID}
aws_secret_access_key = ${BASE_AWS_SECRET_ACCESS_KEY}
CREDS

  cat > "$AWS_CONFIG_FILE" <<CONF
[profile target]
role_arn = ${AWS_ROLE_ARN_TO_ASSUME}
source_profile = base
role_session_name = gcs2s3-${BATCH_TASK_INDEX}
region = ${AWS_REGION:-us-east-1}
CONF

  export AWS_PROFILE=target
fi

# apply any AWS CLI settings (e.g. s3.max_concurrent_requests) to the active profile
if [[ -n "${AWS_CONFIG_SETTINGS:-}" ]]; then
  python3 - <<'PY'
import json, os, subprocess

for key, value in json.loads(os.environ["AWS_CONFIG_SETTINGS"]).items():
    key = key.removeprefix("default.")
    subprocess.run(["aws", "configure", "set", key, str(value)], check=True)
PY
fi

# download from GCS to temp file
tmpfile=$(mktemp)
gcloud storage cp "$GCS_URL" "$tmpfile" \
  --billing-project="$GCP_PROJECT_ID" \
  --quiet

# upload to S3
read -ra s3_cp_args <<< "${S3_CP_ARGS:-}"
aws s3 cp "$tmpfile" "$S3_URL" \
  --checksum-algorithm="CRC32C" \
  --no-progress \
  --storage-class "$STORAGE_CLASS" \
  "${s3_cp_args[@]}"

rm -f "$tmpfile" "${AWS_SHARED_CREDENTIALS_FILE:-}" "${AWS_CONFIG_FILE:-}"
echo "Copy complete for $GCS_URL"

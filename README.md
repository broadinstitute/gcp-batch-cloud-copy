gcp-batch-cloud-copy
---

A [python package](https://pypi.org/project/gcp-batch-cloud-copy/) and [container specification](https://hub.docker.com/r/dmccabe606/gcp-batch-cloud-copy) to do some miscellaneous cloud storage operations on GCP Batch.

The functions below share these arguments for the Batch job:

```python
batch_args = dict(
    gcp_project_id="my-project",
    region="us-central1",
    machine_type="n2-highcpu-4",
    boot_disk_mib=102_400,  # must fit the largest file copied
    max_run_seconds=6 * 60 * 60,
    provisioning_model="SPOT",  # or "STANDARD"
    service_account_email="batch-sa@my-project.iam.gserviceaccount.com",
    container_image_uri="docker.io/dmccabe606/gcp-batch-cloud-copy:0.1.0",
)
```

## gcs2gcs.sh

Copy from GCS to GCS.

The copies run as the Batch service account, which needs access to the source and destination.

```python
from gcp_batch_cloud_copy import gcs2gcs_batch_submit

gcs2gcs_batch_submit(
    url_map=[
        {"url_src": "gs://src-bucket/a.bam", "url_dest": "gs://dest-bucket/a.bam"},
        {"url_src": "gs://src-bucket/b.bam", "url_dest": "gs://dest-bucket/b.bam"},
    ],
    **batch_args,
)
```

## gcs2s3.sh

Copy from GCS to S3.

AWS credentials are given in one of two ways. Exactly one must be provided. Static credentials fail once they expire (e.g. after 1h), so they suit short transfers:

```python
from gcp_batch_cloud_copy import gcs2s3_batch_submit

gcs2s3_batch_submit(
    url_map=[
        {"url_gcs": "gs://src-bucket/a.bam", "url_s3": "s3://dest-bucket/a.bam"},
        {"url_gcs": "gs://src-bucket/b.bam", "url_s3": "s3://dest-bucket/b.bam"},
    ],
    aws_credentials={
        "access_key_id": "AKIA...",
        "secret_access_key": "...",
        "session_token": "...",  # optional
    },
    s3_storage_class="INTELLIGENT_TIERING",
    aws_region="us-east-1",  # optional, this is the default
    aws_config={  # optional, applied with `aws configure set`
        "s3.max_concurrent_requests": 20,
        "s3.multipart_chunksize": "64MB",
    },
    aws_s3_cp_args=["--sse", "AES256"],  # optional, extra `aws s3 cp` arguments
    **batch_args,
)
```

`aws_config` also works with `aws_role` below. A leading `default.` on a key (as in `default.s3.max_concurrent_requests`) is accepted.

For long transfers, let the container assume an AWS role and refresh its own credentials. The long-lived keys of an IAM user that may assume the role are read from GCP Secret Manager, and the Batch service account needs `roles/secretmanager.secretAccessor` on them:

```python
gcs2s3_batch_submit(
    url_map=[
        {"url_gcs": "gs://src-bucket/a.bam", "url_s3": "s3://dest-bucket/a.bam"},
    ],
    aws_credentials=None,
    aws_role={
        "role_arn": "arn:aws:iam::123456789012:role/upload-role",
        "access_key_id_secret": "projects/123/secrets/aws-key-id/versions/latest",
        "secret_access_key_secret": "projects/123/secrets/aws-key-secret/versions/latest",
    },
    s3_storage_class="INTELLIGENT_TIERING",
    **batch_args,
)
```

## gcs_set_md5.sh

Set MD5 hashes for existing objects in GCS, by downloading and re-uploading each object in place.

The re-uploads run as the Batch service account, which needs read and write access to the objects, and `boot_disk_mib` must fit the largest object.

```python
from gcp_batch_cloud_copy import gcs_set_md5_batch_submit

gcs_set_md5_batch_submit(
    urls=[
        "gs://my-bucket/a.bam",
        "gs://my-bucket/b.bam",
    ],
    **batch_args,
)
```

Each function logs the submitted job and a link to track it in the Cloud Console.

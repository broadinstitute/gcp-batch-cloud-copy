import datetime
import json
import logging
from collections.abc import Hashable
from typing import Any
from uuid import uuid4

from google.cloud import batch_v1
from google.protobuf import duration_pb2

logger = logging.getLogger(__name__)


def gcs2s3_batch_submit(
    url_map: list[dict[Hashable, Any]],
    aws_credentials: dict[str, str] | None,
    s3_storage_class: str,
    gcp_project_id: str,
    region: str,
    machine_type: str,
    boot_disk_mib: int,
    max_run_seconds: int,
    provisioning_model: str,
    service_account_email: str,
    container_image_uri: str,
    aws_role: dict[str, str] | None = None,
    aws_region: str = "us-east-1",
    aws_config: dict[str, str | int] | None = None,
    aws_s3_cp_args: list[str] | None = None,
) -> None:
    """
    Copy many files from a GCP Cloud Storage bucket to an AWS S3 bucket by submitting
    them to a GCP Batch job.

    :param url_map: a list of dictionaries, with each containing keys `url_gcs` and
    `url_s3`
    :param aws_credentials: a dictionary of `access_key_id`, `secret_access_key` and
    (optional) `session_token` static AWS credentials. These can't be refreshed, so
    they fail once they expire (e.g. after 1h). Use `aws_role` for long transfers.
    Pass None if `aws_role` is given.
    :param s3_storage_class: the storage class (e.g. "INTELLIGENT_TIERING") of the
    copied objects on S3
    :param gcp_project_id: a GCP project ID
    :param region: the GCP region name to run the batch job in
    :param machine_type: the name of the machine type (e.g. "n2-highcpu-4")
    :param boot_disk_mib: the size of the boot disk in MiB
    :param max_run_seconds: maximum runtime of the job in seconds
    :param provisioning_model: VM provisioning model (e.g. "SPOT", "STANDARD", etc.)
    :param service_account_email: an email address for a service account
    :param container_image_uri: a URL for the Docker image
    :param aws_role: if given, the container assumes an AWS role itself and the AWS CLI
    refreshes the temporary credentials automatically during long uploads. A
    dictionary with keys `role_arn`, `access_key_id_secret` and
    `secret_access_key_secret` (GCP Secret Manager version resource names, e.g.
    "projects/123/secrets/name/versions/latest", holding long-lived IAM user keys
    that are allowed to assume the role). The Batch service account needs
    `roles/secretmanager.secretAccessor` on these secrets.
    :param aws_region: the AWS region name used by the AWS CLI in the container (e.g.
    the region of the destination bucket)
    :param aws_config: optional AWS CLI settings to apply in the container with `aws
    configure set`, e.g. `{"s3.max_concurrent_requests": 20, "s3.multipart_chunksize":
    "64MB"}`. They apply to the profile in use (the assumed role's profile if
    `aws_role` is given, otherwise the default profile). A leading `default.` on a key
    (as in `default.s3.max_concurrent_requests`) is accepted and ignored.
    :param aws_s3_cp_args: optional extra arguments for `aws s3 cp`, e.g.
    `["--sse", "AES256"]`. The container splits them on whitespace, so each argument
    must not contain spaces.
    """

    if (aws_credentials is None) == (aws_role is None):
        raise ValueError("Provide exactly one of aws_credentials or aws_role")

    variables = {
        "GCP_PROJECT_ID": gcp_project_id,
        "AWS_REGION": aws_region,
        "URL_MAPPING": json.dumps(url_map),
        "STORAGE_CLASS": s3_storage_class,
    }

    if aws_s3_cp_args:
        variables["S3_CP_ARGS"] = " ".join(aws_s3_cp_args)

    if aws_config:
        variables["AWS_CONFIG_SETTINGS"] = json.dumps(aws_config)

    secret_variables: dict[str, str] = {}

    if aws_credentials is not None:
        variables["AWS_ACCESS_KEY_ID"] = aws_credentials["access_key_id"]
        variables["AWS_SECRET_ACCESS_KEY"] = aws_credentials["secret_access_key"]
        variables["AWS_SESSION_TOKEN"] = aws_credentials.get("session_token", "")
    else:
        assert aws_role is not None
        # don't set AWS_* credential env vars: they'd override the refreshable profile
        variables["AWS_ROLE_ARN_TO_ASSUME"] = aws_role["role_arn"]
        secret_variables = {
            "BASE_AWS_ACCESS_KEY_ID": aws_role["access_key_id_secret"],
            "BASE_AWS_SECRET_ACCESS_KEY": aws_role["secret_access_key_secret"],
        }

    _submit_batch_job(
        script="/app/gcs2s3.sh",
        display_name="gcs2s3",
        job_id_prefix="gcs2s3-",
        task_count=len(url_map),
        variables=variables,
        secret_variables=secret_variables,
        gcp_project_id=gcp_project_id,
        region=region,
        machine_type=machine_type,
        boot_disk_mib=boot_disk_mib,
        max_run_seconds=max_run_seconds,
        provisioning_model=provisioning_model,
        service_account_email=service_account_email,
        container_image_uri=container_image_uri,
    )


def gcs2gcs_batch_submit(
    url_map: list[dict[Hashable, Any]],
    gcp_project_id: str,
    region: str,
    machine_type: str,
    boot_disk_mib: int,
    max_run_seconds: int,
    provisioning_model: str,
    service_account_email: str,
    container_image_uri: str,
) -> None:
    """
    Copy many files between GCP Cloud Storage buckets by submitting them to a GCP
    Batch job.

    The copies run as the Batch job's service account, which needs access to the
    source and destination.

    :param url_map: a list of dictionaries, with each containing keys `url_src` and
    `url_dest`
    :param gcp_project_id: a GCP project ID
    :param region: the GCP region name to run the batch job in
    :param machine_type: the name of the machine type (e.g. "n2-highcpu-4")
    :param boot_disk_mib: the size of the boot disk in MiB
    :param max_run_seconds: maximum runtime of the job in seconds
    :param provisioning_model: VM provisioning model (e.g. "SPOT", "STANDARD", etc.)
    :param service_account_email: an email address for a service account
    :param container_image_uri: a URL for the Docker image
    """

    _submit_batch_job(
        script="/app/gcs2gcs.sh",
        display_name="gcs2gcs",
        job_id_prefix="gcs2gcs-",
        task_count=len(url_map),
        variables={
            "GCP_PROJECT_ID": gcp_project_id,
            "URL_MAPPING": json.dumps(url_map),
        },
        secret_variables={},
        gcp_project_id=gcp_project_id,
        region=region,
        machine_type=machine_type,
        boot_disk_mib=boot_disk_mib,
        max_run_seconds=max_run_seconds,
        provisioning_model=provisioning_model,
        service_account_email=service_account_email,
        container_image_uri=container_image_uri,
    )


def gcs_set_md5_batch_submit(
    urls: list[str],
    gcp_project_id: str,
    region: str,
    machine_type: str,
    boot_disk_mib: int,
    max_run_seconds: int,
    provisioning_model: str,
    service_account_email: str,
    container_image_uri: str,
) -> None:
    """
    Set the MD5 hash of existing objects in GCP Cloud Storage by submitting them to a
    GCP Batch job. Each object is downloaded and re-uploaded in place without
    parallel composite uploads, so that GCS records an MD5 hash.

    The re-uploads run as the Batch job's service account, which needs read and write
    access to the objects.

    :param urls: a list of `gs://` object URLs
    :param gcp_project_id: a GCP project ID
    :param region: the GCP region name to run the batch job in
    :param machine_type: the name of the machine type (e.g. "n2-highcpu-4")
    :param boot_disk_mib: the size of the boot disk in MiB (must fit the largest object)
    :param max_run_seconds: maximum runtime of the job in seconds
    :param provisioning_model: VM provisioning model (e.g. "SPOT", "STANDARD", etc.)
    :param service_account_email: an email address for a service account
    :param container_image_uri: a URL for the Docker image
    """

    _submit_batch_job(
        script="/app/gcs_set_md5.sh",
        display_name="gcs-set-md5",
        job_id_prefix="gcs-set-md5-",
        task_count=len(urls),
        variables={"GCP_PROJECT_ID": gcp_project_id, "URLS": json.dumps(urls)},
        secret_variables={},
        gcp_project_id=gcp_project_id,
        region=region,
        machine_type=machine_type,
        boot_disk_mib=boot_disk_mib,
        max_run_seconds=max_run_seconds,
        provisioning_model=provisioning_model,
        service_account_email=service_account_email,
        container_image_uri=container_image_uri,
    )


def _submit_batch_job(
    script: str,
    display_name: str,
    job_id_prefix: str,
    task_count: int,
    variables: dict[str, str],
    secret_variables: dict[str, str],
    gcp_project_id: str,
    region: str,
    machine_type: str,
    boot_disk_mib: int,
    max_run_seconds: int,
    provisioning_model: str,
    service_account_email: str,
    container_image_uri: str,
) -> None:
    """
    Submit a GCP Batch job with `task_count` tasks, each running `script`
    in the container. The script uses the ENV var BATCH_TASK_INDEX to identify which
    item it is processing.
    """

    instance_policy = batch_v1.AllocationPolicy.InstancePolicy()
    instance_policy.machine_type = machine_type
    instance_policy.provisioning_model = getattr(
        batch_v1.AllocationPolicy.ProvisioningModel, provisioning_model
    )

    instances = batch_v1.AllocationPolicy.InstancePolicyOrTemplate()
    instances.policy = instance_policy

    service_account = batch_v1.ServiceAccount()
    service_account.email = service_account_email

    allocation_policy = batch_v1.AllocationPolicy()
    allocation_policy.instances = [instances]
    allocation_policy.service_account = service_account

    logs_policy = batch_v1.LogsPolicy()
    logs_policy.destination = batch_v1.LogsPolicy.Destination.CLOUD_LOGGING

    container = batch_v1.Runnable.Container()
    container.image_uri = container_image_uri
    container.entrypoint = "/bin/bash"
    container.commands = ["-c", script]
    # ENV var BATCH_TASK_INDEX will identify which URL mapping is being processed

    runnable = batch_v1.Runnable()
    runnable.display_name = display_name
    runnable.container = container

    compute_resource = batch_v1.ComputeResource()
    compute_resource.cpu_milli = 1000  # 1 vCPU needed per task
    compute_resource.memory_mib = 500  # 500 MiB needed per task
    compute_resource.boot_disk_mib = boot_disk_mib

    task_spec = batch_v1.TaskSpec()
    task_spec.runnables = [runnable]
    task_spec.compute_resource = compute_resource
    task_spec.max_retry_count = 0
    task_spec.max_run_duration = duration_pb2.Duration(seconds=max_run_seconds)

    task_group = batch_v1.TaskGroup()
    task_group.task_count = task_count
    # let Batch calculate task_group.parallelism and task_group.task_count_per_node

    env = batch_v1.Environment()
    env.variables = variables
    if secret_variables:
        env.secret_variables = secret_variables
    task_spec.environment = env

    task_group.task_spec = task_spec

    job = batch_v1.Job()
    job.allocation_policy = allocation_policy
    job.logs_policy = logs_policy
    job.task_groups = [task_group]

    job_request = batch_v1.CreateJobRequest()
    job_request.job = job
    job_id = make_batch_job_id(job_id_prefix)
    job_request.job_id = job_id
    job_request.parent = f"projects/{gcp_project_id}/locations/{region}"

    batch_client = batch_v1.BatchServiceClient()

    res = batch_client.create_job(job_request)
    logger.info(f"Job submitted: {res.name} (uid: {res.uid})")
    logger.info(
        f"Track at https://console.cloud.google.com/batch/jobsDetail/regions/{region}"
        f"/jobs/{job_id}/details?project={gcp_project_id}"
    )


def make_batch_job_id(prefix: str = "gcs2s3-") -> str:
    """
    Generate a valid job ID for GCP Batch that shows the current date and a random
    string, while not exceeding the 63 character limit.

    :param prefix: a prefix for the job ID (e.g. "gcs2gcs-")
    :return: an ID to use as the GCP Batch job ID
    """

    job_id_parts = [
        prefix,
        datetime.datetime.now().strftime("%Y-%m-%d"),
        str(uuid4()).split("-")[0],
    ]

    avail_job_id_len = 63 - (len(job_id_parts[1]) + len(job_id_parts[2]) + 2)
    job_id_parts[0] = job_id_parts[0][:avail_job_id_len]

    return "-".join(job_id_parts)

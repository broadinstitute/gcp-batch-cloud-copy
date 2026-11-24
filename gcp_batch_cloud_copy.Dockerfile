FROM debian:bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      curl \
      ca-certificates \
      python3 \
      python3-pip \
      unzip \
      gnupg && \
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip && \
    unzip awscliv2.zip && \
    ./aws/install && \
    rm -rf aws awscliv2.zip && \
    echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
      | tee /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg \
      | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg && \
    apt-get update && \
    apt-get install -y google-cloud-cli && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY ./gcs2s3.sh /app/gcs2s3.sh
COPY ./gcs2gcs.sh /app/gcs2gcs.sh
COPY ./gcs_set_md5.sh /app/gcs_set_md5.sh

RUN chmod +x /app/gcs2s3.sh
RUN chmod +x /app/gcs2gcs.sh
RUN chmod +x /app/gcs_set_md5.sh

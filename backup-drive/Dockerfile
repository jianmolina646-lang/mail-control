FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates rclone python3 openssl gzip \
    && rm -rf /var/lib/apt/lists/*
COPY mirror.py /app/mirror.py
ENV PYTHONUNBUFFERED=1
CMD ["python3", "/app/mirror.py"]

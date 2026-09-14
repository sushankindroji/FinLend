# FinLend backend (FastAPI) — container image.
# Builds the existing application unchanged; only packages it for Docker.

FROM python:3.11-slim

WORKDIR /app

# System deps needed to build a couple of python wheels (bcrypt/cryptography)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies first for better layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the existing application source (unchanged).
COPY . .

# Make the entrypoint script executable.
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]

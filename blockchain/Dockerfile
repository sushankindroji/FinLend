# FinLend blockchain (Hardhat local node + contract deployment) — container image.
# Packages the existing Hardhat project unchanged.

FROM node:20-bookworm-slim

WORKDIR /app

# build-essential/python3 are needed to build native deps used by Hardhat
# (keccak, secp256k1) on some platforms/architectures.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential python3 curl \
    && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8545

ENTRYPOINT ["/app/docker-entrypoint.sh"]

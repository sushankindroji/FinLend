#!/bin/sh
# Docker entrypoint for the FinLend backend.
#
# This does NOT change any application behavior. It only:
#   1. Optionally waits a short time for the blockchain container to finish
#      deploying the LoanRegistry contract and publish its address, so the
#      backend can pick up CONTRACT_ADDRESS automatically.
#   2. Starts the existing FastAPI app with uvicorn exactly as before.
#
# If the blockchain container/address never appears, the backend still
# starts normally -- app/services/blockchain_service.py already falls back
# to LOCAL_SIMULATION mode on its own, so this script never blocks startup
# indefinitely.
set -e

DEPLOYED_ADDRESS_FILE="/blockchain/deployed-address.json"
MAX_WAIT_SECONDS="${BLOCKCHAIN_WAIT_SECONDS:-60}"

if [ "${BLOCKCHAIN_ENABLED:-true}" = "true" ] && [ -z "${CONTRACT_ADDRESS}" ]; then
  echo "[entrypoint] Waiting up to ${MAX_WAIT_SECONDS}s for blockchain contract deployment..."
  waited=0
  while [ ! -f "$DEPLOYED_ADDRESS_FILE" ] && [ "$waited" -lt "$MAX_WAIT_SECONDS" ]; do
    sleep 2
    waited=$((waited + 2))
  done

  if [ -f "$DEPLOYED_ADDRESS_FILE" ]; then
    ADDR=$(python -c "import json,sys; print(json.load(open('$DEPLOYED_ADDRESS_FILE'))['address'])" 2>/dev/null || true)
    if [ -n "$ADDR" ]; then
      export CONTRACT_ADDRESS="$ADDR"
      echo "[entrypoint] Using deployed contract address: $CONTRACT_ADDRESS"
    fi
  else
    echo "[entrypoint] No deployed contract address found after ${MAX_WAIT_SECONDS}s -- backend will start in LOCAL_SIMULATION mode."
  fi
fi

echo "[entrypoint] Starting FastAPI backend..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

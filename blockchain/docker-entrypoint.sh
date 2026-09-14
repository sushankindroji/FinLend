#!/bin/sh
# Docker entrypoint for the FinLend blockchain container.
#
# Reuses the project's existing Hardhat scripts unchanged:
#   1. Starts the local Hardhat node (same as `npx hardhat node`).
#   2. Waits for its JSON-RPC endpoint to be ready.
#   3. Runs the existing deploy script (scripts/deploy.js), which already
#      writes deployed-address.json -- we don't reimplement that logic.
#   4. Keeps the node running in the foreground so the container stays up
#      and the backend can keep talking to it over the Docker network.
set -e

echo "[blockchain] Starting Hardhat local node..."
npx hardhat node --hostname 0.0.0.0 &
NODE_PID=$!

echo "[blockchain] Waiting for RPC at http://127.0.0.1:8545 ..."
attempt=0
until curl -s -X POST http://127.0.0.1:8545 \
  -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}' >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 60 ]; then
    echo "[blockchain] ERROR: Hardhat node did not become ready in time."
    exit 1
  fi
  sleep 1
done
echo "[blockchain] Hardhat node is ready."

# The in-memory Hardhat node starts fresh every container run, so the
# contract must be (re)deployed each time the node (re)starts. This reuses
# the existing deploy script unchanged; it overwrites deployed-address.json
# with the address for this run.
echo "[blockchain] Deploying LoanRegistry contract..."
npx hardhat run scripts/deploy.js --network localhost

echo "[blockchain] Ready. Following Hardhat node process..."
wait "$NODE_PID"

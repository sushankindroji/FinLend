"""Web3 integration layer.

Talks to the local Hardhat node (or any Ethereum-compatible network) running
the LoanRegistry smart contract (see /blockchain). If the node/contract is
unreachable, falls back to a clearly-labeled LOCAL_SIMULATION mode so the
rest of the demo flow keeps working -- this fallback NEVER fabricates a
transaction hash; it generates a deterministic pseudo-hash prefixed with
"SIMULATED-" so it can never be confused with a real on-chain hash
(honors req #59: do not fake blockchain events).
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid

from web3 import Web3

from app.core.config import get_settings

logger = logging.getLogger("finlend.blockchain")

_ARTIFACT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "blockchain", "artifacts",
    "contracts", "LoanRegistry.sol", "LoanRegistry.json"
)


class BlockchainService:
    def __init__(self):
        settings = get_settings()
        self.settings = settings
        self.enabled = settings.blockchain_enabled
        self.w3: Web3 | None = None
        self.contract = None
        self.account = None
        self.mode = "DISABLED"

        if not self.enabled:
            return

        try:
            self.w3 = Web3(Web3.HTTPProvider(settings.web3_provider_uri, request_kwargs={"timeout": 3}))
            if not self.w3.is_connected():
                raise ConnectionError("Web3 provider not reachable")

            if settings.deployer_private_key:
                self.account = self.w3.eth.account.from_key(settings.deployer_private_key)
            else:
                accounts = self.w3.eth.accounts
                self.account = accounts[0] if accounts else None

            # Auto-discover deployed address from /blockchain/deployed-address.json if not set in env
            contract_address = settings.contract_address
            candidate_address_files = [
                "/blockchain/deployed-address.json",
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "blockchain", "deployed-address.json"),
            ]
            if not contract_address:
                for af in candidate_address_files:
                    if os.path.exists(af):
                        try:
                            with open(af) as f:
                                data = json.load(f)
                                contract_address = data.get("address")
                                if contract_address:
                                    logger.info("Auto-discovered contract address %s from %s", contract_address, af)
                                    break
                        except Exception as e:
                            logger.warning("Could not read address file %s: %e", af, e)

            # Auto-discover artifact path
            candidate_artifacts = [
                "/blockchain/artifacts/contracts/LoanRegistry.sol/LoanRegistry.json",
                _ARTIFACT_PATH,
            ]
            artifact_file = None
            for art in candidate_artifacts:
                if os.path.exists(art):
                    artifact_file = art
                    break

            if contract_address and artifact_file:
                with open(artifact_file) as f:
                    artifact = json.load(f)
                self.contract = self.w3.eth.contract(
                    address=Web3.to_checksum_address(contract_address),
                    abi=artifact["abi"],
                )
                self.mode = "ON_CHAIN"
                logger.info("Blockchain service connected in ON_CHAIN mode at %s (contract: %s)", settings.web3_provider_uri, contract_address)
            else:
                self.mode = "LOCAL_SIMULATION"
                logger.warning(
                    "Contract address (%s) or artifact (%s) not found -- falling back to LOCAL_SIMULATION mode",
                    contract_address, artifact_file
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Blockchain unreachable (%s). Falling back to LOCAL_SIMULATION mode.", exc)
            self.mode = "LOCAL_SIMULATION"

    # -- helpers ------------------------------------------------------
    def _simulated_hash(self, prefix: str) -> str:
        return f"SIMULATED-{prefix}-{uuid.uuid4().hex}"

    def _send(self, fn_call):
        assert self.w3 is not None and self.account is not None
        sender = self.account if isinstance(self.account, str) else self.account.address
        tx = fn_call.build_transaction({
            "from": sender,
            "nonce": self.w3.eth.get_transaction_count(sender),
        })
        if isinstance(self.account, str):
            tx_hash = self.w3.eth.send_transaction(tx)
        else:
            signed = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        return receipt.transactionHash.hex()

    # -- public API -----------------------------------------------------
    def record_funding(self, loan_id: str, lender_ref: str, amount_wei: int) -> dict:
        if self.mode == "ON_CHAIN":
            try:
                receipt_hash = self._send(
                    self.contract.functions.recordFunding(loan_id, lender_ref, amount_wei)
                )
                return {"tx_hash": receipt_hash, "mode": self.mode, "timestamp": int(time.time())}
            except Exception as exc:  # noqa: BLE001
                logger.error("On-chain recordFunding failed, using simulation fallback: %s", exc)

        return {"tx_hash": self._simulated_hash("FUND"), "mode": "LOCAL_SIMULATION", "timestamp": int(time.time())}

    def record_repayment(self, loan_id: str, borrower_ref: str, amount_wei: int) -> dict:
        if self.mode == "ON_CHAIN":
            try:
                receipt_hash = self._send(
                    self.contract.functions.recordRepayment(loan_id, borrower_ref, amount_wei)
                )
                return {"tx_hash": receipt_hash, "mode": self.mode, "timestamp": int(time.time())}
            except Exception as exc:  # noqa: BLE001
                logger.error("On-chain recordRepayment failed, using simulation fallback: %s", exc)

        return {"tx_hash": self._simulated_hash("REPAY"), "mode": "LOCAL_SIMULATION", "timestamp": int(time.time())}

    def explorer_url(self, tx_hash: str) -> str | None:
        if tx_hash.startswith("SIMULATED-"):
            return None
        base = self.settings.block_explorer_base_url
        return f"{base.rstrip('/')}/tx/{tx_hash}" if base else None


_service: BlockchainService | None = None


def get_blockchain_service() -> BlockchainService:
    global _service
    if _service is None:
        _service = BlockchainService()
    return _service

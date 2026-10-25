"""Blockchain transparency and verification API.

Provides transaction details and blockchain verification features.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security import get_current_user
from app.db.mongodb import get_db
from app.services import loan_service
from app.services.blockchain_service import get_blockchain_service

router = APIRouter(prefix="/api/blockchain", tags=["blockchain"])


@router.get("/transaction/{tx_hash}")
async def get_transaction_details(
    tx_hash: str,
    user=Depends(get_current_user),
):
    """
    Get blockchain transaction details.
    
    Returns transaction information including:
    - Transaction hash
    - Block number
    - Timestamp
    - Status (pending, confirmed, failed)
    - Type (funding, repayment)
    - Amount
    """
    blockchain = get_blockchain_service()
    
    # Check if this is a simulated transaction
    if tx_hash.startswith("SIMULATED-"):
        return {
            "tx_hash": tx_hash,
            "mode": "LOCAL_SIMULATION",
            "status": "simulated",
            "message": "This is a simulated transaction for development/testing purposes.",
            "explorer_url": None,
        }
    
    # For real transactions, query the blockchain
    if blockchain.w3 is None or blockchain.mode != "ON_CHAIN":
        return {
            "tx_hash": tx_hash,
            "mode": blockchain.mode,
            "status": "unavailable",
            "message": "Blockchain connection not available.",
        }
    
    try:
        tx = blockchain.w3.eth.get_transaction(tx_hash)
        receipt = blockchain.w3.eth.get_transaction_receipt(tx_hash)
        block = blockchain.w3.eth.get_block(receipt['blockNumber'])
        
        return {
            "tx_hash": tx_hash,
            "mode": "ON_CHAIN",
            "status": "confirmed" if receipt['status'] == 1 else "failed",
            "block_number": receipt['blockNumber'],
            "block_timestamp": block['timestamp'],
            "from_address": tx['from'],
            "to_address": tx['to'],
            "gas_used": receipt['gasUsed'],
            "confirmations": blockchain.w3.eth.block_number - receipt['blockNumber'],
            "explorer_url": blockchain.explorer_url(tx_hash),
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Transaction not found: {str(e)}")


@router.get("/loan/{loan_id}/transactions")
async def get_loan_transactions(
    loan_id: str,
    user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Get all blockchain transactions for a specific loan.
    
    Returns funding and repayment transactions with details.
    """
    # Verify loan exists and user has access
    loan = await db.loans.find_one({"_id": loan_service.oid(loan_id)})
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    
    # Check access (borrower, lenders, or admin)
    borrower_id = str(loan.get("borrower_id", ""))
    is_borrower = borrower_id == user["id"]
    is_admin = user["role"] == "admin"
    
    # Check if user is a lender on this loan
    is_lender = False
    if user["role"] == "lender":
        funding_count = await db.loan_fundings.count_documents({
            "loan_id": loan["_id"],
            "lender_id": loan_service.oid(user["id"]),
        })
        is_lender = funding_count > 0
    
    if not (is_borrower or is_lender or is_admin):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get all transactions
    transactions = []
    
    # Funding transactions
    async for funding in db.loan_fundings.find({"loan_id": loan["_id"]}):
        transactions.append({
            "type": "FUNDING",
            "tx_hash": funding.get("tx_hash"),
            "amount": funding.get("amount"),
            "chain_mode": funding.get("chain_mode"),
            "created_at": funding.get("created_at"),
            "lender_id": str(funding.get("lender_id")),
        })
    
    # Repayment transactions
    async for repayment in db.repayments.find({"loan_id": loan["_id"]}):
        transactions.append({
            "type": "REPAYMENT",
            "tx_hash": repayment.get("tx_hash"),
            "amount": repayment.get("amount"),
            "chain_mode": repayment.get("chain_mode"),
            "created_at": repayment.get("created_at"),
            "is_on_time": repayment.get("is_on_time"),
            "days_late": repayment.get("days_late"),
        })
    
    # Sort by timestamp
    transactions.sort(key=lambda x: x.get("created_at", ""), reverse=False)
    
    return {
        "loan_id": loan_id,
        "loan_amount": loan["amount"],
        "loan_status": loan["status"],
        "transactions": transactions,
        "total_transactions": len(transactions),
    }


@router.get("/verify/loan/{loan_id}")
async def verify_loan_on_chain(
    loan_id: str,
    user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Verify loan's blockchain integrity.
    
    Compares database records with blockchain state.
    """
    # Get loan
    loan = await db.loans.find_one({"_id": loan_service.oid(loan_id)})
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    
    blockchain = get_blockchain_service()
    
    if blockchain.mode != "ON_CHAIN":
        return {
            "loan_id": loan_id,
            "verified": False,
            "mode": blockchain.mode,
            "message": "Blockchain verification not available in current mode.",
        }
    
    # Get all transactions
    funding_txs = []
    async for funding in db.loan_fundings.find({"loan_id": loan["_id"]}):
        funding_txs.append({
            "tx_hash": funding.get("tx_hash"),
            "amount": funding.get("amount"),
            "type": "funding",
        })
    
    repayment_txs = []
    async for repayment in db.repayments.find({"loan_id": loan["_id"]}):
        repayment_txs.append({
            "tx_hash": repayment.get("tx_hash"),
            "amount": repayment.get("amount"),
            "type": "repayment",
        })
    
    all_txs = funding_txs + repayment_txs
    
    verified_txs = []
    failed_txs = []
    
    for tx in all_txs:
        tx_hash = tx["tx_hash"]
        if tx_hash.startswith("SIMULATED-"):
            verified_txs.append({**tx, "status": "simulated"})
        else:
            try:
                receipt = blockchain.w3.eth.get_transaction_receipt(tx_hash)
                if receipt['status'] == 1:
                    verified_txs.append({**tx, "status": "confirmed"})
                else:
                    failed_txs.append({**tx, "status": "failed"})
            except Exception:
                failed_txs.append({**tx, "status": "not_found"})
    
    return {
        "loan_id": loan_id,
        "verified": len(failed_txs) == 0,
        "total_transactions": len(all_txs),
        "verified_transactions": len(verified_txs),
        "failed_transactions": len(failed_txs),
        "mode": blockchain.mode,
        "details": {
            "verified": verified_txs,
            "failed": failed_txs,
        },
    }


@router.get("/status")
async def get_blockchain_status(
    user=Depends(get_current_user),
):
    """
    Get current blockchain connection status.
    
    Returns network info, mode, and connectivity status.
    """
    blockchain = get_blockchain_service()
    
    if blockchain.mode == "DISABLED":
        return {
            "enabled": False,
            "mode": "DISABLED",
            "message": "Blockchain integration is disabled.",
        }
    
    if blockchain.mode == "LOCAL_SIMULATION":
        return {
            "enabled": True,
            "mode": "LOCAL_SIMULATION",
            "message": "Running in local simulation mode (no real blockchain).",
            "connected": False,
        }
    
    # ON_CHAIN mode
    try:
        block_number = blockchain.w3.eth.block_number
        chain_id = blockchain.w3.eth.chain_id
        
        return {
            "enabled": True,
            "mode": "ON_CHAIN",
            "connected": True,
            "network": blockchain.settings.blockchain_network_name,
            "provider_uri": blockchain.settings.web3_provider_uri,
            "contract_address": blockchain.settings.contract_address,
            "current_block": block_number,
            "chain_id": chain_id,
        }
    except Exception as e:
        return {
            "enabled": True,
            "mode": "ON_CHAIN",
            "connected": False,
            "error": str(e),
        }

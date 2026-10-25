"""Real-time update service using WebSockets.

Provides live updates for:
- Loan funding progress
- Marketplace activity
- Notifications
- Status changes
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

logger = logging.getLogger("finlend.realtime")


class RealtimeService:
    """Manages WebSocket connections and real-time broadcasts."""
    
    def __init__(self):
        # user_id -> Set of websocket connections
        self.user_connections: Dict[str, Set] = {}
        
        # loan_id -> Set of websocket connections (for loan-specific updates)
        self.loan_watchers: Dict[str, Set] = {}
        
        # Global connections (marketplace feed)
        self.marketplace_connections: Set = set()
    
    async def connect_user(self, user_id: str, websocket) -> None:
        """Register a user's websocket connection."""
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        
        self.user_connections[user_id].add(websocket)
        logger.info(f"User {user_id} connected (total: {len(self.user_connections[user_id])})")
    
    async def disconnect_user(self, user_id: str, websocket) -> None:
        """Unregister a user's websocket connection."""
        if user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
            logger.info(f"User {user_id} disconnected")
    
    async def watch_loan(self, loan_id: str, websocket) -> None:
        """Register connection to watch specific loan."""
        if loan_id not in self.loan_watchers:
            self.loan_watchers[loan_id] = set()
        
        self.loan_watchers[loan_id].add(websocket)
        logger.info(f"Watching loan {loan_id} (watchers: {len(self.loan_watchers[loan_id])})")
    
    async def unwatch_loan(self, loan_id: str, websocket) -> None:
        """Unregister connection from watching loan."""
        if loan_id in self.loan_watchers:
            self.loan_watchers[loan_id].discard(websocket)
            if not self.loan_watchers[loan_id]:
                del self.loan_watchers[loan_id]
    
    async def connect_marketplace(self, websocket) -> None:
        """Connect to marketplace feed."""
        self.marketplace_connections.add(websocket)
        logger.info(f"Marketplace connection added (total: {len(self.marketplace_connections)})")
    
    async def disconnect_marketplace(self, websocket) -> None:
        """Disconnect from marketplace feed."""
        self.marketplace_connections.discard(websocket)
        logger.info(f"Marketplace connection removed")
    
    async def notify_user(self, user_id: str, event_type: str, data: Dict) -> None:
        """Send notification to specific user."""
        if user_id not in self.user_connections:
            return
        
        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # Send to all user's connections
        dead_connections = set()
        for ws in self.user_connections[user_id]:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to user {user_id}: {e}")
                dead_connections.add(ws)
        
        # Clean up dead connections
        for ws in dead_connections:
            await self.disconnect_user(user_id, ws)
    
    async def notify_loan_watchers(self, loan_id: str, event_type: str, data: Dict) -> None:
        """Send update to all watchers of a specific loan."""
        if loan_id not in self.loan_watchers:
            return
        
        message = {
            "type": event_type,
            "loan_id": loan_id,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        dead_connections = set()
        for ws in self.loan_watchers[loan_id]:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send loan update: {e}")
                dead_connections.add(ws)
        
        # Clean up
        for ws in dead_connections:
            await self.unwatch_loan(loan_id, ws)
    
    async def broadcast_marketplace(self, event_type: str, data: Dict) -> None:
        """Broadcast to all marketplace connections."""
        if not self.marketplace_connections:
            return
        
        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        dead_connections = set()
        for ws in self.marketplace_connections:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to broadcast to marketplace: {e}")
                dead_connections.add(ws)
        
        # Clean up
        for ws in dead_connections:
            await self.disconnect_marketplace(ws)
    
    async def broadcast_funding_progress(
        self,
        loan_id: str,
        loan_amount: float,
        amount_funded: float,
        lender_id: str,
        contribution: float,
        status: str,
    ) -> None:
        """Broadcast loan funding progress."""
        progress_percent = round((amount_funded / loan_amount) * 100, 1)
        
        data = {
            "loan_id": loan_id,
            "loan_amount": loan_amount,
            "amount_funded": amount_funded,
            "remaining": loan_amount - amount_funded,
            "progress_percent": progress_percent,
            "latest_contribution": contribution,
            "lender_id": lender_id,
            "status": status,
        }
        
        # Notify loan watchers
        await self.notify_loan_watchers(loan_id, "funding_progress", data)
        
        # Broadcast to marketplace
        await self.broadcast_marketplace("loan_funded", data)
    
    async def broadcast_loan_status_change(
        self,
        loan_id: str,
        old_status: str,
        new_status: str,
        borrower_id: Optional[str] = None,
    ) -> None:
        """Broadcast loan status change."""
        data = {
            "loan_id": loan_id,
            "old_status": old_status,
            "new_status": new_status,
        }
        
        # Notify loan watchers
        await self.notify_loan_watchers(loan_id, "status_change", data)
        
        # Notify borrower if provided
        if borrower_id:
            await self.notify_user(borrower_id, "loan_status_changed", data)
        
        # Broadcast major status changes to marketplace
        if new_status in ("OPEN_FOR_FUNDING", "FUNDED", "ACTIVE"):
            await self.broadcast_marketplace("loan_status_changed", data)
    
    async def broadcast_repayment(
        self,
        loan_id: str,
        borrower_id: str,
        amount: float,
        remaining: float,
        is_final: bool,
    ) -> None:
        """Broadcast repayment event."""
        data = {
            "loan_id": loan_id,
            "borrower_id": borrower_id,
            "amount": amount,
            "remaining": remaining,
            "is_final": is_final,
        }
        
        # Notify loan watchers
        await self.notify_loan_watchers(loan_id, "repayment_made", data)
        
        # Notify borrower
        await self.notify_user(borrower_id, "repayment_recorded", data)
    
    def get_stats(self) -> Dict:
        """Get current connection statistics."""
        return {
            "active_users": len(self.user_connections),
            "total_user_connections": sum(len(conns) for conns in self.user_connections.values()),
            "watched_loans": len(self.loan_watchers),
            "marketplace_connections": len(self.marketplace_connections),
        }


# Global service instance
_realtime_service: Optional[RealtimeService] = None


def get_realtime_service() -> RealtimeService:
    """Get singleton realtime service."""
    global _realtime_service
    if _realtime_service is None:
        _realtime_service = RealtimeService()
    return _realtime_service

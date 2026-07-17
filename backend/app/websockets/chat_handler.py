from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import json

from app.agents.whatsapp import (
    conversations, 
    ConversationStage,
    handle_confirm_response,
    handle_prepay_response,
    send_prepay_nudge
)
from app.agents.message_generator import generate_confirmation_message

# We use APIRouter so we can easily plug this into main.py
router = APIRouter()

active_connections: dict[str, WebSocket] = {}

def dict_to_label(action: str) -> str:
    """Convert button action ID to display text."""
    labels = {
        "confirm": "✅ Confirm Order",
        "cancel": "❌ Cancel Order",
        "prepay": "💰 Pay Now",
        "cod": "🚚 Keep COD",
    }
    return labels.get(action, action)

@router.get("/chat/{order_id}/history")
def get_chat_history(order_id: str):
    """Debug endpoint to view the raw conversation JSON."""
    conv = conversations.get(order_id)
    if not conv:
        return {"error": "Conversation not found"}
    return {
        "order_id": order_id,
        "stage": conv.stage,
        "outcome": conv.outcome,
        "messages": conv.messages
    }

@router.websocket("/ws/chat/{order_id}")
async def chat_websocket(websocket: WebSocket, order_id: str):
    """WebSocket endpoint for WhatsApp-style chat."""
    
    await websocket.accept()
    active_connections[order_id] = websocket
    
    try:
        # Get conversation from memory store
        conv = conversations.get(order_id)
        if not conv:
            await websocket.send_json({"error": "Order not found. Process order first."})
            await asyncio.sleep(1)
            await websocket.close()
            return
            
        # --- PHASE 1: Send greeting ---
        if conv.stage == ConversationStage.GREETING:
            # Typing indicator (makes it feel real)
            await websocket.send_json({"type": "typing", "duration": 1500})
            await asyncio.sleep(1.5)
            
            # Generate and send confirmation message
            msg = generate_confirmation_message(conv.order_state)
            conv.add_message("bot", msg["text"], msg["buttons"])
            conv.stage = ConversationStage.AWAITING_CONFIRM
            
            await websocket.send_json({
                "type": "message",
                "sender": "bot",
                "text": msg["text"],
                "buttons": msg["buttons"],
                "timestamp": conv.messages[-1]["timestamp"],
            })
            
        # --- PHASE 2: Listen for responses ---
        while conv.stage != ConversationStage.RESOLVED:
            try:
                # Wait for user message (10s for confirm, 60s for prepay)
                wait_time = 10.0 if conv.stage == ConversationStage.AWAITING_CONFIRM else 60.0
                raw = await asyncio.wait_for(
                    websocket.receive_text(), 
                    timeout=wait_time          
                )
                data = json.loads(raw)
                user_action = data.get("action", "")
                user_text = data.get("text", "")
                
                # Log user message
                display_text = user_text or dict_to_label(user_action)
                conv.add_message("user", display_text)
                
                # Handle based on current stage
                if conv.stage == ConversationStage.AWAITING_CONFIRM:
                    await handle_confirm_response(websocket, conv, user_action)
                    
                elif conv.stage == ConversationStage.AWAITING_PREPAY:
                    await handle_prepay_response(websocket, conv, user_action)
                    
            except asyncio.TimeoutError:
                if conv.stage == ConversationStage.AWAITING_CONFIRM:
                    # User hesitated for 10 seconds -> send prepay nudge!
                    await send_prepay_nudge(websocket, conv)
                else:
                    # User didn't respond to the nudge in time
                    conv.outcome = "TIMEOUT"
                    conv.stage = ConversationStage.RESOLVED
                    text = "⏰ No response received. Order has been escalated for manual review."
                    conv.add_message("bot", text)
                    await websocket.send_json({
                        "type": "message",
                        "sender": "bot",
                        "text": text,
                        "timestamp": conv.messages[-1]["timestamp"],
                    })
                
        # --- PHASE 3: Send final outcome to frontend ---
        await websocket.send_json({
            "type": "outcome",
            "outcome": conv.outcome,
            "order_id": order_id,
        })
        
    except WebSocketDisconnect:
        pass
    finally:
        active_connections.pop(order_id, None)

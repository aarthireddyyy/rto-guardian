from enum import Enum
from datetime import datetime
from fastapi import WebSocket
import asyncio

from app.models.schemas import OrderState
from app.agents.message_generator import generate_prepay_nudge

class ConversationStage(str, Enum):
    GREETING = "greeting"
    AWAITING_CONFIRM = "awaiting_confirm"
    PREPAY_NUDGE = "prepay_nudge"
    AWAITING_PREPAY = "awaiting_prepay"
    RESOLVED = "resolved"

class Conversation:
    """Tracks one WhatsApp conversation for one order."""
    
    def __init__(self, order_id: str, order_state: dict):
        self.order_id = order_id
        self.order_state = order_state
        self.stage = ConversationStage.GREETING
        self.messages = []           # chat history
        self.started_at = datetime.now()
        self.outcome = None          # CONFIRMED / DECLINED / PREPAID / TIMEOUT
    
    def add_message(self, sender: str, text: str, buttons: list = None):
        """Add a message to the conversation history."""
        self.messages.append({
            "id": f"msg_{len(self.messages)+1}",
            "sender": sender,         # "bot" or "user"
            "text": text,
            "buttons": buttons,       
            "timestamp": datetime.now().isoformat(),
        })

# In-memory store (good enough for MVP)
conversations: dict[str, Conversation] = {}

async def whatsapp_agent(state: OrderState) -> dict:
    """LangGraph node: Initialize WhatsApp conversation for this order."""
    
    # We ensure we have an order_id. LangGraph state is typically a dict
    order_id = state.get("order_id", f"ord_{int(datetime.now().timestamp())}")
    
    # Create a conversation object (stored in memory)
    conv = Conversation(
        order_id=order_id,
        order_state=state,
    )
    conversations[order_id] = conv
    
    # The actual chat will be handled by the WebSocket endpoint
    # This node just sets up the conversation and marks it as pending.
    return {
        "agent_type": "whatsapp",
        "agent_outcome": "PENDING",
        "agent_message": f"WhatsApp conversation initialized. Connect to WebSocket for order: {order_id}",
    }

# --- WebSocket Response Handlers ---

async def handle_confirm_response(ws: WebSocket, conv: Conversation, action: str):
    """Handle user's response to confirmation message."""
    
    if action == "confirm":
        conv.outcome = "CONFIRMED"
        conv.stage = ConversationStage.RESOLVED
        
        await ws.send_json({"type": "typing", "duration": 1000})
        await asyncio.sleep(1)
        
        text = "✅ Order confirmed! Aapka order jaldi deliver hoga. Thank you! 🎉"
        conv.add_message("bot", text)
        await ws.send_json({
            "type": "message",
            "sender": "bot",
            "text": text,
            "timestamp": conv.messages[-1]["timestamp"],
        })
        
    elif action == "cancel":
        conv.outcome = "DECLINED"
        conv.stage = ConversationStage.RESOLVED
        
        text = "Order cancel kar diya hai. Koi baat nahi, phir milenge! 👋"
        conv.add_message("bot", text)
        await ws.send_json({
            "type": "message",
            "sender": "bot",
            "text": text,
            "timestamp": conv.messages[-1]["timestamp"],
        })
        
    else:
        # Anything else -> treat as hesitation -> prepay nudge
        await send_prepay_nudge(ws, conv)

async def send_prepay_nudge(ws: WebSocket, conv: Conversation):
    """Send prepay nudge when user hesitates."""
    
    conv.stage = ConversationStage.PREPAY_NUDGE
    
    await ws.send_json({"type": "typing", "duration": 2000})
    await asyncio.sleep(2)
    
    msg = generate_prepay_nudge(conv.order_state)
    conv.add_message("bot", msg["text"], msg["buttons"])
    conv.stage = ConversationStage.AWAITING_PREPAY
    
    await ws.send_json({
        "type": "message",
        "sender": "bot",
        "text": msg["text"],
        "buttons": msg["buttons"],
        "timestamp": conv.messages[-1]["timestamp"],
    })

async def handle_prepay_response(ws: WebSocket, conv: Conversation, action: str):
    """Handle user's response to prepay nudge."""
    
    if action == "prepay":
        conv.outcome = "PREPAID"
        conv.stage = ConversationStage.RESOLVED
        
        await ws.send_json({"type": "typing", "duration": 1000})
        await asyncio.sleep(1)
        
        text = "🎉 Payment received! ₹30 cashback credited. Aapka order on the way! 🚀"
        conv.add_message("bot", text)
        await ws.send_json({
            "type": "message", "sender": "bot", "text": text,
            "timestamp": conv.messages[-1]["timestamp"],
        })
        
    elif action == "cod":
        # Keeping COD = still confirmed but no prepay benefit
        conv.outcome = "CONFIRMED"
        conv.stage = ConversationStage.RESOLVED
        
        text = "👍 COD pe hi rakhte hain. Order confirmed! Delivery jaldi hogi. 🚚"
        conv.add_message("bot", text)
        await ws.send_json({
            "type": "message", "sender": "bot", "text": text,
            "timestamp": conv.messages[-1]["timestamp"],
        })
        
    elif action == "cancel":
        conv.outcome = "DECLINED"
        conv.stage = ConversationStage.RESOLVED
        
        text = "Order cancel ho gaya. Phir kabhi shopping karna! 👋"
        conv.add_message("bot", text)
        await ws.send_json({
            "type": "message", "sender": "bot", "text": text,
            "timestamp": conv.messages[-1]["timestamp"],
        })

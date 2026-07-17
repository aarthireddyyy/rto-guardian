from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import logging
import json
from app.agents.voice_agent import VoiceAgent

router = APIRouter()
logger = logging.getLogger(__name__)

# Keep track of active calls in memory
active_voice_calls = {}

# Store for order details (in production, query from database)
orders_store = {}

@router.websocket("/ws/voice/{order_id}")
async def voice_websocket(websocket: WebSocket, order_id: str):
    """
    WebSocket endpoint that connects the browser's microphone/speaker 
    to our Python VoiceAgent State Machine.
    """
    await websocket.accept()
    
    # Get order details from store (populated by /orders/process endpoint)
    order_details = orders_store.get(order_id, {
        "customer_name": "Customer",
        "amount": "500",
        "address": "Address not provided"
    })
    
    # Initialize agent with order details
    agent = VoiceAgent(
        order_id=order_id,
        customer_name=order_details.get("customer_name", "Customer"),
        amount=str(order_details.get("order_value", order_details.get("amount", "500"))),
        # pyrefly: ignore [unexpected-keyword]
        address=order_details.get("address", "Address not provided")
    )
    active_voice_calls[order_id] = agent
    
    try:
        logger.info(f"📞 Voice call connected for order: {order_id}")
        
        # Send initial state to UI
        await websocket.send_text(json.dumps({
            "type": "state",
            "state": agent.state.value,
            "message": "Call connected. Sending greeting..."
        }))
        
        # 1. Start the call: Generate and send the greeting
        greeting_audio = await agent.get_initial_greeting_audio()
        if greeting_audio:
            # Send the transcript to UI first
            last_log = agent.conversation_log[-1] if agent.conversation_log else {"text": ""}
            await websocket.send_text(json.dumps({
                "type": "bot_message",
                "text": last_log.get("text", ""),
                "state": agent.state.value
            }))
            # Then send the audio
            await websocket.send_bytes(greeting_audio)
            
        # 2. The Main Conversation Loop
        while agent.is_call_active:
            try:
                # Wait for message from browser (could be audio bytes or text for testing)
                message = await websocket.receive()
                
                if "bytes" in message:
                    # Audio from browser
                    user_audio_bytes = message["bytes"]
                    logger.info(f"Received {len(user_audio_bytes)} bytes of audio from browser.")
                    
                    # Send status update
                    await websocket.send_text(json.dumps({
                        "type": "state",
                        "state": agent.state.value,
                        "message": "Processing your speech..."
                    }))
                    
                    # Feed the raw bytes to the Brain (ASR -> Groq Logic -> TTS)
                    bot_audio_response = await agent.process_user_audio(user_audio_bytes)
                    
                    # Send user's transcribed text to UI
                    if len(agent.conversation_log) >= 2:
                        user_log = agent.conversation_log[-2]
                        if user_log.get("speaker") == "user":
                            await websocket.send_text(json.dumps({
                                "type": "user_message",
                                "text": user_log.get("text", ""),
                                "state": agent.state.value
                            }))
                    
                    # Send bot's response text to UI
                    if agent.conversation_log:
                        bot_log = agent.conversation_log[-1]
                        if bot_log.get("speaker") == "bot":
                            await websocket.send_text(json.dumps({
                                "type": "bot_message",
                                "text": bot_log.get("text", ""),
                                "state": agent.state.value
                            }))
                    
                    # Stream the newly generated Voice back to the browser speaker
                    if bot_audio_response:
                        await websocket.send_bytes(bot_audio_response)
                        
                elif "text" in message:
                    # Text message (for testing without audio)
                    data = json.loads(message["text"])
                    if data.get("type") == "text_input":
                        user_text = data.get("text", "")
                        logger.info(f"Received text input: {user_text}")
                        
                        # Process as text
                        bot_audio_response = await agent.process_user_text(user_text)
                        
                        # Send conversation updates
                        if len(agent.conversation_log) >= 2:
                            user_log = agent.conversation_log[-2]
                            await websocket.send_text(json.dumps({
                                "type": "user_message",
                                "text": user_log.get("text", ""),
                                "state": agent.state.value
                            }))
                        
                        if agent.conversation_log:
                            bot_log = agent.conversation_log[-1]
                            await websocket.send_text(json.dumps({
                                "type": "bot_message",
                                "text": bot_log.get("text", ""),
                                "state": agent.state.value
                            }))
                        
                        if bot_audio_response:
                            await websocket.send_bytes(bot_audio_response)
                    
            except Exception as e:
                logger.error(f"Error during audio processing loop: {e}", exc_info=True)
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": str(e)
                }))
                break
                
        # 3. Call has naturally finished (reached CLOSING or DECLINED state)
        logger.info(f"✅ Call finished for {order_id}. State: {agent.state.value}, Landmark: {agent.landmark}")
        
        # Send final outcome to UI
        outcome = "CONFIRMED" if agent.state.value == "closing" else "DECLINED"
        await websocket.send_text(json.dumps({
            "type": "call_ended",
            "outcome": outcome,
            "landmark": agent.landmark,
            "state": agent.state.value
        }))
        
    except WebSocketDisconnect:
        logger.info(f"❌ Browser disconnected the voice call for {order_id}")
    except Exception as e:
        logger.error(f"Unexpected error in voice websocket: {e}", exc_info=True)
    finally:
        # Cleanup when the call ends
        active_voice_calls.pop(order_id, None)

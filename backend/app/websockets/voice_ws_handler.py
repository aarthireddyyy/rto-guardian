from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import logging
from app.agents.voice_agent import VoiceAgent

router = APIRouter()
logger = logging.getLogger(__name__)

# Keep track of active calls in memory
active_voice_calls = {}

@router.websocket("/ws/voice/{order_id}")
async def voice_websocket(websocket: WebSocket, order_id: str):
    """
    WebSocket endpoint that connects the browser's microphone/speaker 
    to our Python VoiceAgent State Machine.
    """
    await websocket.accept()
    
    # In a real production app, we would query the database here using the order_id
    # to get the real customer name and amount. For the MVP, we hardcode it.
    agent = VoiceAgent(order_id=order_id, customer_name="Rahul", amount="249")
    active_voice_calls[order_id] = agent
    
    try:
        logger.info(f"📞 Voice call connected for order: {order_id}")
        
        # 1. Start the call: Generate and send the "Namaste" greeting immediately
        greeting_audio = await agent.get_initial_greeting_audio()
        if greeting_audio:
            await websocket.send_bytes(greeting_audio)
            
        # 2. The Main Conversation Loop
        while agent.is_call_active:
            try:
                # Wait in silence until the browser sends us recorded audio bytes
                user_audio_bytes = await websocket.receive_bytes()
                logger.info(f"Received {len(user_audio_bytes)} bytes of audio from browser.")
                
                # Feed the raw bytes to the Brain (ASR -> Groq Logic -> TTS)
                bot_audio_response = await agent.process_user_audio(user_audio_bytes)
                
                # Stream the newly generated Voice back to the browser speaker
                if bot_audio_response:
                    await websocket.send_bytes(bot_audio_response)
                    
            except Exception as e:
                logger.error(f"Error during audio processing loop: {e}")
                break
                
        # 3. Call has naturally finished (reached CLOSING state)
        logger.info(f"✅ Call finished for {order_id}. Extracted Landmark: {agent.landmark}")
        
        # (Optional) Here is where you would update the database with the extracted landmark
        
    except WebSocketDisconnect:
        logger.info(f"❌ Browser disconnected the voice call for {order_id}")
    finally:
        # Cleanup when the call ends
        active_voice_calls.pop(order_id, None)

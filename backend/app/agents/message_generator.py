import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Check if GROQ_API_KEY is available
groq_api_key = os.getenv("GROQ_API_KEY")
groq_client = None

if groq_api_key:
    try:
        from groq import Groq
        groq_client = Groq(api_key=groq_api_key)
    except ImportError:
        pass

def generate_confirmation_message(order_state: dict) -> dict:
    """Generate a natural WhatsApp confirmation message."""
    
    if not groq_client:
        return {
            "text": f"Namaste {order_state.get('customer_name', 'Customer')}! 👋 Meesho par aapka order ₹{order_state.get('order_value', 0)} ke liye received hua hai. Delivery address: {order_state.get('address', '')}. Payment: {order_state.get('payment_mode', 'COD')}. Sahi hai toh ✅ dabao!",
            "buttons": [
                {"id": "confirm", "label": "✅ Confirm Order"},
                {"id": "cancel", "label": "❌ Cancel Order"},
            ]
        }
        
    prompt = f"""You are Meesho's friendly order confirmation bot on WhatsApp.
    
Generate a SHORT confirmation message (max 3 lines) for this order:
- Customer: {order_state.get('customer_name')}
- Item value: ₹{order_state.get('order_value')}
- Payment: {order_state.get('payment_mode')}  
- Delivery to: {order_state.get('address')}

Rules:
- Use Hinglish (mix of Hindi and English) — this is how Meesho talks
- Be warm and friendly, use emojis
- End with asking them to confirm or cancel
- Keep it casual, not corporate

Example tone: "Hey Priya! 🛍️ Aapka order confirm kar dein? ₹349 ka kurta, COD pe aa raha hai Lucknow. Sahi hai toh ✅ dabao!"

Generate ONLY the message text, nothing else."""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.8,
        )
        message_text = response.choices[0].message.content.strip()
    except Exception as e:
        message_text = f"Simulated: (Groq Error: {str(e)})"

    return {
        "text": message_text,
        "buttons": [
            {"id": "confirm", "label": "✅ Confirm Order"},
            {"id": "cancel", "label": "❌ Cancel Order"},
        ]
    }

def generate_prepay_nudge(order_state: dict) -> dict:
    """Generate a prepay nudge message when user hesitates."""
    
    if not groq_client:
        return {
            "text": "Arre wait! 💰 Abhi UPI se pay karo toh ₹30 cashback seedha mil jayega! Offer limited hai 🔥",
            "buttons": [
                {"id": "prepay", "label": "💰 Pay Now (₹30 off!)"},
                {"id": "cod", "label": "🚚 Keep COD"},
                {"id": "cancel", "label": "❌ Cancel Order"},
            ]
        }
        
    prompt = f"""You are Meesho's WhatsApp bot. The customer hasn't confirmed their ₹{order_state.get('order_value')} COD order yet.

Generate a SHORT prepay nudge (2 lines max):
- Offer ₹30 cashback if they pay online now
- Make it feel like a special deal, not pushy
- Use Hinglish and emojis
- Mention UPI payment

Example tone: "Arre wait! 💰 Abhi UPI se pay karo toh ₹30 cashback seedha mil jayega! Offer limited hai 🔥"

Generate ONLY the message text."""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.8,
        )
        text = response.choices[0].message.content.strip()
    except Exception as e:
        text = f"Simulated: (Groq Error: {str(e)})"

    return {
        "text": text,
        "buttons": [
            {"id": "prepay", "label": "💰 Pay Now (₹30 off!)"},
            {"id": "cod", "label": "🚚 Keep COD"},
            {"id": "cancel", "label": "❌ Cancel Order"},
        ]
    }

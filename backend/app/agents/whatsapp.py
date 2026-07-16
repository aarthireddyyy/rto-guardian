import os
from dotenv import load_dotenv
from app.models.schemas import OrderState

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

async def whatsapp_agent(state: OrderState) -> dict:
    """Medium risk — send WhatsApp-style confirmation, process response."""
    
    bot_message = None
    if groq_client:
        try:
            prompt = f"""You are a Meesho order confirmation bot. Generate a brief, friendly WhatsApp 
            message to confirm this order:
            - Customer: {state['customer_name']}
            - Item value: ₹{state['order_value']}
            - Address: {state['address']}
            - Payment: {state['payment_mode']}
            
            Keep it under 3 lines. Include ✅ Confirm and ❌ Cancel options.
            Write in a mix of English and Hindi (Hinglish) like Meesho's actual messages."""
            
            response = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150
            )
            bot_message = response.choices[0].message.content
        except Exception as e:
            # Fallback on API error
            bot_message = f"Simulated: (Groq Error: {str(e)})"
            
    if not bot_message:
        # Fallback to simulated message
        bot_message = (
            f"Namaste {state['customer_name']}! 👋 Meesho par aapka order ₹{state['order_value']} "
            f"ke liye received hua hai. Delivery address: {state['address']}. "
            f"Payment: {state['payment_mode']}. Kya aap is order ko confirm karna chahte hain?\n"
            f"👉 Reply 'Confirm' ya 'Cancel'."
        )
    
    return {
        "agent_type": "whatsapp",
        "agent_outcome": "PENDING",
        "agent_message": bot_message,
    }

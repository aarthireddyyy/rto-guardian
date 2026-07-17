import os
import logging
# pyrefly: ignore [missing-import]
from groq import AsyncGroq
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# Initialize the async Groq client
client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

async def classify_intent(text: str, options: list[str]) -> str:
    """
    Given a user's transcribed text (Hinglish/Hindi/English) and a list of valid options
    (e.g., ["YES", "NO"] or ["HINDI", "ENGLISH"]), returns the single best matching option.
    """
    if not client:
        logger.error("GROQ_API_KEY is missing from .env")
        return options[0]

    prompt = f"""
You are an intent classifier for a voice bot in India. 
The user said: "{text}"

Your job is to classify their intent into EXACTLY one of the following options: {options}
If they are agreeing or saying yes in Hindi/Hinglish (like "haan", "theek hai", "kardo"), output YES.
If they are disagreeing (like "nahi", "cancel"), output NO.

Respond with ONLY the exact option string from the list above. No other words, no punctuation.
"""
    try:
        completion = await client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",  # Llama-3.1-8B is lightning fast for this
            temperature=0.0,
            max_tokens=10
        )
        result = completion.choices[0].message.content.strip().upper()
        
        # Ensure the LLM didn't hallucinate an option outside our allowed list
        for opt in options:
            if opt.upper() in result:
                return opt.upper()
                
        return options[0] # Fallback if confused
    except Exception as e:
        logger.error(f"Groq classification error: {e}")
        return options[0]

async def extract_landmark(text: str) -> str:
    """
    Given a Hinglish sentence, extracts the core landmark mentioned by the user.
    """
    if not client:
        return text

    prompt = f"""
The user was asked for a landmark for delivery.
They said: "{text}"

Extract JUST the landmark. Remove conversational filler words like "ke paas", "ke peeche", "hai", "mera ghar".
For example:
- "Petrol pump ke peeche hai" -> "Petrol pump"
- "Ek bada mandir hai udhar aaja" -> "Bada mandir"
- "School ke paas" -> "School"

Respond with ONLY the extracted landmark string. Nothing else.
"""
    try:
        completion = await client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.0,
            max_tokens=20
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Groq extraction error: {e}")
        return text

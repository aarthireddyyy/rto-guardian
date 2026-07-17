import os
import httpx
import base64
import logging
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
SARVAM_BASE_URL = "https://api.sarvam.ai"

async def speech_to_text(audio_bytes: bytes) -> str:
    """
    Takes raw audio bytes, sends to Sarvam ASR, and returns the transcribed Hinglish text.
    """
    if not SARVAM_API_KEY:
        logger.error("SARVAM_API_KEY is missing from .env file")
        return ""

    headers = {
        "API-Subscription-Key": SARVAM_API_KEY
        # Content type is usually multipart/form-data for audio uploads,
        # httpx handles this automatically when using the 'files' parameter.
    }
    
    # We create a temporary async client for the request
    async with httpx.AsyncClient() as client:
        try:
            logger.info("Sending audio to Sarvam ASR...")
            # Note: Sarvam's exact API expects a file payload. 
            # We simulate saving it as a wav file in memory to send it.
            files = {'file': ('audio.wav', audio_bytes, 'audio/wav')}
            
            # The endpoint for speech to text
            response = await client.post(
                f"{SARVAM_BASE_URL}/speech-to-text-translate",
                headers=headers,
                files=files,
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            
            # Usually the transcription is under a 'transcript' or 'text' key in their JSON
            transcript = data.get("transcript", "")
            logger.info(f"Sarvam ASR Transcription: {transcript}")
            return transcript
            
        except Exception as e:
            logger.error(f"Error calling Sarvam ASR: {str(e)}")
            return ""

async def text_to_speech(text: str, language_code: str = "hi-IN", speaker: str = "rahul") -> bytes:
    """
    Takes a string of text, sends to Sarvam TTS, and returns audio bytes.
    """
    if not SARVAM_API_KEY:
        logger.error("SARVAM_API_KEY is missing from .env file")
        return b""

    headers = {
        "API-Subscription-Key": SARVAM_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "inputs": [text],
        "target_language_code": language_code,
        "speaker": speaker,
        "pace": 1.0,
        "speech_sample_rate": 8000,
        "enable_preprocessing": True,
        "model": "bulbul:v3"
    }

    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Sending text to Sarvam TTS: '{text}'")
            response = await client.post(
                f"{SARVAM_BASE_URL}/text-to-speech",
                headers=headers,
                json=payload,
                timeout=10.0
            )
            if response.status_code != 200:
                logger.error(f"Sarvam API Error Body: {response.text}")
            response.raise_for_status()
            data = response.json()
            
            # Sarvam returns the audio as a base64 encoded string in their JSON response
            base64_audio = data["audios"][0]
            audio_bytes = base64.b64decode(base64_audio)
            
            logger.info("Successfully generated audio from Sarvam TTS.")
            return audio_bytes
            
        except Exception as e:
            logger.error(f"Error calling Sarvam TTS: {str(e)}")
            return b""

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

# Language code mapping for Sarvam API
LANGUAGE_MAPPING = {
    "hi-IN": "hi-IN",  # Hindi
    "en-IN": "en-IN",  # English (India)
    "te-IN": "te-IN",  # Telugu
    "ta-IN": "ta-IN",  # Tamil
    "ml-IN": "ml-IN",  # Malayalam
    "kn-IN": "kn-IN",  # Kannada
    "gu-IN": "gu-IN",  # Gujarati
    "mr-IN": "mr-IN",  # Marathi
    "bn-IN": "bn-IN",  # Bengali
    "pa-IN": "pa-IN",  # Punjabi
}

async def speech_to_text(audio_bytes: bytes, language_code: str = "hi-IN") -> str:
    """
    Takes raw audio bytes, sends to Sarvam ASR, and returns the transcribed text.
    Supports multiple Indian languages.
    """
    if not SARVAM_API_KEY:
        logger.error("SARVAM_API_KEY is missing from .env file")
        return ""

    if not audio_bytes or len(audio_bytes) == 0:
        logger.error("Empty audio bytes received")
        return ""

    headers = {
        "API-Subscription-Key": SARVAM_API_KEY
    }
    
    # Map language code
    target_language = LANGUAGE_MAPPING.get(language_code, "hi-IN")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            logger.info(f"Sending {len(audio_bytes)} bytes to Sarvam ASR (language: {target_language})...")
            
            # Prepare file for upload
            files = {'file': ('audio.wav', audio_bytes, 'audio/wav')}
            data = {'language_code': target_language}
            
            # The endpoint for speech to text
            response = await client.post(
                f"{SARVAM_BASE_URL}/speech-to-text-translate",
                headers=headers,
                files=files,
                data=data
            )
            
            if response.status_code != 200:
                logger.error(f"Sarvam ASR Error ({response.status_code}): {response.text}")
                return ""
                
            data = response.json()
            
            # Usually the transcription is under a 'transcript' or 'text' key in their JSON
            transcript = data.get("transcript", data.get("text", ""))
            logger.info(f"✅ Sarvam ASR Transcription: '{transcript}'")
            return transcript
            
        except httpx.TimeoutException:
            logger.error("Sarvam ASR request timed out")
            return ""
        except httpx.HTTPStatusError as e:
            logger.error(f"Sarvam ASR HTTP error: {e.response.status_code} - {e.response.text}")
            return ""
        except Exception as e:
            logger.error(f"Error calling Sarvam ASR: {str(e)}", exc_info=True)
            return ""

async def text_to_speech(text: str, language_code: str = "hi-IN", speaker: str = "manisha") -> bytes:
    """
    Takes a string of text, sends to Sarvam TTS, and returns audio bytes.
    Supports multiple Indian languages including Telugu.
    
    Available speakers (Sarvam API): 
    anushka, abhilash, manisha, vidya, arya, karun, hitesh, aditya, 
    ritu, priya, neha, rahul, pooja, rohan, simran, kavya, amit, dev, 
    ishita, shreya, ratan, varun, manan, sumit, roopa, kabir, aayan, 
    shubh, ashutosh, advait, anand, tanya, tarun, sunny, mani, gokul, 
    vijay, shruti, suhani, mohit, kavitha, rehan, soham, rupali
    """
    if not SARVAM_API_KEY:
        logger.error("SARVAM_API_KEY is missing from .env file")
        return b""

    if not text or len(text.strip()) == 0:
        logger.error("Empty text provided for TTS")
        return b""

    headers = {
        "API-Subscription-Key": SARVAM_API_KEY,
        "Content-Type": "application/json"
    }
    
    # Map language code
    target_language = LANGUAGE_MAPPING.get(language_code, "hi-IN")
    
    # Choose appropriate speaker based on language
    # Use female voices for better clarity
    # Available speakers for bulbul:v3: aditya, ritu, ashutosh, priya, neha, 
    # rahul, pooja, rohan, simran, kavya, amit, dev, ishita, shreya, ratan, 
    # varun, manan, sumit, roopa, kabir, aayan, shubh, advait, anand, tanya, 
    # tarun, sunny, mani, gokul, vijay, shruti, suhani, mohit, kavitha, rehan, 
    # soham, rupali, niharika
    if language_code == "te-IN":
        speaker = "kavitha"  # Female Telugu voice
    elif language_code == "en-IN":
        speaker = "priya"    # Female English voice
    elif language_code == "hi-IN":
        speaker = "ritu"     # Female Hindi voice (changed from manisha to ritu)
    else:
        speaker = "priya"    # Default to priya
    
    payload = {
        "inputs": [text],
        "target_language_code": target_language,
        "speaker": speaker,
        "pace": 1.0,
        "speech_sample_rate": 8000,
        "enable_preprocessing": True,
        "model": "bulbul:v3"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            logger.info(f"Sending text to Sarvam TTS (language: {target_language}, speaker: {speaker}): '{text[:50]}...'")
            
            response = await client.post(
                f"{SARVAM_BASE_URL}/text-to-speech",
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                logger.error(f"Sarvam TTS Error ({response.status_code}): {response.text}")
                return b""
                
            data = response.json()
            
            # Sarvam returns the audio as a base64 encoded string in their JSON response
            if "audios" not in data or len(data["audios"]) == 0:
                logger.error(f"No audio in Sarvam TTS response: {data}")
                return b""
                
            base64_audio = data["audios"][0]
            audio_bytes = base64.b64decode(base64_audio)
            
            logger.info(f"✅ Successfully generated {len(audio_bytes)} bytes of audio from Sarvam TTS")
            return audio_bytes
            
        except httpx.TimeoutException:
            logger.error("Sarvam TTS request timed out")
            return b""
        except httpx.HTTPStatusError as e:
            logger.error(f"Sarvam TTS HTTP error: {e.response.status_code} - {e.response.text}")
            return b""
        except Exception as e:
            logger.error(f"Error calling Sarvam TTS: {str(e)}", exc_info=True)
            return b""

import logging
from enum import Enum
from app.services import sarvam_service
from app.agents import groq_parser

logger = logging.getLogger(__name__)

class VoiceState(Enum):
    LANGUAGE_SELECT = "language_select"
    GREET_HINDI = "greet_hindi"
    GREET_ENGLISH = "greet_english"
    WAIT_CONFIRM = "wait_confirm"
    LANDMARK_ASK = "landmark_ask"
    FOLLOWUP_LANDMARK = "followup_landmark"
    CLOSING = "closing"
    DECLINED = "declined"

class VoiceAgent:
    def __init__(self, order_id: str, customer_name: str, amount: str):
        self.state = VoiceState.LANGUAGE_SELECT
        self.order_id = order_id
        self.customer_name = customer_name
        self.amount = amount
        self.language = "hi-IN" # Default to Hindi
        self.landmark = None
        self.is_call_active = True

    async def get_initial_greeting_audio(self) -> bytes:
        """Called when the call first connects. Generates the first audio byte stream."""
        text = "Namaste! Hindi mein baat karne ke liye Hindi bolen, or say English for English."
        logger.info(f"[State: {self.state.name}] Bot says: {text}")
        return await sarvam_service.text_to_speech(text, language_code="hi-IN")

    async def process_user_audio(self, audio_bytes: bytes) -> bytes:
        """
        The main loop for actual websockets.
        1. Listen (ASR)
        2. Think & Transition (process text)
        3. Speak (TTS)
        """
        # 1. Listen (Convert user's audio bytes to text)
        user_text = await sarvam_service.speech_to_text(audio_bytes)
        if not user_text:
            return await self._speak("Maaf kijiye, mujhe theek se sunai nahi diya. Kripya wapas bolein.")
        
        logger.info(f"[User Audio Transcribed]: {user_text}")
        
        # 2 & 3. Think, Transition, and Speak
        return await self.process_user_text(user_text)

    async def process_user_text(self, user_text: str) -> bytes:
        """
        Separated text logic for easy testing (bypasses the ASR step).
        """
        logger.info(f"Evaluating intent in state: {self.state.name}...")
        
        if self.state == VoiceState.LANGUAGE_SELECT:
            intent = await groq_parser.classify_intent(user_text, ["HINDI", "ENGLISH"])
            if intent == "ENGLISH":
                self.language = "en-IN"
                self.state = VoiceState.GREET_ENGLISH
                return await self._speak(f"Hello {self.customer_name}. Please confirm your order of {self.amount} rupees. Say yes to confirm.")
            else:
                self.language = "hi-IN"
                self.state = VoiceState.GREET_HINDI
                return await self._speak(f"Namaste {self.customer_name}. Aapka {self.amount} rupaiye ka order confirm karein? Haan ya naa bole.")

        elif self.state in [VoiceState.GREET_HINDI, VoiceState.GREET_ENGLISH]:
            intent = await groq_parser.classify_intent(user_text, ["YES", "NO"])
            if intent == "YES":
                self.state = VoiceState.LANDMARK_ASK
                if self.language == "hi-IN":
                    return await self._speak("Dhanyawad! Delivery ke liye koi nazdeeki landmark bata dijiye, jaise koi school ya mandir?")
                else:
                    return await self._speak("Thank you! Please provide a nearby landmark for delivery.")
            else:
                self.state = VoiceState.DECLINED
                self.is_call_active = False
                if self.language == "hi-IN":
                    return await self._speak("Theek hai, hum ye order cancel kar rahe hain. Dhanyawad.")
                else:
                    return await self._speak("Okay, we will cancel this order. Thank you.")

        elif self.state == VoiceState.LANDMARK_ASK:
            landmark = await groq_parser.extract_landmark(user_text)
            self.landmark = landmark
            # Count words to see if it's too vague (e.g. they just said "school")
            if len(landmark.split()) < 2:
                self.state = VoiceState.FOLLOWUP_LANDMARK
                if self.language == "hi-IN":
                    return await self._speak(f"{landmark} ke paas kahan par exactly? Thoda aur detail de dijiye.")
                else:
                    return await self._speak(f"Where exactly near {landmark}? Please provide more detail.")
            else:
                self.state = VoiceState.CLOSING
                self.is_call_active = False
                if self.language == "hi-IN":
                    return await self._speak(f"Theek hai, {landmark} par delivery ho jayegi. Dhanyawad!")
                else:
                    return await self._speak(f"Okay, delivery will be done at {landmark}. Thank you!")
                    
        elif self.state == VoiceState.FOLLOWUP_LANDMARK:
            landmark = await groq_parser.extract_landmark(user_text)
            self.landmark = landmark
            self.state = VoiceState.CLOSING
            self.is_call_active = False
            if self.language == "hi-IN":
                return await self._speak(f"Shukriya, {landmark} par order aa jayega.")
            else:
                return await self._speak(f"Thank you, order will arrive at {landmark}.")
                
        # Default fallback if the state machine gets confused
        return await self._speak("Dhanyawad.")

    async def _speak(self, text: str) -> bytes:
        """Helper to generate speech using Sarvam TTS in the correct language."""
        logger.info(f"[State: {self.state.name}] Bot says: {text}")
        return await sarvam_service.text_to_speech(text, language_code=self.language)

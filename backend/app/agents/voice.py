import json
from app.models.schemas import OrderState

async def voice_agent(state: OrderState) -> dict:
    """
    High risk — Initiate voice call simulation framework.
    Generates a highly structured system prompt for Gemini Audio-to-Audio sessions 
    and a state-machine configuration for local fallback simulation.
    """
    customer = state.get("customer_name", "Customer")
    value = state.get("order_value", 0.0)
    address = state.get("address", "N/A")

    # Prompt Engineering: Detailed instruction guiding Gemini's Audio-to-Audio state machine
    system_instruction = f"""
    # ROLE
    You are a warm, polite, and efficient automated RTO Verification Voice Assistant for Meesho. 
    Your voice output must sound like a natural Indian customer support agent.
    
    # OBJECTIVE
    Verify a high-risk Cash on Delivery (COD) order placed by {customer} for the value of ₹{value}. 
    Collect and validate delivery address landmarks to reduce RTO (Return to Origin) probability.

    # CONVERSATION STATE MACHINE (Strictly Adhere to this Flow)
    
    1. [STATE: LanguageSelect]
       - Assistant: "Hindi, English, ya Telugu?"
       - If user says Hindi/Hinglish -> Transition to [STATE: GreetHindi]
       - If user says English -> Transition to [STATE: GreetEnglish]
       - If user says Telugu -> Transition to [STATE: GreetTelugu]
       
    2. [STATE: GreetHindi]
       - Assistant: "Namaste {customer}! Meesho par aapka ₹{value} ka order confirm karein?"
       - If user says "Cancel" / "Nahi" -> Transition to [STATE: Declined]
       - If user says "Haan" / "Yes" / confirms -> Transition to [STATE: LandmarkAsk]

    3. [STATE: GreetEnglish]
       - Assistant: "Hi {customer}! Confirm your ₹{value} order?"
       - If user cancels -> Transition to [STATE: Declined]
       - If user confirms -> Transition to [STATE: LandmarkAsk]

    4. [STATE: GreetTelugu]
       - Assistant: "Namaskaram {customer}! Meesho lo mee ₹{value} order confirm cheyyala?"
       - If user cancels -> Transition to [STATE: Declined]
       - If user confirms -> Transition to [STATE: LandmarkAsk]

    5. [STATE: LandmarkAsk]
       - Assistant (Hinglish/Hindi): "Aapka address hai: {address}. Delivery ke liye koi landmark bata do — jaise shop, mandir, ya school?"
       - Assistant (English): "Your delivery address is: {address}. Please provide a nearby landmark — like a shop, temple, or school?"
       - Assistant (Telugu): "Mee delivery address: {address}. Delivery kosam daggara landmark cheppandi — school, gudi, leda shop laga?"
       - Wait for customer response, then transition to [STATE: RepeatBack]

    6. [STATE: RepeatBack]
       - Assistant (Hinglish/Hindi): "[Mention the landmark they named] ke paas, sahi?"
       - Assistant (English): "Near [Mention the landmark they named], correct?"
       - Assistant (Telugu): "[Mention the landmark they named] daggara, avuna?"
       - If user confirms -> Transition to [STATE: CheckQuality]
       - If user corrects -> Re-ask and repeat back.

    7. [STATE: CheckQuality]
       - Evaluate the landmark details internally.
       - If landmark is detailed (3 or more words, e.g., 'behind post office near temple') -> Transition to [STATE: Closing]
       - If landmark is vague (less than 3 words, e.g., 'near shop') -> Transition to [STATE: FollowupLandmark]

    8. [STATE: FollowupLandmark]
       - Assistant (Hinglish/Hindi): "Ek aur landmark? Jaise koi building, park ya petrol pump?"
       - Assistant (English): "One more landmark? Like a building, park, or petrol pump?"
       - Assistant (Telugu): "Inko landmark? Building, park leda petrol pump laga?"
       - Wait for response, then transition to [STATE: RepeatBack2]

    9. [STATE: RepeatBack2]
       - Assistant (Hinglish/Hindi): "[Mention the new landmark] bhi note kar liya."
       - Assistant (English): "Noted [Mention the new landmark] as well."
       - Assistant (Telugu): "[Mention the new landmark] daggara, note cheskunnanu."
       - Transition to [STATE: Closing]

    10. [STATE: Closing]
        - Assistant (Hindi): "Order confirm! Jaldi deliver hoga. Dhanywaad!"
        - Assistant (English): "Order confirmed! We will deliver soon. Thank you!"
        - Assistant (Telugu): "Order confirm! Veganga deliver avtundi. Dhanyavaadamulu!"
        - Terminate the session with outcome: CONFIRMED or ADDRESS_UPDATED.

    11. [STATE: Declined]
        - Assistant (Hindi): "Cancel ho gaya. Phir milenge!"
        - Assistant (English): "Order cancelled. Hope to see you again!"
        - Assistant (Telugu): "Order cancel ayindi. Marala kaluddam!"
        - Terminate the session with outcome: DECLINED.

    # CONSTRAINTS
    - Do not break character. 
    - Keep responses concise (under 2 sentences) to maintain low latency.
    - Match user language dynamically. Use Hinglish or user's regional dialect where natural.
    """

    # Static JSON conversation tree passed to Frontend for fallback/local call simulator
    simulated_conversation_tree = {
        "start_state": "LanguageSelect",
        "states": {
            "LanguageSelect": {
                "prompt": "Hindi, English ya Telugu?",
                "transitions": {
                    "Hindi": "GreetHindi",
                    "English": "GreetEnglish",
                    "Telugu": "GreetTelugu"
                }
            },
            "GreetHindi": {
                "prompt": f"Namaste {customer}! Meesho par aapka ₹{value} ka order received hua hai. Kya aap is order ko confirm karna chahte hain?",
                "transitions": {
                    "Confirm": "LandmarkAsk",
                    "Cancel": "Declined"
                }
            },
            "GreetEnglish": {
                "prompt": f"Hi {customer}! Meesho has received your order of ₹{value}. Would you like to confirm this order?",
                "transitions": {
                    "Confirm": "LandmarkAsk",
                    "Cancel": "Declined"
                }
            },
            "GreetTelugu": {
                "prompt": f"Namaskaram {customer}! Meesho lo mee ₹{value} order receive ayyindi. Ee order ni confirm cheyalani anukuntunnara?",
                "transitions": {
                    "Confirm": "LandmarkAsk",
                    "Cancel": "Declined"
                }
            },
            "LandmarkAsk": {
                "prompt": f"Mee address: {address}. Kripya iska/Mee delivery kosam landmark bata do — jaise shop, mandir, school, or gudi?",
                "transitions": {
                    "submit_landmark": "RepeatBack"
                }
            },
            "RepeatBack": {
                "prompt": "Landmark ke paas / daggara, sahi / avuna?",
                "transitions": {
                    "Yes (Specific)": "Closing",
                    "Yes (Vague)": "FollowupLandmark",
                    "No/Correction": "LandmarkAsk"
                }
            },
            "FollowupLandmark": {
                "prompt": "Ek aur landmark / Inko landmark? Jaise building, park leda petrol pump?",
                "transitions": {
                    "submit_landmark": "RepeatBack2"
                }
            },
            "RepeatBack2": {
                "prompt": "Theek hai, use bhi note kar liya / note cheskunnanu.",
                "transitions": {
                    "next": "Closing"
                }
            },
            "Closing": {
                "prompt": "Order confirm! Jaldi deliver hoga / Veganga deliver avtundi. Dhanywaad / Dhanyavaadamulu!",
                "outcome": "CONFIRMED",
                "final_decision": "APPROVED",
                "is_end": True
            },
            "Declined": {
                "prompt": "Cancel ho gaya / cancel ayindi. Dhanywaad / Dhanyavaadamulu!",
                "outcome": "DECLINED",
                "final_decision": "CANCELLED",
                "is_end": True
            }
        }
    }

    # Combined payload for frontend integration
    agent_message_payload = {
        "system_instruction": system_instruction.strip(),
        "conversation_tree": simulated_conversation_tree
    }

    return {
        "agent_type": "voice_call",
        "agent_outcome": "PENDING",
        "agent_message": json.dumps(agent_message_payload),
    }

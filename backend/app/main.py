import os
# pyrefly: ignore [missing-import]
import joblib
import numpy as np
from fastapi import FastAPI, HTTPException
from app.models.schemas import (
    OrderInput, 
    RiskOutput, 
    OrderState, 
    ProcessOrderRequest, 
    ProcessOrderResponse
)
from app.agents.orchestrator import orchestrator
from app.agents.rescore import rescore
from app.websockets.chat_handler import router as chat_router
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="RTO Risk Scoring & Agent Orchestrator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)

# Global variable to hold the loaded ML artifacts
artifact = None

# In-memory storage repository abstraction
orders_db: dict[str, OrderState] = {}

def get_order_state(order_id: str) -> OrderState:
    """Retrieve the current state of an order from storage."""
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")
    return orders_db[order_id]

def save_order_state(order_id: str, state: OrderState):
    """Save the updated state of an order to storage."""
    orders_db[order_id] = state

@app.on_event("startup")
def load_model():
    global artifact
    # Path relative to this main.py file
    model_path = os.path.join(os.path.dirname(__file__), "..", "ml", "models", "rto_risk_model.pkl")
    if not os.path.exists(model_path):
        print(f"Warning: Model not found at {model_path}. Please run train.py first.")
        return
    artifact = joblib.load(model_path)
    print("Model loaded successfully.")

@app.post("/predict", response_model=RiskOutput)
def predict_risk(order: OrderInput):
    if artifact is None:
        raise HTTPException(status_code=500, detail="Model is not loaded.")

    model = artifact['model']
    scaler = artifact['scaler']
    le = artifact['label_encoder']

    # 1. Encode payment mode
    try:
        payment_encoded = le.transform([order.payment_mode])[0]
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid payment_mode. Must be one of {le.classes_}")

    # 2. Build feature array exactly matching the training order
    features = np.array([[
        order.user_history_rto_rate,
        order.user_total_orders,
        order.orders_in_last_7days,
        payment_encoded,
        order.order_value,
        order.address_length,
        order.pincode_rto_rate
    ]])

    # 3. Scale features using the fitted scaler
    features_scaled = scaler.transform(features)

    # 4. Predict risk (probability of class 1 / RTO)
    risk_score = float(model.predict_proba(features_scaled)[0][1])

    # 5. Apply Business Logic Thresholds
    if risk_score < 0.3:
        tier, intervention = "LOW", "auto_approve"
        should_approve = True
    elif risk_score < 0.7:
        tier, intervention = "MEDIUM", "whatsapp_verification"
        should_approve = False
    else:
        tier, intervention = "HIGH", "voice_call"
        should_approve = False

    return RiskOutput(
        risk_score=round(risk_score, 4),
        risk_tier=tier,
        should_approve=should_approve,
        intervention=intervention
    )

@app.post("/orders/process", response_model=ProcessOrderResponse)
async def process_order(req: ProcessOrderRequest):
    """Phase 1: Scores order, triggers LangGraph, routes to appropriate agent node."""
    initial_state: OrderState = {
        "order_id": req.order_id,
        "customer_name": req.customer_name,
        "phone": req.phone,
        "address": req.address,
        "pincode": req.pincode,
        "order_value": req.order_value,
        "payment_mode": req.payment_mode,
        "user_history_rto_rate": req.user_history_rto_rate,
        "user_total_orders": req.user_total_orders,
        "orders_in_last_7days": req.orders_in_last_7days,
        "address_length": len(req.address),
        "pincode_rto_rate": req.pincode_rto_rate,
        
        # Initializing state fields for graph output
        "risk_score": 0.0,
        "risk_tier": "",
        "agent_type": "",
        "agent_outcome": "PENDING",
        "agent_message": "",
        "rescored": False,
        "new_risk_score": None,
        "final_decision": "",
    }
    
    # Run the compiled LangGraph pipeline
    final_state = await orchestrator.ainvoke(initial_state)
    
    # Store state to memory DB
    save_order_state(req.order_id, final_state)
    
    return ProcessOrderResponse(
        order_id=final_state["order_id"],
        risk_score=final_state["risk_score"],
        risk_tier=final_state["risk_tier"],
        agent_type=final_state["agent_type"],
        agent_message=final_state["agent_message"],
        final_decision=final_state["final_decision"],
        rescored=final_state["rescored"],
        new_risk_score=final_state.get("new_risk_score"),
    )

@app.post("/orders/{order_id}/respond")
async def handle_agent_response(order_id: str, outcome: str):
    """Phase 2: Customer responded to agent. Updates state, triggers rescoring node."""
    # Retrieve current state
    state = get_order_state(order_id)
    
    # Update state with outcome (CONFIRMED / DECLINED / PREPAID / ADDRESS_UPDATED)
    state["agent_outcome"] = outcome
    
    # Execute the rescoring node manually
    rescore_result = rescore(state)
    
    # Update and save state
    state.update(rescore_result)
    save_order_state(order_id, state)
    
    return {
        "order_id": order_id,
        "agent_outcome": outcome,
        "new_risk_score": state.get("new_risk_score"),
        "final_decision": state.get("final_decision"),
    }

@app.get("/orders/{order_id}")
def get_order(order_id: str):
    """Debug/Inspect endpoint to retrieve active order state."""
    return get_order_state(order_id)

@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": artifact is not None}

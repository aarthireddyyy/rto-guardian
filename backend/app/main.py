import os
# pyrefly: ignore [missing-import]
import joblib
import numpy as np
from fastapi import FastAPI, HTTPException
from app.models.schemas import OrderInput, RiskOutput
import uvicorn

app = FastAPI(title="RTO Risk Scoring API")

# Global variable to hold the loaded artifacts
artifact = None

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

@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": artifact is not None}

from pydantic import BaseModel
from typing import TypedDict, Optional

class OrderInput(BaseModel):
    user_history_rto_rate: float
    user_total_orders: int
    orders_in_last_7days: int
    payment_mode: str
    order_value: float
    address_length: int
    pincode_rto_rate: float

class RiskOutput(BaseModel):
    risk_score: float
    risk_tier: str
    should_approve: bool
    intervention: str

class OrderState(TypedDict):
    # --- Input (set once at the start) ---
    order_id: str
    customer_name: str
    phone: str
    address: str
    pincode: str
    order_value: float
    payment_mode: str
    
    # --- ML features (set by scorer) ---
    user_history_rto_rate: float
    user_total_orders: int
    orders_in_last_7days: int
    address_length: int
    pincode_rto_rate: float
    
    # --- Risk scoring (set by score_order node) ---
    risk_score: float
    risk_tier: str                    # LOW / MEDIUM / HIGH
    
    # --- Agent results (set by agent nodes) ---
    agent_type: str                   # auto_approve / whatsapp / voice_call
    agent_outcome: str                # APPROVED / DECLINED / CONFIRMED / TIMEOUT / ESCALATED / PENDING
    agent_message: str                # what the agent said/did
    
    # --- Re-scoring (set by rescore node) ---
    rescored: bool
    new_risk_score: Optional[float]
    
    # --- Final decision ---
    final_decision: str               # APPROVED / CANCELLED / ESCALATED

class ProcessOrderRequest(BaseModel):
    order_id: str
    customer_name: str
    phone: str
    address: str
    pincode: str
    order_value: float
    payment_mode: str
    # Pre-computed features
    user_history_rto_rate: float
    user_total_orders: int
    orders_in_last_7days: int
    pincode_rto_rate: float

class ProcessOrderResponse(BaseModel):
    order_id: str
    risk_score: float
    risk_tier: str
    agent_type: str
    agent_message: str
    final_decision: str
    rescored: bool
    new_risk_score: Optional[float]

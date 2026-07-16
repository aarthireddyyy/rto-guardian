from pydantic import BaseModel

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

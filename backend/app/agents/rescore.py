from app.models.schemas import OrderState

def rescore(state: OrderState) -> dict:
    """Re-calculate risk based on agent outcome."""
    outcome = state.get("agent_outcome", "PENDING")
    original_score = state.get("risk_score", 0.0)
    
    # Multiplier-based re-scoring reflecting live user action
    multipliers = {
        "CONFIRMED": 0.3,        # Confirmed -> 70% reduction in risk
        "PREPAID": 0.1,          # Switched to prepaid -> 90% reduction
        "ADDRESS_UPDATED": 0.4,  # Fixed address/landmark -> 60% reduction
        "DECLINED": 1.5,         # User cancelled -> risk increases
        "TIMEOUT": 1.2,          # User did not respond -> risk increases
    }
    
    multiplier = multipliers.get(outcome, 1.0)
    new_score = min(original_score * multiplier, 1.0)
    
    # Final decision mapping based on updated risk tier
    if new_score < 0.3:
        decision = "APPROVED"
    elif outcome == "DECLINED":
        decision = "CANCELLED"
    else:
        decision = "ESCALATED"  # Send to manual review queue
        
    return {
        "rescored": True,
        "new_risk_score": round(new_score, 4),
        "final_decision": decision,
    }

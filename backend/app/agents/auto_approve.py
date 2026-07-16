from app.models.schemas import OrderState

def auto_approve(state: OrderState) -> dict:
    """Low risk order — approve immediately, no intervention needed."""
    return {
        "agent_type": "auto_approve",
        "agent_outcome": "APPROVED",
        "agent_message": f"Order auto-approved. Risk score {state['risk_score']:.2f} is below threshold.",
        "final_decision": "APPROVED",
        "rescored": False,
    }

import httpx
import logging
# pyrefly: ignore [missing-import]
from langgraph.graph import StateGraph, END
from app.models.schemas import OrderState
from app.agents.auto_approve import auto_approve
from app.agents.whatsapp import whatsapp_agent
from app.agents.voice import voice_agent
from app.agents.rescore import rescore

logger = logging.getLogger(__name__)

# Define the score_order node
async def score_order(state: OrderState) -> dict:
    """Call the ML Risk Scorer API (Component 1) to retrieve the initial score and tier."""
    
    payload = {
        "user_history_rto_rate": state.get("user_history_rto_rate", 0.0),
        "user_total_orders": state.get("user_total_orders", 0),
        "orders_in_last_7days": state.get("orders_in_last_7days", 0),
        "payment_mode": state.get("payment_mode", "COD"),
        "order_value": state.get("order_value", 0.0),
        "address_length": len(state.get("address", "")),
        "pincode_rto_rate": state.get("pincode_rto_rate", 0.0),
    }

    try:
        # Call the FastAPI /predict endpoint hosted locally
        import os
        port = os.getenv("PORT", "8080")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://127.0.0.1:{port}/predict",
                json=payload,
                timeout=5.0
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"ML Scorer result: risk_score={result['risk_score']}, tier={result['risk_tier']}")
                return {
                    "risk_score": result["risk_score"],
                    "risk_tier": result["risk_tier"]
                }
    except Exception as e:
        logger.warning(f"ML Scorer unavailable, using fallback heuristics: {e}")
        # Log/Warning fallback: If the FastAPI server is not running during tests,
        # we generate a mock risk score based on simple heuristics to allow seamless local testing
        score = 0.15 # Default low risk
        if state.get("payment_mode") == "COD":
            if state.get("user_history_rto_rate", 0.0) > 0.5:
                score = 0.85
            elif state.get("order_value", 0.0) >= 1000.0:
                score = 0.55
        
        tier = "LOW" if score < 0.3 else "MEDIUM" if score < 0.7 else "HIGH"
        logger.info(f"Fallback scoring: risk_score={score}, tier={tier}")
        return {
            "risk_score": score,
            "risk_tier": tier
        }

# Define the routing logic (conditional edge)
def route_by_risk(state: OrderState) -> str:
    """Decide which agent node to run based on the initial risk score."""
    score = state.get("risk_score", 0.0)
    
    if score < 0.25:
        route = "auto_approve"
    elif score < 0.45:
        route = "whatsapp_agent"
    else:
        route = "voice_agent"
    
    logger.info(f"Routing order {state.get('order_id')} with score {score} to: {route}")
    return route

def build_orchestrator():
    """Build and compile the LangGraph workflow."""
    
    # 1. Initialize StateGraph with our custom OrderState schema
    workflow = StateGraph(OrderState)
    
    # 2. Add nodes (the functional execution steps)
    workflow.add_node("score_order", score_order)
    workflow.add_node("auto_approve", auto_approve)
    workflow.add_node("whatsapp_agent", whatsapp_agent)
    workflow.add_node("voice_agent", voice_agent)
    workflow.add_node("rescore", rescore)
    
    # 3. Define Entrypoint
    workflow.set_entry_point("score_order")
    
    # 4. Define Conditional Edges (routing logic from scoring node)
    workflow.add_conditional_edges(
        "score_order",
        route_by_risk,
        {
            "auto_approve": "auto_approve",
            "whatsapp_agent": "whatsapp_agent",
            "voice_agent": "voice_agent",
        }
    )
    
    # 5. Define Static Edges (after agent execution, flow to rescore or end)
    workflow.add_edge("auto_approve", END)
    workflow.add_edge("whatsapp_agent", "rescore")
    workflow.add_edge("voice_agent", "rescore")
    workflow.add_edge("rescore", END)
    
    # 6. Compile
    return workflow.compile()

# Compile a shared singleton instance of the orchestrator graph
orchestrator = build_orchestrator()

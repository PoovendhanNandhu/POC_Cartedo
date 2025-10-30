"""LangGraph workflow for scenario re-contextualization."""
from langgraph.graph import StateGraph, END
from src.graph.state import WorkflowState
from src.graph.nodes import (
    ingestor_node,
    analyzer_node,
    transformer_node,
    consistency_checker_node,
    validator_node,
    finalizer_node
)
from src.utils.config import config


def should_transform(state: WorkflowState) -> str:
    """Decide if transformation is needed."""
    if state.get("final_status") == "OK":
        # Short-circuit: same scenario selected
        return "finalize"
    return "transform"


def should_retry_transform(state: WorkflowState) -> str:
    """Decide if transformation should be retried."""
    consistency_score = state.get("consistency_score", 0)
    retry_count = state.get("retry_count", 0)
    
    if consistency_score < config.CONSISTENCY_THRESHOLD and retry_count < config.MAX_RETRIES:
        state["retry_count"] = retry_count + 1
        return "transform"
    return "validate"


def should_abort(state: WorkflowState) -> str:
    """Decide if workflow should abort."""
    if state.get("final_status") == "FAIL":
        validation_errors = state.get("validation_errors", [])
        # Check if locked fields were modified
        for error in validation_errors:
            if "Locked field was modified" in str(error):
                return "finalize"  # Abort immediately
    return "finalize"


def create_workflow() -> StateGraph:
    """
    Create the LangGraph workflow for scenario re-contextualization.
    
    Workflow:
    START → Ingestor → Analyzer → [same scenario?] → Finalizer
                                  ↓ [different]
                               Transformer ←──┐
                                  ↓           │
                            ConsistencyChecker│
                                  ↓           │
                            [score < threshold & retries < max?]
                                  ↓           │
                              Validator       │
                                  ↓
                              Finalizer → END
    """
    # Create workflow
    workflow = StateGraph(WorkflowState)
    
    # Add nodes
    workflow.add_node("ingest", ingestor_node)
    workflow.add_node("analyze", analyzer_node)
    workflow.add_node("transform", transformer_node)
    workflow.add_node("check_consistency", consistency_checker_node)
    workflow.add_node("validate", validator_node)
    workflow.add_node("finalize", finalizer_node)
    
    # Set entry point
    workflow.set_entry_point("ingest")
    
    # Add edges
    workflow.add_edge("ingest", "analyze")
    
    # Conditional: same scenario or transform?
    workflow.add_conditional_edges(
        "analyze",
        should_transform,
        {
            "transform": "transform",
            "finalize": "finalize"
        }
    )
    
    # Transform → Check consistency
    workflow.add_edge("transform", "check_consistency")
    
    # Conditional: retry transform or proceed to validation?
    workflow.add_conditional_edges(
        "check_consistency",
        should_retry_transform,
        {
            "transform": "transform",
            "validate": "validate"
        }
    )
    
    # Conditional: abort or finalize?
    workflow.add_conditional_edges(
        "validate",
        should_abort,
        {
            "finalize": "finalize"
        }
    )
    
    # Finalize → END
    workflow.add_edge("finalize", END)
    
    return workflow.compile()


# Create compiled workflow instance
scenario_workflow = create_workflow()

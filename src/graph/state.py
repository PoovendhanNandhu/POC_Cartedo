"""State schema for LangGraph workflow."""
from typing import TypedDict, Optional, Literal


class WorkflowState(TypedDict, total=False):
    """Shared state across all LangGraph nodes."""
    
    # Input data
    input_json: dict
    selected_scenario: str | int
    
    # Scenario analysis
    selected_scenario_index: int
    selected_scenario_text: str
    current_scenario_text: str
    scenario_options: list[str]
    
    # Entity mapping
    entity_map: dict[str, str]
    candidate_paths: list[str]
    style_profile: dict
    
    # Hashing and validation
    locked_field_hashes: dict[str, str]
    
    # Transformation results
    transformed_json: Optional[dict]
    
    # Validation results
    changed_paths: list[str]
    validation_errors: list[dict]
    consistency_score: float
    
    # Execution metadata
    retry_count: int
    node_logs: list[dict]
    runtime_ms: int
    final_status: Literal["OK", "FAIL", "PENDING"]
    
    # OpenAI stats
    openai_stats: dict

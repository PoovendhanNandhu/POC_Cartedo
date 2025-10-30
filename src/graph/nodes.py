"""LangGraph nodes for scenario re-contextualization workflow."""
import json
import time
import re
from typing import Any
from copy import deepcopy
from src.graph.state import WorkflowState
from src.utils.helpers import (
    compute_sha256,
    get_by_path,
    generate_json_diff,
    search_keywords,
    create_log_entry
)
from src.utils.openai_client import openai_client
from src.utils.config import config


def ingestor_node(state: WorkflowState) -> WorkflowState:
    """
    Ingest and validate input JSON, compute locked field hashes.
    
    Args:
        state: Current workflow state
    
    Returns:
        Updated state with hashes and validation
    """
    start_time = time.time()
    
    try:
        input_json = state["input_json"]
        selected_scenario = state["selected_scenario"]
        
        # Validate input JSON structure
        if "topicWizardData" not in input_json:
            raise ValueError("Invalid JSON: missing 'topicWizardData' key")
        
        data = input_json["topicWizardData"]
        
        # Validate locked fields exist
        locked_field_hashes = {}
        for field in config.LOCKED_FIELDS:
            if field not in data:
                raise ValueError(f"Locked field '{field}' not found in input JSON")
            
            # Compute hash for locked field
            field_value = data[field]
            field_hash = compute_sha256(field_value)
            locked_field_hashes[field] = field_hash
        
        # Extract scenario options
        scenario_options = data.get("scenarioOptions", [])
        if not scenario_options:
            raise ValueError("No scenarioOptions found in input JSON")
        
        # Validate selected_scenario
        if isinstance(selected_scenario, int):
            if selected_scenario < 0 or selected_scenario >= len(scenario_options):
                raise ValueError(f"Invalid scenario index: {selected_scenario}")
            selected_scenario_index = selected_scenario
            selected_scenario_text = scenario_options[selected_scenario]
        else:
            # Try to find matching scenario text
            selected_scenario_text = selected_scenario
            selected_scenario_index = None
            for idx, option in enumerate(scenario_options):
                if option.lower() == selected_scenario.lower() or \
                   selected_scenario.lower() in option.lower():
                    selected_scenario_index = idx
                    selected_scenario_text = option
                    break
            
            if selected_scenario_index is None:
                raise ValueError(f"Scenario not found: {selected_scenario}")
        
        # Get current scenario
        current_scenario_text = data.get("selectedScenarioOption", "")
        
        # Debug logging
        import logging
        logging.info(f"IngestorNode: current_scenario_text length: {len(current_scenario_text)}")
        logging.info(f"IngestorNode: selected_scenario_text length: {len(selected_scenario_text)}")
        logging.info(f"IngestorNode: selected_scenario_index: {selected_scenario_index}")
        
        # Update state
        duration_ms = int((time.time() - start_time) * 1000)
        
        state["locked_field_hashes"] = locked_field_hashes
        state["scenario_options"] = scenario_options
        state["selected_scenario_index"] = selected_scenario_index
        state["selected_scenario_text"] = selected_scenario_text
        state["current_scenario_text"] = current_scenario_text
        state["retry_count"] = 0
        state["node_logs"] = state.get("node_logs", [])
        state["final_status"] = "PENDING"
        state["validation_errors"] = []
        
        state["node_logs"].append(create_log_entry(
            "IngestorNode",
            "success",
            duration_ms,
            locked_fields_count=len(locked_field_hashes),
            scenario_count=len(scenario_options)
        ))
        
        return state
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        state["node_logs"] = state.get("node_logs", [])
        state["node_logs"].append(create_log_entry(
            "IngestorNode",
            "failed",
            duration_ms,
            error=str(e)
        ))
        state["final_status"] = "FAIL"
        state["validation_errors"] = [{"node": "IngestorNode", "error": str(e)}]
        return state


def analyzer_node(state: WorkflowState) -> WorkflowState:
    """
    Analyze scenarios and build entity mapping.
    
    Args:
        state: Current workflow state
    
    Returns:
        Updated state with entity mapping and candidate paths
    """
    start_time = time.time()
    
    try:
        current_scenario = state.get("current_scenario_text", "")
        selected_scenario = state.get("selected_scenario_text", "")
        
        # Debug: Check if scenarios are empty
        if not current_scenario:
            raise ValueError(f"current_scenario_text is empty. State keys: {list(state.keys())}")
        if not selected_scenario:
            raise ValueError(f"selected_scenario_text is empty. State keys: {list(state.keys())}")
        
        # Short-circuit if same scenario
        if current_scenario.strip() == selected_scenario.strip():
            duration_ms = int((time.time() - start_time) * 1000)
            state["node_logs"].append(create_log_entry(
                "AnalyzerNode",
                "short_circuit",
                duration_ms,
                message="Same scenario selected, no transformation needed"
            ))
            state["final_status"] = "OK"
            state["transformed_json"] = state["input_json"]
            state["entity_map"] = {}
            return state
        
        # Extract entities from current scenario
        current_entities = extract_entities_from_scenario(current_scenario)
        
        # Extract entities from selected scenario
        target_entities = extract_entities_from_scenario(selected_scenario)
        
        # Build entity mapping
        entity_map = build_entity_mapping(current_entities, target_entities)
        
        # Identify candidate transformation paths
        candidate_paths = [
            "lessonInformation.lesson",
            "selectedScenarioOption",
            "simulationName",
            "workplaceScenario.scenario",
            "workplaceScenario.background.organizationName",
            "workplaceScenario.background.aboutOrganization",
            "workplaceScenario.background.organizationImageKeyWords",
            "workplaceScenario.challenge.currentIssue",
            "workplaceScenario.learnerRoleReportingManager.learnerRole.roleDescription",
            "workplaceScenario.learnerRoleReportingManager.learnerRole.scopeOfWork",
            "workplaceScenario.learnerRoleReportingManager.reportingManager.name",
            "workplaceScenario.learnerRoleReportingManager.reportingManager.email",
            "workplaceScenario.learnerRoleReportingManager.reportingManager.message",
        ]
        
        # Style profile (basic analysis)
        style_profile = {
            "avg_sentence_length": 18,
            "tone": "professional_instructional",
            "formality": "high"
        }
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        state["entity_map"] = entity_map
        state["candidate_paths"] = candidate_paths
        state["style_profile"] = style_profile
        
        state["node_logs"].append(create_log_entry(
            "AnalyzerNode",
            "success",
            duration_ms,
            entity_mappings=len(entity_map),
            candidate_paths_count=len(candidate_paths)
        ))
        
        return state
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        state["node_logs"].append(create_log_entry(
            "AnalyzerNode",
            "failed",
            duration_ms,
            error=str(e)
        ))
        state["validation_errors"].append({"node": "AnalyzerNode", "error": str(e)})
        # Set default empty entity_map to prevent downstream errors
        state["entity_map"] = {}
        state["candidate_paths"] = []
        state["style_profile"] = {}
        return state


def extract_entities_from_scenario(scenario_text: str) -> dict:
    """Extract key entities from scenario text."""
    entities = {}
    
    # Extract brand names (capitalized words before "is/faces/sees")
    brand_match = re.search(r"([A-Z][a-zA-Z]+(?:'s)?)\s+(?:is|faces|sees|'s)", scenario_text)
    if brand_match:
        entities["brand"] = brand_match.group(1).replace("'s", "")
    
    # Extract competitor (after "after" or "when")
    competitor_match = re.search(r"(?:after|when)\s+([A-Z][a-zA-Z]+(?:'s)?)", scenario_text)
    if competitor_match:
        entities["competitor"] = competitor_match.group(1).replace("'s", "")
    
    # Extract challenge type
    if "$1 menu" in scenario_text or "$1 value menu" in scenario_text:
        entities["challenge"] = "$1 value menu"
    elif "Buy One Get One Free" in scenario_text or "BOGO" in scenario_text:
        entities["challenge"] = "BOGO promotion"
    elif "discount" in scenario_text.lower():
        entities["challenge"] = "discount promotion"
    
    # Extract industry
    if "restaurant" in scenario_text.lower() or "fast-casual" in scenario_text.lower() or "food" in scenario_text.lower():
        entities["industry"] = "fast-casual restaurant"
    elif "fashion" in scenario_text.lower() or "retail" in scenario_text.lower():
        entities["industry"] = "fashion retail"
    elif "airline" in scenario_text.lower():
        entities["industry"] = "airline"
    elif "hotel" in scenario_text.lower():
        entities["industry"] = "hospitality"
    
    return entities


def build_entity_mapping(current: dict, target: dict) -> dict[str, str]:
    """Build mapping between current and target entities."""
    mapping = {}
    
    if "brand" in current and "brand" in target:
        mapping[current["brand"]] = target["brand"]
    
    if "competitor" in current and "competitor" in target:
        mapping[current["competitor"]] = target["competitor"]
    
    if "challenge" in current and "challenge" in target:
        mapping[current["challenge"]] = target["challenge"]
    
    if "industry" in current and "industry" in target:
        mapping[current["industry"]] = target["industry"]
    
    return mapping


def transformer_node(state: WorkflowState) -> WorkflowState:
    """
    Transform JSON using OpenAI with entity mapping.
    
    Args:
        state: Current workflow state
    
    Returns:
        Updated state with transformed JSON
    """
    start_time = time.time()
    
    try:
        input_json = deepcopy(state["input_json"])
        entity_map = state["entity_map"]
        selected_scenario = state["selected_scenario_text"]
        current_scenario = state["current_scenario_text"]
        
        # Build system prompt
        system_prompt = f"""You are transforming a business simulation JSON from one scenario to another.

CRITICAL RULES:
1. NEVER modify these locked fields (keep byte-for-byte identical):
   - scenarioOptions
   - assessmentCriterion
   - selectedAssessmentCriterion
   - industryAlignedActivities
   - selectedIndustryAlignedActivities

2. Keep EXACT same JSON structure (same keys, same nesting, same array lengths)

3. Apply these entity mappings consistently:
{json.dumps(entity_map, indent=2)}

4. Replace ALL brand names, competitor names, industry terms, and contextual details

5. Maintain professional instructional tone

6. Preserve field types (string→string, array→array)

7. Keep email format patterns (e.g., name@domain.com)

8. Adapt KPIs and metrics to new industry context while preserving magnitude

Output ONLY valid JSON matching the input structure."""

        # Build user prompt - OPTIMIZED: Only send fields that need transformation
        topic_data = input_json.get("topicWizardData", {})
        
        transformable_fields = {
            "lessonInformation": topic_data.get("lessonInformation", {}),
            "selectedScenarioOption": topic_data.get("selectedScenarioOption", ""),
            "simulationName": topic_data.get("simulationName", ""),
            "workplaceScenario": topic_data.get("workplaceScenario", {})
        }
        
        user_prompt = f"""Transform from current to target scenario.

CURRENT: {current_scenario[:200]}...
TARGET: {selected_scenario[:200]}...

MAPPINGS:
{json.dumps(entity_map, indent=2)}

TRANSFORM THESE FIELDS:
{json.dumps(transformable_fields, indent=2)}

Return COMPLETE topicWizardData as JSON."""

        # Call OpenAI
        transformed_data = openai_client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=16000
        )
        
        # CRITICAL: Force-restore locked fields from original input
        # (OpenAI sometimes modifies them despite instructions)
        input_data = input_json.get("topicWizardData", {})

        # Check if OpenAI returned data wrapped in topicWizardData or not
        if "topicWizardData" in transformed_data:
            transformed_topic_data = transformed_data["topicWizardData"]
        else:
            # OpenAI returned fields directly - wrap them in topicWizardData
            transformed_topic_data = transformed_data
            transformed_data = {}  # Create new root object

        for locked_field in config.LOCKED_FIELDS:
            if locked_field in input_data:
                # Restore original locked field
                transformed_topic_data[locked_field] = deepcopy(input_data[locked_field])

        # Always wrap in topicWizardData to match input structure
        transformed_data = {"topicWizardData": transformed_topic_data}
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        state["transformed_json"] = transformed_data
        state["openai_stats"] = openai_client.get_stats()
        
        state["node_logs"].append(create_log_entry(
            "TransformerNode",
            "success",
            duration_ms,
            tokens_used=openai_client.total_tokens_used
        ))
        
        return state
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        state["node_logs"].append(create_log_entry(
            "TransformerNode",
            "failed",
            duration_ms,
            error=str(e)
        ))
        state["validation_errors"].append({"node": "TransformerNode", "error": str(e)})
        return state


def transformer_node_streaming(state: WorkflowState, stream_callback=None):
    """
    Transform JSON using OpenAI with streaming support.
    
    Args:
        state: Current workflow state
        stream_callback: Optional callback function for streaming chunks
    
    Yields:
        Streaming chunks from OpenAI
    
    Returns:
        Updated state with transformed JSON
    """
    start_time = time.time()
    
    try:
        input_json = deepcopy(state["input_json"])
        entity_map = state.get("entity_map", {})
        selected_scenario = state.get("selected_scenario_text", "")
        current_scenario = state.get("current_scenario_text", "")
        
        if not entity_map:
            raise ValueError("entity_map is empty or missing - AnalyzerNode may have failed")
        if not selected_scenario:
            raise ValueError("selected_scenario_text is missing - IngestorNode may have failed")
        if not current_scenario:
            raise ValueError("current_scenario_text is missing - IngestorNode may have failed")
        
        # Build system prompt
        system_prompt = f"""You are transforming a business simulation JSON from one scenario to another.

CRITICAL RULES:
1. NEVER modify these locked fields (keep byte-for-byte identical):
   - scenarioOptions
   - assessmentCriterion
   - selectedAssessmentCriterion
   - industryAlignedActivities
   - selectedIndustryAlignedActivities

2. Keep EXACT same JSON structure (same keys, same nesting, same array lengths)

3. Apply these entity mappings consistently:
{json.dumps(entity_map, indent=2)}

4. Replace ALL brand names, competitor names, industry terms, and contextual details

5. Maintain professional instructional tone

6. Preserve field types (string→string, array→array)

7. Keep email format patterns (e.g., name@domain.com)

8. Adapt KPIs and metrics to new industry context while preserving magnitude

Output ONLY valid JSON matching the input structure."""

        # Build user prompt - OPTIMIZED: Only send fields that need transformation
        topic_data = input_json.get("topicWizardData", {})
        
        # Extract only the fields that will change (exclude locked fields)
        transformable_fields = {
            "lessonInformation": topic_data.get("lessonInformation", {}),
            "selectedScenarioOption": topic_data.get("selectedScenarioOption", ""),
            "simulationName": topic_data.get("simulationName", ""),
            "workplaceScenario": topic_data.get("workplaceScenario", {})
        }
        
        user_prompt = f"""Transform this JSON from the current scenario to the target scenario.

CURRENT SCENARIO:
{current_scenario[:200]}...

TARGET SCENARIO:
{selected_scenario[:200]}...

ENTITY MAPPINGS TO APPLY:
{json.dumps(entity_map, indent=2)}

FIELDS TO TRANSFORM (return complete transformed topicWizardData):
{json.dumps(transformable_fields, indent=2)}

IMPORTANT: 
- Return the COMPLETE topicWizardData object
- Include all original fields (even locked ones - I'll restore them later)
- Only transform the scenario-specific content
- Maintain exact JSON structure

Return complete topicWizardData as valid JSON."""

        # Call OpenAI with streaming
        transformed_data = None
        char_count = 0
        
        for chunk in openai_client.generate_json_streaming(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=16000
        ):
            if isinstance(chunk, dict) and chunk.get("__complete__"):
                # Final complete JSON
                transformed_data = chunk.get("data")
            else:
                # Streaming chunk
                char_count += len(chunk)
                if stream_callback:
                    stream_callback({
                        "type": "openai_chunk",
                        "chunk": chunk,
                        "total_chars": char_count
                    })
                yield chunk
        
        if not transformed_data:
            raise ValueError("No complete data received from OpenAI stream")
        
        # CRITICAL: Force-restore locked fields from original input
        input_data = input_json.get("topicWizardData", {})

        # Check if OpenAI returned data wrapped in topicWizardData or not
        if "topicWizardData" in transformed_data:
            transformed_topic_data = transformed_data["topicWizardData"]
        else:
            # OpenAI returned fields directly - wrap them in topicWizardData
            transformed_topic_data = transformed_data
            transformed_data = {}  # Create new root object

        for locked_field in config.LOCKED_FIELDS:
            if locked_field in input_data:
                # Restore original locked field
                transformed_topic_data[locked_field] = deepcopy(input_data[locked_field])

        # Always wrap in topicWizardData to match input structure
        transformed_data = {"topicWizardData": transformed_topic_data}
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        state["transformed_json"] = transformed_data
        state["openai_stats"] = openai_client.get_stats()
        
        state["node_logs"].append(create_log_entry(
            "TransformerNode",
            "success",
            duration_ms,
            tokens_used=openai_client.total_tokens_used
        ))
        
        # Yield completion signal with updated state
        yield {"__complete__": True, "__state__": state}
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        state["node_logs"].append(create_log_entry(
            "TransformerNode",
            "failed",
            duration_ms,
            error=str(e)
        ))
        state["validation_errors"].append({"node": "TransformerNode", "error": str(e)})
        
        # Yield completion signal with error state
        yield {"__complete__": True, "__state__": state, "__error__": str(e)}


def consistency_checker_node(state: WorkflowState) -> WorkflowState:
    """
    Check cross-field consistency in transformed JSON.
    
    Args:
        state: Current workflow state
    
    Returns:
        Updated state with consistency score
    """
    start_time = time.time()
    
    try:
        transformed_json = state.get("transformed_json")
        if not transformed_json:
            raise ValueError("No transformed JSON to check")
        
        entity_map = state["entity_map"]
        current_scenario = state["current_scenario_text"]
        
        # Extract old scenario keywords
        old_keywords = []
        for old_entity in entity_map.keys():
            old_keywords.append(old_entity)
        
        # Search for old keywords in transformed JSON (excluding locked fields)
        findings = search_keywords(
            transformed_json,
            old_keywords,
            exclude_paths=config.LOCKED_FIELDS
        )
        
        # Calculate consistency score
        total_checks = len(old_keywords)
        failed_checks = len(findings)
        consistency_score = max(0.0, 1.0 - (failed_checks / max(total_checks, 1)))
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        state["consistency_score"] = consistency_score
        
        state["node_logs"].append(create_log_entry(
            "ConsistencyCheckerNode",
            "success",
            duration_ms,
            consistency_score=consistency_score,
            old_keywords_found=len(findings)
        ))
        
        return state
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        state["node_logs"].append(create_log_entry(
            "ConsistencyCheckerNode",
            "failed",
            duration_ms,
            error=str(e)
        ))
        state["consistency_score"] = 0.0
        return state


def validator_node(state: WorkflowState) -> WorkflowState:
    """
    Validate transformed JSON against locked fields and schema.
    
    Args:
        state: Current workflow state
    
    Returns:
        Updated state with validation results
    """
    start_time = time.time()
    
    try:
        input_json = state["input_json"]
        transformed_json = state.get("transformed_json")
        locked_field_hashes = state["locked_field_hashes"]
        
        if not transformed_json:
            raise ValueError("No transformed JSON to validate")
        
        validation_errors = []
        
        # Check locked fields immutability
        input_data = input_json.get("topicWizardData", {})
        transformed_data = transformed_json.get("topicWizardData", {})
        
        locked_fields_pass = True
        for field in config.LOCKED_FIELDS:
            if field in transformed_data:
                current_hash = compute_sha256(transformed_data[field])
                expected_hash = locked_field_hashes[field]
                
                if current_hash != expected_hash:
                    locked_fields_pass = False
                    validation_errors.append({
                        "field": field,
                        "error": "Locked field was modified",
                        "expected_hash": expected_hash,
                        "actual_hash": current_hash
                    })
        
        # Generate diff of changed paths
        changed_paths = generate_json_diff(input_json, transformed_json)
        
        # Search for old scenario keywords
        entity_map = state.get("entity_map", {})
        old_keywords = list(entity_map.keys())
        keyword_findings = search_keywords(
            transformed_json,
            old_keywords,
            exclude_paths=config.LOCKED_FIELDS
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        state["changed_paths"] = changed_paths
        state["validation_errors"] = validation_errors
        
        # Set final status
        if not locked_fields_pass:
            state["final_status"] = "FAIL"
        elif state.get("consistency_score", 0) >= config.CONSISTENCY_THRESHOLD:
            state["final_status"] = "OK"
        else:
            state["final_status"] = "FAIL"
        
        state["node_logs"].append(create_log_entry(
            "ValidatorNode",
            "success" if locked_fields_pass else "failed",
            duration_ms,
            locked_fields_pass=locked_fields_pass,
            changed_paths_count=len(changed_paths),
            old_keywords_found=len(keyword_findings)
        ))
        
        return state
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        state["node_logs"].append(create_log_entry(
            "ValidatorNode",
            "failed",
            duration_ms,
            error=str(e)
        ))
        state["final_status"] = "FAIL"
        state["validation_errors"].append({"node": "ValidatorNode", "error": str(e)})
        return state


def finalizer_node(state: WorkflowState) -> WorkflowState:
    """
    Finalize and prepare outputs.
    
    Args:
        state: Current workflow state
    
    Returns:
        Final state with all outputs ready
    """
    start_time = time.time()
    
    try:
        # Calculate total runtime
        total_runtime = sum(log.get("duration_ms", 0) for log in state.get("node_logs", []))
        state["runtime_ms"] = total_runtime
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        state["node_logs"].append(create_log_entry(
            "FinalizerNode",
            "success",
            duration_ms,
            total_runtime_ms=total_runtime
        ))
        
        return state
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        state["node_logs"].append(create_log_entry(
            "FinalizerNode",
            "failed",
            duration_ms,
            error=str(e)
        ))
        return state

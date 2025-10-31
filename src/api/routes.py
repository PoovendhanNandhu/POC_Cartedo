"""FastAPI routes for scenario re-contextualization API."""
import json
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from src.models.schemas import (
    TransformRequest,
    TransformResponse,
    ValidationReport,
    ValidateOnlyRequest,
    HealthResponse
)
from src.graph.workflow import scenario_workflow
from src.utils.openai_client import openai_client
from src.utils.config import config
from src.utils.helpers import compute_sha256, generate_json_diff, search_keywords

router = APIRouter()


@router.post("/transform/stream-openai")
async def transform_scenario_stream_openai(request: TransformRequest):
    """
    Transform JSON with real-time OpenAI streaming output.
    
    Shows the actual JSON being generated token-by-token from OpenAI.
    """
    async def event_generator():
        """Generate SSE events including OpenAI streaming chunks."""
        try:
            from src.graph.nodes import (
                ingestor_node, analyzer_node, transformer_node_streaming,
                consistency_checker_node, validator_node, finalizer_node
            )
            import time as time_module
            
            # Send start event
            yield f"data: {json.dumps({'event': 'start', 'message': 'Starting transformation'})}\n\n"
            await asyncio.sleep(0.05)
            
            # Prepare initial state
            state = {
                "input_json": request.input_json,
                "selected_scenario": request.selected_scenario,
                "node_logs": [],
                "validation_errors": [],
                "retry_count": 0,
                "final_status": "PENDING"
            }
            
            # Run nodes in thread pool (except transformer which we'll stream)
            import concurrent.futures
            loop = asyncio.get_event_loop()
            
            # 1. Ingestor
            yield f"data: {json.dumps({'event': 'node_start', 'node': 'IngestorNode'})}\n\n"
            with concurrent.futures.ThreadPoolExecutor() as pool:
                state = await loop.run_in_executor(pool, ingestor_node, state)
            yield f"data: {json.dumps({'event': 'node_complete', 'node': 'IngestorNode'})}\n\n"
            await asyncio.sleep(0.05)
            
            # 2. Analyzer
            yield f"data: {json.dumps({'event': 'node_start', 'node': 'AnalyzerNode'})}\n\n"
            with concurrent.futures.ThreadPoolExecutor() as pool:
                state = await loop.run_in_executor(pool, analyzer_node, state)
            yield f"data: {json.dumps({'event': 'node_complete', 'node': 'AnalyzerNode'})}\n\n"
            await asyncio.sleep(0.05)
            
            # 3. Transformer with streaming (progress only, no chunks)
            # Skip transformation if Analyzer short-circuited (same scenario)
            if state.get("final_status") == "OK" and state.get("transformed_json"):
                yield f"data: {json.dumps({'event': 'node_skipped', 'node': 'TransformerNode', 'message': 'Same scenario selected; skipping transformation'})}\n\n"
                await asyncio.sleep(0.05)
            else:
                yield f"data: {json.dumps({'event': 'node_start', 'node': 'TransformerNode', 'message': 'Starting OpenAI transformation'})}\n\n"
                await asyncio.sleep(0.05)
                
                # Run transformer streaming in thread pool but don't send chunks
                updated_state = None
                
                # Use a queue to communicate chunks from thread
                from queue import Queue
                chunk_queue = Queue()

                def run_transformer():
                    final_state = None
                    error_msg = None
                    chunk_count = 0
                    try:
                        for chunk in transformer_node_streaming(state):
                            if isinstance(chunk, dict) and chunk.get("__complete__"):
                                final_state = chunk.get("__state__")
                                if chunk.get("__error__"):
                                    error_msg = chunk["__error__"]
                            else:
                                # Send chunks to queue for streaming
                                chunk_count += 1
                                chunk_queue.put({'type': 'chunk', 'content': chunk, 'count': chunk_count})
                    except Exception as e:
                        import traceback
                        error_msg = f"{str(e)}\n{traceback.format_exc()}"

                    chunk_queue.put({'type': 'done'})
                    return final_state, error_msg

                # Execute in thread pool
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = loop.run_in_executor(pool, run_transformer)

                    # Stream chunks while waiting
                    while not future.done():
                        await asyncio.sleep(0.1)  # Check frequently

                        # Process any chunks in queue
                        while not chunk_queue.empty():
                            chunk_data = chunk_queue.get()
                            if chunk_data['type'] == 'chunk':
                                yield f"data: {json.dumps({'event': 'openai_chunk', 'chunk': chunk_data['content'], 'count': chunk_data['count']})}\n\n"
                            elif chunk_data['type'] == 'done':
                                break

                    # Get any remaining chunks
                    while not chunk_queue.empty():
                        chunk_data = chunk_queue.get()
                        if chunk_data['type'] == 'chunk':
                            yield f"data: {json.dumps({'event': 'openai_chunk', 'chunk': chunk_data['content'], 'count': chunk_data['count']})}\n\n"

                    # Get results
                    updated_state, error_msg = await future
                
                # Check for errors
                if error_msg:
                    yield f"data: {json.dumps({'event': 'error', 'message': f'TransformerNode error: {error_msg}'})}\n\n"
                    return
                
                # Update state with result
                if updated_state:
                    state = updated_state
                else:
                    # If no state returned, something went wrong
                    yield f"data: {json.dumps({'event': 'error', 'message': 'TransformerNode did not return updated state'})}\n\n"
                    return
                
                yield f"data: {json.dumps({'event': 'node_complete', 'node': 'TransformerNode', 'message': 'Transformation complete'})}\n\n"
                await asyncio.sleep(0.05)
            
            # 4. Consistency Checker
            yield f"data: {json.dumps({'event': 'node_start', 'node': 'ConsistencyCheckerNode'})}\n\n"
            with concurrent.futures.ThreadPoolExecutor() as pool:
                state = await loop.run_in_executor(pool, consistency_checker_node, state)
            yield f"data: {json.dumps({'event': 'node_complete', 'node': 'ConsistencyCheckerNode'})}\n\n"
            await asyncio.sleep(0.05)
            
            # 5. Validator
            yield f"data: {json.dumps({'event': 'node_start', 'node': 'ValidatorNode'})}\n\n"
            with concurrent.futures.ThreadPoolExecutor() as pool:
                state = await loop.run_in_executor(pool, validator_node, state)
            yield f"data: {json.dumps({'event': 'node_complete', 'node': 'ValidatorNode'})}\n\n"
            await asyncio.sleep(0.05)
            
            # 6. Finalizer
            with concurrent.futures.ThreadPoolExecutor() as pool:
                state = await loop.run_in_executor(pool, finalizer_node, state)
            
            # Build response
            output_json = state.get("transformed_json", request.input_json)
            
            validation_report = ValidationReport(
                schema_pass=state.get("final_status") == "OK",
                locked_fields_compliance=len([e for e in state.get("validation_errors", []) 
                                              if e.get("field") in config.LOCKED_FIELDS]) == 0,
                locked_field_hashes=state.get("locked_field_hashes", {}),
                changed_paths=state.get("changed_paths", []),
                scenario_consistency_score=state.get("consistency_score", 0.0),
                old_scenario_keywords_found=search_keywords(
                    state.get("transformed_json", {}),
                    list(state.get("entity_map", {}).keys()),
                    exclude_paths=config.LOCKED_FIELDS
                ),
                runtime_ms=state.get("runtime_ms", 0),
                retries=state.get("retry_count", 0),
                openai_stats=state.get("openai_stats", {}),
                final_status=state.get("final_status", "FAIL")
            )
            
            response = TransformResponse(
                output_json=output_json,
                validation_report=validation_report,
                execution_time_ms=state.get("runtime_ms", 0)
            )
            
            # Send final result
            yield f"data: {json.dumps({'event': 'complete', 'result': response.model_dump()})}\n\n"
            
        except Exception as e:
            import traceback
            yield f"data: {json.dumps({'event': 'error', 'message': str(e), 'traceback': traceback.format_exc()})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/validate")
async def validate_transformation(request: ValidateOnlyRequest):
    """
    Validate an already-transformed JSON without performing transformation.
    
    Args:
        request: ValidateOnlyRequest with original and transformed JSON
    
    Returns:
        ValidationReport
    """
    try:
        original = request.original_json
        transformed = request.transformed_json
        locked_fields = request.locked_fields or config.LOCKED_FIELDS
        
        # Compute hashes for locked fields
        locked_field_hashes = {}
        validation_errors = []
        
        original_data = original.get("topicWizardData", {})
        transformed_data = transformed.get("topicWizardData", {})
        
        for field in locked_fields:
            if field in original_data:
                original_hash = compute_sha256(original_data[field])
                locked_field_hashes[field] = original_hash
                
                if field in transformed_data:
                    transformed_hash = compute_sha256(transformed_data[field])
                    if original_hash != transformed_hash:
                        validation_errors.append({
                            "field": field,
                            "error": "Locked field was modified"
                        })
        
        # Generate diff
        changed_paths = generate_json_diff(original, transformed)
        
        # Determine status
        locked_pass = len(validation_errors) == 0
        final_status = "OK" if locked_pass else "FAIL"
        
        return ValidationReport(
            schema_pass=True,
            locked_fields_compliance=locked_pass,
            locked_field_hashes=locked_field_hashes,
            changed_paths=changed_paths,
            scenario_consistency_score=1.0 if locked_pass else 0.0,
            old_scenario_keywords_found=[],
            runtime_ms=0,
            retries=0,
            openai_stats={},
            final_status=final_status
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check API and OpenAI connectivity."""
    try:
        # Test OpenAI connection
        openai_connected = await openai_client.test_connection()
        
        return HealthResponse(
            status="healthy",
            version=config.APP_VERSION,
            openai_connected=openai_connected
        )
    except Exception as e:
        return HealthResponse(
            status="unhealthy",
            version=config.APP_VERSION,
            openai_connected=False
        )


@router.get("/scenarios")
async def list_scenarios(input_json: str = None):
    """
    List available scenarios from input JSON or sample file.

    Args:
        input_json: Base64 encoded JSON or JSON string (optional)

    Returns:
        List of scenario options
    """
    try:
        # If no input provided, use sample_input.json
        if not input_json:
            import os
            sample_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "sample_input.json")
            if os.path.exists(sample_file):
                with open(sample_file, 'r') as f:
                    data = json.load(f)
            else:
                return {"message": "No input provided and sample_input.json not found"}
        else:
            data = json.loads(input_json)

        scenario_options = data.get("topicWizardData", {}).get("scenarioOptions", [])
        current_scenario = data.get("topicWizardData", {}).get("selectedScenarioOption", "")

        return {
            "total": len(scenario_options),
            "current_scenario": current_scenario,
            "scenarios": scenario_options  # Return simple array for easier UI handling
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

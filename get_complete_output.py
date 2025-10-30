#!/usr/bin/env python3
"""
Helper script to get the complete JSON output from the streaming endpoint.
Extracts the final 'complete' event and saves the full scenario JSON.
"""
import json
import requests
import sys

def get_complete_scenario(input_json, selected_scenario, output_file="complete_scenario.json"):
    """
    Call the streaming endpoint and extract the complete final JSON.

    Args:
        input_json: The input JSON object
        selected_scenario: The scenario option (string or index)
        output_file: Where to save the complete output
    """
    url = "http://localhost:8000/api/v1/transform/stream-openai"

    payload = {
        "input_json": input_json,
        "selected_scenario": selected_scenario
    }

    print(f"🚀 Sending request to {url}")
    print(f"📄 Selected scenario: {selected_scenario}\n")

    # Stream the response
    response = requests.post(url, json=payload, stream=True, timeout=300)

    if response.status_code != 200:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        return None

    print("📡 Receiving streaming response...\n")

    complete_result = None
    output_json_data = None
    chunk_count = 0

    # Process each line in the stream
    for line in response.iter_lines():
        if not line:
            continue

        line = line.decode('utf-8')

        # SSE format: "data: {...}"
        if line.startswith('data: '):
            data_str = line[6:]  # Remove "data: " prefix
            try:
                event_data = json.loads(data_str)
                event_type = event_data.get('event', '')

                # Print progress
                if event_type == 'start':
                    print(f"✅ {event_data.get('message', '')}")
                elif event_type == 'node_start':
                    print(f"⏳ Starting: {event_data.get('node', '')}")
                elif event_type == 'node_complete':
                    print(f"✅ Completed: {event_data.get('node', '')}")
                elif event_type == 'openai_chunk':
                    chunk_count += 1
                    if chunk_count % 50 == 0:
                        print(f"   📝 Received {chunk_count} chunks...")
                elif event_type == 'output_json':
                    print(f"\n📦 Received complete output JSON!")
                    output_json_data = event_data.get('data')
                elif event_type == 'complete':
                    print(f"🎉 Transformation complete!")
                    complete_result = event_data.get('result')
                    break
                elif event_type == 'error':
                    print(f"\n❌ Error: {event_data.get('message', '')}")
                    return None

            except json.JSONDecodeError:
                continue

    if complete_result:
        # Save the complete output (includes validation report)
        with open(output_file, 'w') as f:
            json.dump(complete_result, f, indent=2)

        print(f"\n✅ Complete result saved to: {output_file}")

        # Save the output_json separately (just the transformed scenario)
        if output_json_data:
            output_json_file = output_file.replace('.json', '_output_only.json')
            with open(output_json_file, 'w') as f:
                json.dump(output_json_data, f, indent=2)
            print(f"✅ Output JSON (transformed scenario) saved to: {output_json_file}")

        print(f"📊 Total OpenAI chunks received: {chunk_count}")

        # Print summary
        output_json = complete_result.get('output_json', {}) or output_json_data
        validation = complete_result.get('validation_report', {})

        print(f"\n📋 Summary:")
        print(f"   Simulation Name: {output_json.get('simulationName', 'N/A')}")
        print(f"   Organization: {output_json.get('workplaceScenario', {}).get('background', {}).get('organizationName', 'N/A')}")
        print(f"   Validation Status: {'✅ PASS' if validation.get('schema_pass') else '❌ FAIL'}")
        print(f"   Execution Time: {complete_result.get('execution_time_ms', 0)}ms")

        return complete_result
    else:
        print("\n❌ No complete result received")
        return None


if __name__ == "__main__":
    # Example: Load from sample_input.json if it exists
    import os

    if os.path.exists("sample_input.json"):
        print("📂 Loading input from sample_input.json\n")
        with open("sample_input.json", 'r') as f:
            data = json.load(f)

        result = get_complete_scenario(
            input_json=data,
            selected_scenario=1,  # or use a string scenario option
            output_file="complete_scenario_output.json"
        )

        if result:
            print("\n✅ Success! Check 'complete_scenario_output.json' for the full output.")
    else:
        print("Usage: python get_complete_output.py")
        print("Make sure 'sample_input.json' exists in the current directory.")
        print("\nOr import and use the function:")
        print("  from get_complete_output import get_complete_scenario")
        print("  result = get_complete_scenario(your_input, scenario_option)")

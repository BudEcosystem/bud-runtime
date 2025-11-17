#!/usr/bin/env python3
#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""Generate realistic test data for executor testing from dataset.json schemas.

This script uses an LLM to generate realistic input/output values based on
the field definitions in dataset.json. The generated data can then be used
to test prompt executors across different models.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from budprompt.executors import PromptExecutorFactory
from budprompt.prompt.schemas import Message, ModelSettings


META_PROMPT_TEMPLATE = """You are a test data generator for AI task evaluation. Generate realistic sample data for testing.

Task Description:
{task_description}

Input Fields:
{formatted_input_fields}

Output Fields:
{formatted_output_fields}

Generate realistic sample data for testing this task. Return ONLY valid JSON in this exact format:
{{
  "inputs": {{
    "field_name": "realistic_value"
  }},
  "outputs": {{
    "field_name": "expected_result"
  }}
}}

Guidelines:
- Make inputs realistic and detailed (2-3 sentences for text fields)
- Generate expected outputs that logically follow from the inputs
- Match the data types specified (text, list, json object)
- For text_area: use 50-150 words with relevant details
- For list: provide 2-3 relevant items as an array
- For json: create properly formatted nested objects
- Ensure outputs are consistent with inputs and task requirements
- Return ONLY the JSON object, no explanations or markdown formatting"""


def load_dataset(file_path: str, limit: int = 50, start_index: int = 0) -> List[Dict[str, Any]]:
    """Load dataset from JSON file and return subset of records.

    Args:
        file_path: Path to dataset.json
        limit: Maximum number of records to load
        start_index: Starting index for records

    Returns:
        List of dataset records

    Raises:
        FileNotFoundError: If dataset file doesn't exist
        json.JSONDecodeError: If dataset is not valid JSON
    """
    print(f"Loading dataset from {file_path}...")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    total_records = len(data)
    print(f"Total records in dataset: {total_records}")

    # Filter records that have response field
    valid_records = [r for r in data if "response" in r and "inputs" in r.get("response", {})]
    print(f"Valid records with response data: {len(valid_records)}")

    # Apply start_index and limit
    subset = valid_records[start_index : start_index + limit]
    print(f"Selected records: {len(subset)} (from index {start_index} to {start_index + len(subset)})")

    return subset


def format_field_info(fields: List[Dict[str, Any]]) -> str:
    """Format field definitions into readable string.

    Args:
        fields: List of field definitions with input_name/output_name, type, description

    Returns:
        Formatted string listing fields with their types and descriptions
    """
    if not fields:
        return "None specified"

    formatted = []
    for field in fields:
        # Handle both input_name and output_name
        name = field.get("input_name") or field.get("output_name", "unknown")
        field_type = field.get("type", "text")
        description = field.get("description", "No description")

        formatted.append(f"- {name} ({field_type}): {description}")

    return "\n".join(formatted)


def build_generation_prompt(record: Dict[str, Any]) -> str:
    """Build meta-prompt for generating test data from dataset record.

    Args:
        record: Dataset record containing response with prompt, inputs, outputs

    Returns:
        Complete meta-prompt string
    """
    response = record.get("response", {})

    task_description = response.get("prompt", "No task description provided")
    input_fields = response.get("inputs", [])
    output_fields = response.get("outputs", [])

    formatted_inputs = format_field_info(input_fields)
    formatted_outputs = format_field_info(output_fields)

    return META_PROMPT_TEMPLATE.format(
        task_description=task_description,
        formatted_input_fields=formatted_inputs,
        formatted_output_fields=formatted_outputs,
    )


async def generate_test_data_for_record(
    executor: Any,
    record: Dict[str, Any],
    model_settings: ModelSettings,
    deployment_name: str,
    api_key: str = None,
) -> Dict[str, Any]:
    """Generate test data for a single dataset record.

    Args:
        executor: Prompt executor instance
        record: Dataset record
        model_settings: Model configuration
        deployment_name: Model deployment name
        api_key: Optional API key

    Returns:
        Dictionary with id, inputs, outputs

    Raises:
        Exception: If generation or JSON parsing fails
    """
    record_id = record.get("_id", "unknown")

    # Build generation prompt
    generation_prompt = build_generation_prompt(record)

    # Create message with generation prompt as system message
    messages = [Message(role="system", content=generation_prompt)]

    # Execute with unstructured input/output (just text)
    result = await executor.execute(
        deployment_name=deployment_name,
        model_settings=model_settings,
        input_schema=None,  # Unstructured
        output_schema=None,  # Unstructured
        messages=messages,
        input_data="Generate the test data now.",  # Trigger generation
        stream=False,
        api_key=api_key,
    )

    # Parse JSON response from LLM
    # Result should be a string containing JSON
    result_text = result if isinstance(result, str) else str(result)

    # Try to extract JSON from response
    try:
        # Remove markdown code blocks if present
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()

        generated_data = json.loads(result_text)

        # Validate structure
        if "inputs" not in generated_data or "outputs" not in generated_data:
            raise ValueError("Generated data missing 'inputs' or 'outputs' keys")

        return {"id": record_id, "inputs": generated_data["inputs"], "outputs": generated_data["outputs"]}

    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse JSON from LLM response: {e}\nResponse: {result_text[:200]}")
    except Exception as e:
        raise Exception(f"Error processing generated data: {e}")


async def generate_all_test_data(args: argparse.Namespace) -> List[Dict[str, Any]]:
    """Generate test data for all dataset records.

    Args:
        args: Command-line arguments

    Returns:
        List of generated test data records
    """
    # Load dataset
    dataset_path = Path(__file__).parent / "dataset.json"
    records = load_dataset(str(dataset_path), limit=args.limit, start_index=args.start_index)

    if not records:
        print("No records to process!")
        return []

    # Create executor
    print(f"\nInitializing executor (version 3)...")
    executor = PromptExecutorFactory.get_executor(version=3)

    # Create model settings
    model_settings = ModelSettings(
        temperature=0.7,  # Some creativity for varied data
        max_tokens=800,  # Enough for inputs + outputs
    )

    print(f"Using model: {args.model_name}")
    print(f"Gateway URL: {args.gateway_url}")
    print(f"\nGenerating test data for {len(records)} records...\n")

    results = []
    failed_count = 0
    output_path = Path(args.output)

    for idx, record in enumerate(records, start=1):
        record_id = record.get("_id", f"record_{idx}")

        try:
            print(f"[{idx}/{len(records)}] Processing {record_id}...", end=" ")

            # Generate test data
            test_data = await generate_test_data_for_record(
                executor=executor,
                record=record,
                model_settings=model_settings,
                deployment_name=args.model_name,
                api_key=args.api_key,
            )

            results.append(test_data)
            print("✓ Success")

            # Save incrementally every 10 records
            if idx % 10 == 0:
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
                print(f"  → Saved {len(results)} records to {output_path}")

        except Exception as e:
            failed_count += 1
            print(f"✗ Failed: {str(e)[:100]}")
            # Continue processing other records

    # Final save
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Generation Summary:")
    print(f"  Total records:    {len(records)}")
    print(f"  Successful:       {len(results)}")
    print(f"  Failed:           {failed_count}")
    print(f"  Output file:      {output_path}")
    print(f"{'='*60}")

    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate test data for executor testing from dataset.json",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--gateway-url",
        required=True,
        help="Model gateway base URL (e.g., http://20.66.97.208/v1)",
    )

    parser.add_argument(
        "--model-name",
        required=True,
        help="Model deployment name (e.g., qwen3-32b)",
    )

    parser.add_argument(
        "--api-key",
        default=None,
        help="Optional API key for authorization",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Number of test cases to generate",
    )

    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="Start from specific record index (for resuming)",
    )

    parser.add_argument(
        "--output",
        default="test_data.json",
        help="Output file path for generated test data",
    )

    args = parser.parse_args()

    # Set environment variable for BudServe gateway
    import os

    os.environ["BUD_GATEWAY_BASE_URL"] = args.gateway_url

    # Run async generation
    try:
        asyncio.run(generate_all_test_data(args))
        print("\n✓ Test data generation completed successfully!")
    except KeyboardInterrupt:
        print("\n\n⚠ Generation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

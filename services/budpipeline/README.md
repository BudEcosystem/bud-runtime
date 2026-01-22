# BudPipeline

Pipeline orchestration service for the bud-stack platform.

## Features

- DAG-based workflow definition with YAML/JSON
- Dependency resolution with parallel step execution
- Jinja2-templated parameter resolution
- Conditional step execution
- Cron-based scheduling
- Built-in action handlers
- Dapr workflow integration

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Start development server
python -m budpipeline.main
```

## API Endpoints

- `POST /api/v1/workflow/validate` - Validate a DAG definition
- `POST /api/v1/workflow/workflows` - Create a workflow
- `GET /api/v1/workflow/workflows` - List workflows
- `POST /api/v1/workflow/executions` - Start workflow execution
- `GET /api/v1/workflow/executions/{id}` - Get execution details

## DAG Format

```yaml
name: my-workflow
version: "1.0.0"
parameters:
  - name: input_value
    type: string
    required: true
steps:
  - id: step1
    name: First Step
    action: log
    params:
      message: "{{ params.input_value }}"
  - id: step2
    name: Second Step
    action: transform
    depends_on: [step1]
    params:
      input: "{{ steps.step1.outputs.message }}"
outputs:
  result: "{{ steps.step2.outputs.result }}"
```

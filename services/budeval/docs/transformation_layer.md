# Evaluation Engine Transformation Layer

## Overview

The transformation layer provides a uniform interface for converting generic evaluation requests into engine-specific formats. This design allows BudEval to support multiple evaluation engines (OpenCompass, DeepEval, etc.) while maintaining a consistent API.

## Architecture

### Core Components

1. **Generic Schemas** (`budeval/core/schemas.py`)
   - `GenericEvaluationRequest`: Engine-agnostic evaluation request
   - `GenericModelConfig`: Standard model configuration
   - `GenericDatasetConfig`: Standard dataset configuration
   - `GenericJobConfig`: Standard job configuration
   - `TransformedEvaluationData`: Output of transformation

2. **Base Transformer** (`budeval/core/transformers/base.py`)
   - Abstract base class defining the transformation interface
   - Methods for config generation, command building, validation
   - Default implementations for common functionality

3. **Engine-Specific Transformers**
   - `OpenCompassTransformer`: Transforms to OpenCompass format
   - `DeepEvalTransformer`: Transforms to DeepEval format
   - Additional transformers can be added following the same pattern

4. **Transformer Registry** (`budeval/core/transformers/registry.py`)
   - Central registry for all transformers
   - Auto-registration on import
   - Factory pattern for transformer instantiation

## Data Flow

```
User Request (API)
    ↓
GenericEvaluationRequest
    ↓
TransformerRegistry.get_transformer(engine)
    ↓
Engine-Specific Transformer
    ↓
TransformedEvaluationData
    ↓
Kubernetes Job Deployment
```

## Adding a New Engine

To add support for a new evaluation engine:

### 1. Create the Transformer

```python
# budeval/core/transformers/myengine_transformer.py
from budeval.core.transformers.base import BaseTransformer
from budeval.core.schemas import EvaluationEngine

class MyEngineTransformer(BaseTransformer):
    def __init__(self):
        super().__init__(EvaluationEngine.MYENGINE)

    def generate_config_files(self, request):
        # Generate engine-specific configs
        return {"config.yaml": "..."}

    def build_command(self, request):
        # Build container command
        return ["python", "run.py"], ["--config", "config.yaml"]

    # Implement other required methods...
```

### 2. Register the Engine

Add to `budeval/core/schemas.py`:
```python
class EvaluationEngine(str, Enum):
    OPENCOMPASS = "opencompass"
    DEEPEVAL = "deepeval"
    MYENGINE = "myengine"  # Add your engine
```

### 3. Auto-Register the Transformer

Add to `budeval/core/transformers/registry.py`:
```python
try:
    from budeval.core.transformers.myengine_transformer import MyEngineTransformer
    TransformerRegistry.register(EvaluationEngine.MYENGINE, MyEngineTransformer)
except ImportError:
    logger.warning("Failed to import MyEngine transformer")
```

## Usage Example

```python
from budeval.core.schemas import (
    GenericEvaluationRequest,
    GenericModelConfig,
    GenericDatasetConfig,
    EvaluationEngine,
    ModelType,
)
from budeval.core.transformers.registry import TransformerRegistry

# Create a generic request
request = GenericEvaluationRequest(
    eval_request_id=uuid4(),
    engine=EvaluationEngine.OPENCOMPASS,
    model=GenericModelConfig(
        name="gpt-3.5-turbo",
        type=ModelType.API,
        api_key="...",
        base_url="https://api.openai.com/v1",
    ),
    datasets=[
        GenericDatasetConfig(name="mmlu", category="knowledge"),
        GenericDatasetConfig(name="gsm8k", category="math"),
    ],
)

# Get transformer and transform
transformer = TransformerRegistry.get_transformer(request.engine)
transformed = transformer.transform_request(request)

# Use transformed data for job deployment
print(transformed.job_config.image)  # Docker image
print(transformed.config_files)      # Config files for ConfigMap
```

## Benefits

1. **Separation of Concerns**: Core workflow logic is decoupled from engine specifics
2. **Extensibility**: New engines can be added without modifying core code
3. **Type Safety**: Pydantic models ensure data validation
4. **Consistency**: All engines follow the same transformation pattern
5. **Testability**: Each transformer can be tested independently

## Next Steps for Integration

To fully integrate the transformation layer:

1. Update `workflows.py` to use transformers instead of hardcoded logic
2. Modify `services.py` to accept engine parameter in evaluation requests
3. Refactor `configmap_manager.py` to use transformed config files
4. Update `ansible_orchestrator.py` to use generic job configs
5. Add tests for each transformer

This transformation layer provides the foundation for supporting multiple evaluation engines while maintaining a clean, extensible architecture.

"""Direct OpenCompass integration without abstraction layers."""

import json
from typing import Dict

from budeval.evals.schemas import EvaluationRequest


class OpenCompassHandler:
    """Handles OpenCompass evaluation configuration and execution."""

    @staticmethod
    def generate_config(request: EvaluationRequest) -> Dict[str, str]:
        """Generate OpenCompass configuration files.

        Returns:
            Dict mapping filename to content
        """
        config_files = {}

        # Generate model configuration
        model_config = f"""from opencompass.models import OpenAI

models = [
    dict(
        type=OpenAI,
        path='{request.model.name}',
        key='{request.model.api_key}',
        openai_api_base='{request.model.base_url}',
        max_out_len={request.model.max_out_len},
        max_seq_len={request.model.max_seq_len},
        batch_size={request.model.batch_size},
        query_per_second={request.model.query_per_second},
    ),
]
"""
        config_files["model_config.py"] = model_config

        # Generate metadata
        metadata = {
            "eval_request_id": str(request.eval_request_id),
            "experiment_id": str(request.experiment_id) if request.experiment_id else None,
            "model_name": request.model.name,
            "datasets": [d.name for d in request.datasets],
        }
        config_files["metadata.json"] = json.dumps(metadata, indent=2)

        return config_files

    @staticmethod
    def build_command(request: EvaluationRequest) -> str:
        """Build OpenCompass execution command.

        Returns:
            Shell command to execute OpenCompass
        """
        datasets_str = " ".join([d.name for d in request.datasets])
        debug_flag = " --debug" if request.debug else ""

        command = f"""#!/bin/bash
set -e

# Create a model config file that uses environment variables
mkdir -p /workspace/opencompass/configs/models
cat > /workspace/opencompass/configs/models/bud_model.py << 'EOF'
from opencompass.models import OpenAISDK
import os

models = [
    dict(
        type=OpenAISDK,
        abbr=os.environ.get('MODEL_NAME', 'model'),
        path=os.environ.get('MODEL_NAME', 'model'),
        key=os.environ.get('OPENAI_API_KEY'),
        openai_api_base=os.environ.get('OPENAI_API_BASE'),
        query_per_second={request.model.query_per_second},
        max_out_len={request.model.max_out_len},
        max_seq_len={request.model.max_seq_len},
        batch_size={request.model.batch_size}
    )
]
EOF

# Run OpenCompass evaluation
cd /workspace
python /workspace/run.py \\
    --models bud_model \\
    --datasets {datasets_str} \\
    --work-dir /workspace/outputs \\
    --max-num-workers {request.num_workers}{debug_flag}

echo "Evaluation completed successfully"
"""
        return command.strip()

    @staticmethod
    def get_environment_variables(request: EvaluationRequest) -> Dict[str, str]:
        """Get environment variables for OpenCompass container."""
        return {
            "TRANSFORMERS_CACHE": "/workspace/cache/transformers",
            "HF_HOME": "/workspace/cache/huggingface",
            "TORCH_HOME": "/workspace/cache/torch",
            "MODEL_NAME": request.model.name,
            "OPENAI_API_KEY": request.model.api_key,
            "OPENAI_API_BASE": request.model.base_url,
        }

    @staticmethod
    def get_resource_requirements() -> Dict[str, str]:
        """Get default resource requirements for OpenCompass containers."""
        return {"cpu_request": "1000m", "cpu_limit": "2000m", "memory_request": "2Gi", "memory_limit": "4Gi"}

# Convert the request to required format for opencompass to work
from budeval.commons.logging import logging
from budeval.evals.schema import EvaluationRequest


logger = logging.getLogger(__name__)


class OpencompassTransformer:
    def __init__(self):
        """Initialize the transformer."""
        pass

    def transform(self, request: EvaluationRequest) -> list:
        """Transform the request to required format for opencompass to work."""
        logger = logging.getLogger("::EVAL:: OpencompassTransformer")
        jobs = []
        task_type = "gen"

        def _coerce_bool_flag(value, default: bool = False) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "y", "on"}
            return default

        for eval_config in request.eval_configs:
            if eval_config.config_name == "task_type":
                mode_value = eval_config.config_value.get("mode")
                if isinstance(mode_value, list) and mode_value:
                    task_type = str(mode_value[0]).lower()
                elif isinstance(mode_value, str):
                    task_type = mode_value.lower()
                break

        supports_logprobs = _coerce_bool_flag(
            request.eval_model_info.extra_args.get("supports_logprobs"), default=True
        )
        # for each request.eval_datasets
        for dataset in request.eval_datasets:
            # Create a job for each dataset
            logger.debug(f"Dataset {dataset.dataset_id} - Run {dataset.run_id}")

            dataset_task_type = (dataset.task_type or task_type or "gen").lower()
            task_flag = f"--task {dataset_task_type}" if dataset_task_type != "gen" else ""
            request_logprobs = dataset_task_type == "ppl" and supports_logprobs

            if dataset_task_type == "ppl" and not supports_logprobs:
                logger.warning(
                    "Skipping logprobs request for PPL evaluation because the endpoint does not advertise support"
                )

            extra_body = "{'logprobs': True}" if request_logprobs else "None"

            script = f"""# Setup data symlink for datasets (if data directory exists in PVC)
echo "Setting up data access..."
if [ -d /workspace/shared/data ]; then
    rm -rf /workspace/data
    ln -sf /workspace/shared/data /workspace/data
    echo "Created symlink: /workspace/data -> /workspace/shared/data"
else
    echo "Warning: No /workspace/shared/data directory found"
fi

# Create output directory in shared storage
mkdir -p /workspace/shared/results/{request.eval_id}/opencompass-{dataset.run_id}
echo "Created output directory: /workspace/shared/results/{request.eval_id}/opencompass-{dataset.run_id}"

# Verify directory structure
echo "Directory structure:"
ls -la /workspace/ | head -10

# Create a model config file that uses environment variables
mkdir -p /workspace/opencompass/configs/models
cat > /workspace/opencompass/configs/models/bud_model.py << 'EOF'
from opencompass.models import OpenAISDK
import os

models = [
    dict(
        type=OpenAISDK,
        abbr='{request.eval_model_info.model_name}',
        path='{request.eval_model_info.model_name}',  # Actual model name for API
        key='{request.eval_model_info.api_key}',
        tokenizer_path='Qwen/Qwen3-4B-Instruct-2507',  # Custom tokenizer
        openai_api_base='{request.eval_model_info.endpoint}',
        query_per_second={int(request.eval_model_info.extra_args.get("query_per_second", "10"))},
        max_out_len={int(request.eval_model_info.extra_args.get("max_out_len", str(request.eval_model_info.extra_args.get("max_out_len") or 2048)))},
        max_seq_len={int(request.eval_model_info.extra_args.get("max_seq_len", "4096"))},
        extra_body={extra_body},
        mode='mid',
        batch_size=20
    )
]
EOF

# Change to workspace directory where OpenCompass is installed
cd /workspace

# Run OpenCompass evaluation with direct output to shared storage
python /workspace/run.py \\
    --models bud_model \\
    --datasets {dataset.dataset_id} \\
    --work-dir /workspace/shared/results/{request.eval_id}/opencompass-{dataset.run_id} \\
    {task_flag} --max-num-workers 8 --debug
"""

            logger.debug(f"Generated OpenCompass command: {script}")

            job = {
                "run_id": dataset.run_id,
                "dataset": dataset.dataset_id,
                "script": script.strip(),
                "output_path": f"/workspace/shared/results/{request.eval_id}/opencompass-{dataset.run_id}",
            }

            jobs.append(job)

        return jobs

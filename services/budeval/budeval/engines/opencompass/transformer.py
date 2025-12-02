# Convert the request to required format for opencompass to work
from budeval.commons.logging import logging
from budeval.evals.schema import EvalMode, EvaluationRequest


logger = logging.getLogger(__name__)


class OpencompassTransformer:
    def __init__(self):
        """Initialize the transformer."""
        pass

    def transform(self, request: EvaluationRequest) -> list:
        """Transform the request to required format for opencompass to work."""
        logger = logging.getLogger("::EVAL:: OpencompassTransformer")
        jobs = []
        # for each request.eval_datasets
        for dataset in request.eval_datasets:
            eval_mode = dataset.eval_mode or request.eval_mode
            ppl_enabled = eval_mode == EvalMode.PPL or bool(
                request.eval_model_info.extra_args.get("ppl", False)
            )
            log_probs_enabled = ppl_enabled or bool(
                request.eval_model_info.extra_args.get("log_probs")
                or request.eval_model_info.extra_args.get("logprobs")
            )
            output_dir = (
                f"/workspace/shared/results/{request.eval_id}/opencompass-"
                f"{eval_mode.value}-{dataset.run_id}"
            )
            mode_flag = "--ppl \\\n    " if eval_mode == EvalMode.PPL else ""

            # Create a job for each dataset
            logger.debug(f"Dataset {dataset.dataset_id} - Run {dataset.run_id}")

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
mkdir -p {output_dir}
echo "Created output directory: {output_dir}"

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
        mode='mid',
        batch_size=20,
        generation_kwargs={{
            "log_probs": {str(log_probs_enabled).lower()},
            "logprobs": {str(log_probs_enabled).lower()},
            "ppl": {str(ppl_enabled).lower()},
        }}
    )
]
EOF

# Change to workspace directory where OpenCompass is installed
cd /workspace

# Run OpenCompass evaluation with direct output to shared storage
python /workspace/run.py \\
    --models bud_model \\
    {mode_flag}--datasets {dataset.dataset_id} \\
    --work-dir {output_dir} \\
    --max-num-workers 8 --debug
"""

            logger.debug(f"Generated OpenCompass command: {script}")

            job = {
                "run_id": dataset.run_id,
                "eval_mode": eval_mode,
                "dataset": dataset.dataset_id,
                "script": script.strip(),
                "output_path": output_dir,
            }

            jobs.append(job)

        return jobs

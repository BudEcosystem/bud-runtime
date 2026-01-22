"""Model-related actions.

This module contains actions for model operations:
- model_add: Add a local model from HuggingFace, URL, or disk
- cloud_model_add: Add a cloud-hosted model (OpenAI, Anthropic, etc.)
- model_delete: Delete a model
- model_benchmark: Run benchmarks on a model

Actions are registered via entry points in pyproject.toml.
Imports here are for documentation and testing purposes.
"""

from budpipeline.actions.model.add import ModelAddAction, ModelAddExecutor
from budpipeline.actions.model.add_cloud import CloudModelAddAction, CloudModelAddExecutor
from budpipeline.actions.model.benchmark import ModelBenchmarkAction, ModelBenchmarkExecutor
from budpipeline.actions.model.delete import ModelDeleteAction, ModelDeleteExecutor

__all__ = [
    # Add Local Model
    "ModelAddAction",
    "ModelAddExecutor",
    # Add Cloud Model
    "CloudModelAddAction",
    "CloudModelAddExecutor",
    # Delete
    "ModelDeleteAction",
    "ModelDeleteExecutor",
    # Benchmark
    "ModelBenchmarkAction",
    "ModelBenchmarkExecutor",
]

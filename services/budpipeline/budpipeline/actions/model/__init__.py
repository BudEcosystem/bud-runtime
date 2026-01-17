"""Model-related actions.

This module contains actions for model operations:
- model_add: Add a model from HuggingFace
- model_delete: Delete a model
- model_benchmark: Run benchmarks on a model

Actions are registered via entry points in pyproject.toml.
Imports here are for documentation and testing purposes.
"""

from budpipeline.actions.model.add import ModelAddAction, ModelAddExecutor
from budpipeline.actions.model.benchmark import ModelBenchmarkAction, ModelBenchmarkExecutor
from budpipeline.actions.model.delete import ModelDeleteAction, ModelDeleteExecutor

__all__ = [
    # Add
    "ModelAddAction",
    "ModelAddExecutor",
    # Delete
    "ModelDeleteAction",
    "ModelDeleteExecutor",
    # Benchmark
    "ModelBenchmarkAction",
    "ModelBenchmarkExecutor",
]

"""Built-in control flow actions.

This module contains the built-in actions for control flow
and basic operations: log, delay, conditional, transform,
aggregate, set_output, and fail.

Actions are registered via entry points in pyproject.toml.
Imports here are for documentation and testing purposes.
"""

from budpipeline.actions.builtin.aggregate import AggregateAction, AggregateExecutor
from budpipeline.actions.builtin.conditional import ConditionalAction, ConditionalExecutor
from budpipeline.actions.builtin.delay import DelayAction, DelayExecutor
from budpipeline.actions.builtin.fail import FailAction, FailExecutor
from budpipeline.actions.builtin.log import LogAction, LogExecutor
from budpipeline.actions.builtin.set_output import SetOutputAction, SetOutputExecutor
from budpipeline.actions.builtin.transform import TransformAction, TransformExecutor

__all__ = [
    # Log
    "LogAction",
    "LogExecutor",
    # Delay
    "DelayAction",
    "DelayExecutor",
    # Conditional
    "ConditionalAction",
    "ConditionalExecutor",
    # Transform
    "TransformAction",
    "TransformExecutor",
    # Aggregate
    "AggregateAction",
    "AggregateExecutor",
    # Set Output
    "SetOutputAction",
    "SetOutputExecutor",
    # Fail
    "FailAction",
    "FailExecutor",
]

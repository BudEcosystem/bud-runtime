"""Registry for managing evaluation engine transformers."""

from __future__ import annotations

from budmicroframe.commons import logging

from budeval.core.schemas import EvaluationEngine
from budeval.core.transformers.base import BaseTransformer


logger = logging.get_logger(__name__)


class TransformerRegistry:
    """Registry for managing engine-specific transformers."""

    _transformers: dict[EvaluationEngine, type[BaseTransformer]] = {}
    _instances: dict[EvaluationEngine, BaseTransformer] = {}

    @classmethod
    def register(cls, engine: EvaluationEngine, transformer_class: type[BaseTransformer]) -> None:
        """Register a transformer for a specific engine.

        Args:
            engine: The evaluation engine
            transformer_class: The transformer class to register
        """
        if engine in cls._transformers:
            logger.warning(f"Overwriting existing transformer for engine: {engine.value}")

        cls._transformers[engine] = transformer_class
        logger.info(f"Registered transformer for engine: {engine.value}")

    @classmethod
    def get_transformer(cls, engine: EvaluationEngine) -> BaseTransformer:
        """Get a transformer instance for a specific engine.

        Args:
            engine: The evaluation engine

        Returns:
            Transformer instance

        Raises:
            ValueError: If no transformer is registered for the engine
        """
        if engine not in cls._transformers:
            raise ValueError(f"No transformer registered for engine: {engine.value}")

        # Use singleton pattern for transformer instances
        if engine not in cls._instances:
            cls._instances[engine] = cls._transformers[engine](engine)

        return cls._instances[engine]

    @classmethod
    def list_engines(cls) -> list[EvaluationEngine]:
        """List all registered engines.

        Returns:
            List of registered evaluation engines
        """
        return list(cls._transformers.keys())

    @classmethod
    def is_registered(cls, engine: EvaluationEngine) -> bool:
        """Check if a transformer is registered for an engine.

        Args:
            engine: The evaluation engine

        Returns:
            True if a transformer is registered, False otherwise
        """
        return engine in cls._transformers

    @classmethod
    def clear(cls) -> None:
        """Clear all registered transformers (mainly for testing)."""
        cls._transformers.clear()
        cls._instances.clear()


# Auto-register transformers when imported
def _auto_register_transformers():
    """Automatically register known transformers."""
    try:
        from budeval.core.transformers.opencompass_transformer import OpenCompassTransformer

        TransformerRegistry.register(EvaluationEngine.OPENCOMPASS, OpenCompassTransformer)
    except ImportError as e:
        logger.warning(f"Failed to import OpenCompass transformer: {e}")

    # Add more transformers here as they are implemented
    # try:
    #     from budeval.core.transformers.deepeval_transformer import DeepEvalTransformer
    #     TransformerRegistry.register(EvaluationEngine.DEEPEVAL, DeepEvalTransformer)
    # except ImportError as e:
    #     logger.warning(f"Failed to import DeepEval transformer: {e}")


# Run auto-registration when module is imported
_auto_register_transformers()

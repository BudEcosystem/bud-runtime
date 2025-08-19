"""Core engine registry functionality."""

from abc import abstractmethod
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable, Dict, Optional, Protocol, Type, runtime_checkable

from budeval.commons.logging import logging


logger = logging.getLogger(__name__)


@runtime_checkable
class EngineProtocol(Protocol):
    """Protocol defining the interface that all engines must implement."""

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the engine."""
        pass

    @abstractmethod
    def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the engine's main functionality."""
        pass


@dataclass
class EngineMetadata:
    """Metadata information for an engine."""

    name: str
    version: str
    description: str
    author: str
    docker_image_url: str  # URL to the Docker image for this engine
    tags: Optional[list[str]] = field(default_factory=list)
    config_schema: Optional[Dict[str, Any]] = None
    dependencies: Optional[list[str]] = field(default_factory=list)
    capabilities: Optional[list[str]] = field(default_factory=list)


class EngineRegistry:
    """Registry for managing engines and their metadata."""

    _engines: Dict[str, Type[EngineProtocol]] = {}
    _metadata: Dict[str, EngineMetadata] = {}

    @classmethod
    def register(cls, metadata: EngineMetadata) -> Callable:
        """Register an engine with its metadata."""

        def decorator(engine_class: Type[EngineProtocol]) -> Type[EngineProtocol]:
            if not issubclass(engine_class, EngineProtocol):
                raise TypeError(f"{engine_class.__name__} does not implement EngineProtocol")

            engine_name = metadata.name.lower()
            if engine_name in cls._engines:
                logger.warning(f"Engine {engine_name} is already registered. Overwriting...")

            cls._engines[engine_name] = engine_class
            cls._metadata[engine_name] = metadata
            logger.info(f"Registered engine: {engine_name} (version: {metadata.version})")
            return engine_class

        return decorator

    @classmethod
    @lru_cache(maxsize=128)
    def get_engine(cls, name: str) -> Type[EngineProtocol]:
        """Get an engine class by name."""
        engine_name = name.lower()
        if engine_name not in cls._engines:
            raise KeyError(f"Engine {engine_name} not found in registry")
        return cls._engines[engine_name]

    @classmethod
    def get_metadata(cls, name: str) -> EngineMetadata:
        """Get metadata for an engine by name."""
        engine_name = name.lower()
        if engine_name not in cls._metadata:
            raise KeyError(f"Metadata for engine {engine_name} not found")
        return cls._metadata[engine_name]

    @classmethod
    def list_engines(cls) -> Dict[str, EngineMetadata]:
        """List all registered engines and their metadata."""
        return cls._metadata.copy()

    @classmethod
    def get_engines_by_tag(cls, tag: str) -> Dict[str, EngineMetadata]:
        """Get all engines that have a specific tag."""
        return {
            name: metadata
            for name, metadata in cls._metadata.items()
            if metadata.tags is not None and tag in metadata.tags
        }

    @classmethod
    def get_engines_by_capability(cls, capability: str) -> Dict[str, EngineMetadata]:
        """Get all engines that have a specific capability."""
        return {
            name: metadata
            for name, metadata in cls._metadata.items()
            if metadata.capabilities is not None and capability in metadata.capabilities
        }

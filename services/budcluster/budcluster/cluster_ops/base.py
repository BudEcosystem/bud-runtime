from abc import ABC, abstractmethod
from uuid import UUID


class BaseClusterHandler(ABC):
    """Base class for cluster handlers."""

    @abstractmethod
    def initial_setup(self, cluster_id: UUID) -> None:
        """Execute initial setup."""
        raise NotImplementedError

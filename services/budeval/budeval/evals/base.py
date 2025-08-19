from abc import ABC, abstractmethod
from uuid import UUID


class BaseClusterHandler(ABC):
    """Base class for cluster handlers."""

    @abstractmethod
    def verify_cluster_connection(self, cluster_id: UUID) -> None:
        """Verify cluster connection."""
        raise NotImplementedError

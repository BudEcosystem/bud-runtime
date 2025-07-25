from abc import ABC, abstractmethod


class BaseSeeder(ABC):
    """Base seeder class."""

    @abstractmethod
    async def seed(self) -> None:
        """Seed the database."""
        pass

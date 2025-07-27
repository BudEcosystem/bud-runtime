from abc import ABC, abstractmethod
from typing import Optional


class BaseModelInfo(ABC):
    @classmethod
    @abstractmethod
    def from_pretrained(cls, pretrained_model_name_or_path: str, token: Optional[str] = None) -> dict:
        """Load model information from pretrained model path or name."""
        pass

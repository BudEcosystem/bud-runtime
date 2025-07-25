import math
import random
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, model_validator


class BaseEngineCompatibility(ABC):
    """Base class for all engine compatibility checks."""

    @abstractmethod
    def check_args_compatibility(self, engine_args: Dict[str, Any]) -> bool:
        """Check if the engine is compatible with the given device."""
        pass

    @abstractmethod
    def check_model_compatibility(self, model: str) -> bool:
        """Check if the model is compatible with the engine."""
        pass

    @abstractmethod
    def check_device_compatibility(self, device: str) -> Optional[str]:
        """Check if the device is compatible with the engine."""
        pass


class BaseEngineArgs(BaseModel):
    """Base class for all engine arguments."""

    @model_validator(mode="before")
    @classmethod
    def root_validator(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Root validator for the engine arguments."""
        return {
            field_info.alias or field_name: values[field_name]
            for field_name, field_info in cls.model_fields.items()
            if field_name in values
        }

    @staticmethod
    def get_tensor_parallel_size(value: Optional[int] = None, min_val: int = 1, max_val: int = 1) -> int:
        """Retrieve the tensor parallel size.

        This method returns a random integer between the minimum and maximum
        values for the tensor parallel size. If a value is provided, it will
        add or subtract a random value to use as mutation in genetic algorithms.

        Args:
            value (int, optional): The initial value for mutation. Defaults to None.

        Returns:
            int: A random integer which is a factor of 2 between 1 and 8.
        """
        if max_val < min_val:
            raise ValueError("max_val must be greater than min_val")

        if (max_val & (max_val - 1)) != 0:
            max_val = 2 ** (max_val.bit_length() - 1)
        max_val = int(math.log2(max_val))
        min_val = int(math.log2(min_val))

        if value is not None:
            mutation = random.choice([-1, 1]) * 2
            x = int(math.log2(value))
            mutated_value = min(max_val, max(min_val, x + mutation))
            return int(2**mutated_value)
        return int(2 ** random.randint(min_val, max_val))

    def _get_properties(self, properties_to_skip: Optional[List[str]] = None) -> Dict[str, Any]:
        """Dynamically creates a map of property names and their corresponding random generator functions from the default_factory."""
        properties_to_skip = properties_to_skip or []
        return {
            field_name: getattr(self, f"get_{field_name}") or getattr(self, field_name)
            for field_name, field_info in self.model_fields.items()
            if field_name not in properties_to_skip
        }

    def get_args_and_envs(self) -> Dict[str, Dict[str, Any]]:
        """Retrieve the arguments and environment variables.

        This method constructs a dictionary containing the arguments and environment variables
        associated with the model fields. It categorizes them into 'args' and 'envs' based on
        their aliases. If an alias starts with 'args_', it is added to the 'args' dictionary,
        and if it starts with 'env_', it is added to the 'envs' dictionary. If no alias is present,
        the field name is converted to kebab-case and added to the 'args' dictionary.

        Returns:
            Dict[str, Dict[str, Any]]: A dictionary containing 'args' and 'envs' with their respective values.
        """
        args_and_envs: Dict[str, Dict[str, Any]] = {"args": {}, "envs": {}}

        for field_name, field_info in self.model_fields.items():
            value = getattr(self, field_name)
            if field_info.alias is not None and field_info.alias.startswith("args_"):
                args_and_envs["args"][field_info.alias.replace("args_", "")] = value
            elif field_info.alias is not None and field_info.alias.startswith("env_"):
                args_and_envs["envs"][field_info.alias.replace("env_", "")] = value
            else:
                args_and_envs["args"][field_name.replace("_", "-")] = value

        return args_and_envs

"""Engine registry package."""

# Import all engines to ensure they are registered
from . import opencompass  # noqa: F401


__all__ = ["opencompass"]

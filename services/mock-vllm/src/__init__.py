"""Mock vLLM service for integration testing."""

from .api_server import app
from .mock_responses import MockResponseGenerator
from .protocol import *

__version__ = "0.1.0"
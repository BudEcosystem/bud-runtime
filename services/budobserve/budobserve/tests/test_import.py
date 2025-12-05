"""Basic import tests for BudObserve SDK.

These tests verify that the package structure is correct and all
modules can be imported without errors.
"""

from __future__ import annotations


def test_import_budobserve() -> None:
    """Test that budobserve package can be imported."""
    import budobserve

    assert budobserve is not None


def test_import_version() -> None:
    """Test that version is accessible."""
    from budobserve import __version__

    assert __version__ is not None
    assert isinstance(__version__, str)
    assert __version__ == "0.1.0"


def test_import_types() -> None:
    """Test that types module can be imported."""
    from budobserve.types import Attributes, AttributeValue, JsonValue

    # Verify types are accessible
    assert AttributeValue is not None
    assert Attributes is not None
    assert JsonValue is not None


def test_import_internal_main() -> None:
    """Test that internal main module can be imported."""
    from budobserve._internal.main import BudObserve, get_budobserve

    assert BudObserve is not None
    assert get_budobserve is not None


def test_import_internal_config() -> None:
    """Test that internal config module can be imported."""
    from budobserve._internal.config import BudObserveConfig, get_default_config

    assert BudObserveConfig is not None
    assert get_default_config is not None


def test_import_internal_providers() -> None:
    """Test that internal provider modules can be imported."""
    from budobserve._internal.logger import ProxyLoggerProvider
    from budobserve._internal.meter import ProxyMeterProvider
    from budobserve._internal.tracer import ProxyTracerProvider

    assert ProxyTracerProvider is not None
    assert ProxyMeterProvider is not None
    assert ProxyLoggerProvider is not None


def test_import_internal_span() -> None:
    """Test that internal span module can be imported."""
    from budobserve._internal.span import BudSpan

    assert BudSpan is not None


def test_import_internal_constants() -> None:
    """Test that internal constants module can be imported."""
    from budobserve._internal import constants

    assert constants.SERVICE_NAME == "service.name"
    assert constants.BUD_PROJECT_ID == "bud.project.id"
    assert constants.GEN_AI_SYSTEM == "gen_ai.system"


def test_budobserve_singleton() -> None:
    """Test that BudObserve follows singleton pattern."""
    from budobserve._internal.main import BudObserve

    instance1 = BudObserve()
    instance2 = BudObserve()

    assert instance1 is instance2


def test_budobserve_config_default() -> None:
    """Test that default configuration is created correctly."""
    from budobserve._internal.config import BudObserveConfig

    config = BudObserveConfig()

    assert config.service_name == "unknown-service"
    assert config.service_version == "0.0.0"
    assert config.environment == "development"
    assert config.otlp_endpoint is None
    assert config.budmetrics_endpoint is None
    assert config.enable_console_exporter is False
    assert config.scrub_patterns == []

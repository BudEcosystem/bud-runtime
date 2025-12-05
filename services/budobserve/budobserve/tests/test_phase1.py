"""Comprehensive tests for Phase 1 - Core OTEL Wrapper & Initialization Layer.

Tests cover:
- ProxyTracerProvider and ProxyTracer
- ProxyMeterProvider and ProxyMeter
- ProxyLoggerProvider and ProxyLogger
- BudObserveConfig with environment variables
- BudObserve main class and global instance
"""

from __future__ import annotations

import os
from threading import Thread
from unittest.mock import patch

from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.trace import NoOpTracer, Span, SpanKind

from budobserve._internal.config import (
    GLOBAL_CONFIG,
    BudObserveConfig,
    _get_env,
    _get_env_bool,
    _get_env_float,
    get_default_config,
)
from budobserve._internal.logger import (
    NoOpLoggerProvider,
    ProxyLogger,
    ProxyLoggerProvider,
    SuppressedLogger,
)
from budobserve._internal.main import BudObserve, get_default_instance
from budobserve._internal.meter import (
    NoOpMeterProvider,
    ProxyMeter,
    ProxyMeterProvider,
    SuppressedMeter,
)
from budobserve._internal.tracer import (
    NoOpTracerProvider,
    ProxyTracer,
    ProxyTracerProvider,
    SuppressedTracer,
)

# =============================================================================
# ProxyTracerProvider Tests
# =============================================================================


class TestProxyTracerProvider:
    """Tests for ProxyTracerProvider."""

    def test_initialization_with_noop_provider(self) -> None:
        """Test that proxy starts with NoOpTracerProvider."""
        proxy = ProxyTracerProvider()
        assert isinstance(proxy.provider, NoOpTracerProvider)
        assert not proxy.is_configured

    def test_get_tracer_returns_proxy_tracer(self) -> None:
        """Test that get_tracer returns a ProxyTracer."""
        proxy = ProxyTracerProvider()
        tracer = proxy.get_tracer("test-module")
        assert isinstance(tracer, ProxyTracer)
        assert tracer.instrumenting_module_name == "test-module"

    def test_get_tracer_with_version_and_schema(self) -> None:
        """Test get_tracer with all parameters."""
        proxy = ProxyTracerProvider()
        tracer = proxy.get_tracer(
            instrumenting_module_name="test-module",
            instrumenting_library_version="1.0.0",
            schema_url="https://example.com/schema",
        )
        assert isinstance(tracer, ProxyTracer)

    def test_set_provider_updates_existing_tracers(self) -> None:
        """Test that setting provider updates all existing tracers."""
        proxy = ProxyTracerProvider()
        tracer = proxy.get_tracer("test-module")

        # Initially, should be NoOp
        assert isinstance(tracer._tracer, NoOpTracer)

        # Set a real provider
        sdk_provider = SDKTracerProvider()
        proxy.set_provider(sdk_provider)

        # Now provider should be updated
        assert proxy.is_configured
        assert proxy.provider is sdk_provider

    def test_suppress_scopes(self) -> None:
        """Test scope suppression."""
        proxy = ProxyTracerProvider()
        proxy.get_tracer("suppressed-scope")

        # Suppress the scope
        proxy.suppress_scopes("suppressed-scope")

        # New tracer for suppressed scope should be suppressed
        tracer2 = proxy.get_tracer("suppressed-scope")
        assert isinstance(tracer2._tracer, SuppressedTracer)

    def test_is_span_tracer_flag(self) -> None:
        """Test is_span_tracer flag on tracers."""
        proxy = ProxyTracerProvider()
        span_tracer = proxy.get_tracer("test", is_span_tracer=True)
        log_tracer = proxy.get_tracer("test", is_span_tracer=False)

        assert span_tracer.is_span_tracer is True
        assert log_tracer.is_span_tracer is False

    def test_force_flush(self) -> None:
        """Test force_flush returns True for NoOp provider."""
        proxy = ProxyTracerProvider()
        assert proxy.force_flush() is True

    def test_shutdown(self) -> None:
        """Test shutdown doesn't raise."""
        proxy = ProxyTracerProvider()
        proxy.shutdown()  # Should not raise


class TestProxyTracer:
    """Tests for ProxyTracer."""

    def test_start_span(self) -> None:
        """Test that start_span delegates to underlying tracer."""
        proxy_provider = ProxyTracerProvider()
        tracer = proxy_provider.get_tracer("test-module")

        span = tracer.start_span("test-span")
        assert isinstance(span, Span)

    def test_start_as_current_span(self) -> None:
        """Test start_as_current_span context manager."""
        proxy_provider = ProxyTracerProvider()
        tracer = proxy_provider.get_tracer("test-module")

        with tracer.start_as_current_span("test-span") as span:
            assert isinstance(span, Span)

    def test_start_span_with_attributes(self) -> None:
        """Test start_span with attributes."""
        proxy_provider = ProxyTracerProvider()
        tracer = proxy_provider.get_tracer("test-module")

        span = tracer.start_span(
            "test-span",
            kind=SpanKind.CLIENT,
            attributes={"key": "value"},
        )
        assert isinstance(span, Span)


# =============================================================================
# ProxyMeterProvider Tests
# =============================================================================


class TestProxyMeterProvider:
    """Tests for ProxyMeterProvider."""

    def test_initialization_with_noop_provider(self) -> None:
        """Test that proxy starts with NoOpMeterProvider."""
        proxy = ProxyMeterProvider()
        assert isinstance(proxy.provider, NoOpMeterProvider)
        assert not proxy.is_configured

    def test_get_meter_returns_proxy_meter(self) -> None:
        """Test that get_meter returns a ProxyMeter."""
        proxy = ProxyMeterProvider()
        meter = proxy.get_meter("test-module")
        assert isinstance(meter, ProxyMeter)
        assert meter.name == "test-module"

    def test_suppress_scopes(self) -> None:
        """Test scope suppression."""
        proxy = ProxyMeterProvider()

        # Suppress the scope
        proxy.suppress_scopes("suppressed-scope")

        # New meter for suppressed scope should be suppressed
        meter = proxy.get_meter("suppressed-scope")
        assert isinstance(meter._meter, SuppressedMeter)

    def test_force_flush(self) -> None:
        """Test force_flush returns True for NoOp provider."""
        proxy = ProxyMeterProvider()
        assert proxy.force_flush() is True

    def test_shutdown(self) -> None:
        """Test shutdown doesn't raise."""
        proxy = ProxyMeterProvider()
        proxy.shutdown()  # Should not raise


class TestProxyMeter:
    """Tests for ProxyMeter."""

    def test_create_counter(self) -> None:
        """Test creating a counter instrument."""
        proxy_provider = ProxyMeterProvider()
        meter = proxy_provider.get_meter("test-module")

        counter = meter.create_counter("test_counter", unit="1", description="Test")
        assert counter is not None

    def test_create_histogram(self) -> None:
        """Test creating a histogram instrument."""
        proxy_provider = ProxyMeterProvider()
        meter = proxy_provider.get_meter("test-module")

        histogram = meter.create_histogram("test_histogram")
        assert histogram is not None

    def test_create_up_down_counter(self) -> None:
        """Test creating an up-down counter instrument."""
        proxy_provider = ProxyMeterProvider()
        meter = proxy_provider.get_meter("test-module")

        counter = meter.create_up_down_counter("test_updown")
        assert counter is not None

    def test_create_gauge(self) -> None:
        """Test creating a gauge instrument."""
        proxy_provider = ProxyMeterProvider()
        meter = proxy_provider.get_meter("test-module")

        gauge = meter.create_gauge("test_gauge")
        assert gauge is not None


# =============================================================================
# ProxyLoggerProvider Tests
# =============================================================================


class TestProxyLoggerProvider:
    """Tests for ProxyLoggerProvider."""

    def test_initialization_with_noop_provider(self) -> None:
        """Test that proxy starts with NoOpLoggerProvider."""
        proxy = ProxyLoggerProvider()
        assert isinstance(proxy.provider, NoOpLoggerProvider)
        assert not proxy.is_configured

    def test_get_logger_returns_proxy_logger(self) -> None:
        """Test that get_logger returns a ProxyLogger."""
        proxy = ProxyLoggerProvider()
        logger = proxy.get_logger("test-module")
        assert isinstance(logger, ProxyLogger)
        assert logger.name == "test-module"

    def test_suppress_scopes(self) -> None:
        """Test scope suppression."""
        proxy = ProxyLoggerProvider()

        # Suppress the scope
        proxy.suppress_scopes("suppressed-scope")

        # New logger for suppressed scope should be suppressed
        logger = proxy.get_logger("suppressed-scope")
        assert isinstance(logger._logger, SuppressedLogger)

    def test_min_level_property(self) -> None:
        """Test min_level property."""
        import logging

        proxy = ProxyLoggerProvider(min_level=logging.WARNING)
        assert proxy.min_level == logging.WARNING

        proxy.min_level = logging.ERROR
        assert proxy.min_level == logging.ERROR

    def test_force_flush(self) -> None:
        """Test force_flush returns True for NoOp provider."""
        proxy = ProxyLoggerProvider()
        assert proxy.force_flush() is True


# =============================================================================
# BudObserveConfig Tests
# =============================================================================


class TestBudObserveConfig:
    """Tests for BudObserveConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = BudObserveConfig()

        assert config.service_name == "unknown-service"
        assert config.service_version is None
        assert config.environment is None
        assert config.otlp_endpoint is None
        assert config.budmetrics_endpoint is None
        assert config.console_enabled is False
        assert config.console_colors == "auto"
        assert config.sample_rate == 1.0
        assert config.scrub_patterns == []
        assert config.is_initialized is False

    def test_from_environment(self) -> None:
        """Test configuration from environment variables."""
        with patch.dict(
            os.environ,
            {
                "BUDOBSERVE_SERVICE_NAME": "test-service",
                "BUDOBSERVE_SERVICE_VERSION": "1.0.0",
                "BUDOBSERVE_ENVIRONMENT": "production",
                "BUDOBSERVE_OTLP_ENDPOINT": "http://localhost:4317",
                "BUDOBSERVE_CONSOLE": "true",
                "BUDOBSERVE_SAMPLE_RATE": "0.5",
            },
            clear=False,
        ):
            config = BudObserveConfig.from_environment()

            assert config.service_name == "test-service"
            assert config.service_version == "1.0.0"
            assert config.environment == "production"
            assert config.otlp_endpoint == "http://localhost:4317"
            assert config.console_enabled is True
            assert config.sample_rate == 0.5

    def test_from_environment_otel_fallback(self) -> None:
        """Test that OTEL env vars are used as fallback."""
        with patch.dict(
            os.environ,
            {
                "OTEL_SERVICE_NAME": "otel-service",
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://otel:4317",
            },
            clear=False,
        ):
            # Clear BUDOBSERVE vars if they exist
            env = os.environ.copy()
            for key in list(env.keys()):
                if key.startswith("BUDOBSERVE_"):
                    del os.environ[key]

            config = BudObserveConfig.from_environment()

            assert config.service_name == "otel-service"
            assert config.otlp_endpoint == "http://otel:4317"

    def test_merge_with(self) -> None:
        """Test merging configuration with explicit values."""
        base_config = BudObserveConfig(
            service_name="base-service",
            service_version="1.0.0",
            environment="dev",
        )

        merged = base_config.merge_with(
            service_name="new-service",
            environment="prod",
        )

        assert merged.service_name == "new-service"
        assert merged.service_version == "1.0.0"  # Unchanged
        assert merged.environment == "prod"

    def test_create_resource(self) -> None:
        """Test creating OTEL resource from config."""
        config = BudObserveConfig(
            service_name="test-service",
            service_version="1.0.0",
            environment="production",
        )

        resource = config.create_resource()
        attrs = dict(resource.attributes)

        assert attrs["service.name"] == "test-service"
        assert attrs["service.version"] == "1.0.0"
        assert attrs["deployment.environment.name"] == "production"
        assert attrs["telemetry.sdk.name"] == "budobserve"
        assert "process.pid" in attrs

    def test_configure_marks_initialized(self) -> None:
        """Test that configure marks config as initialized."""
        config = BudObserveConfig()
        assert config.is_initialized is False

        config.configure(service_name="test-service")
        assert config.is_initialized is True


class TestEnvHelpers:
    """Tests for environment variable helper functions."""

    def test_get_env_first_match(self) -> None:
        """Test _get_env returns first matching value."""
        with patch.dict(os.environ, {"VAR1": "value1", "VAR2": "value2"}):
            result = _get_env("VAR1", "VAR2")
            assert result == "value1"

    def test_get_env_fallback(self) -> None:
        """Test _get_env returns second if first not set."""
        with patch.dict(os.environ, {"VAR2": "value2"}, clear=False):
            os.environ.pop("VAR1", None)
            result = _get_env("VAR1", "VAR2")
            assert result == "value2"

    def test_get_env_default(self) -> None:
        """Test _get_env returns default if none set."""
        os.environ.pop("VAR1", None)
        os.environ.pop("VAR2", None)
        result = _get_env("VAR1", "VAR2", default="default")
        assert result == "default"

    def test_get_env_bool_true(self) -> None:
        """Test _get_env_bool with true values."""
        for val in ["true", "TRUE", "1", "yes", "YES"]:
            with patch.dict(os.environ, {"TEST": val}):
                assert _get_env_bool("TEST") is True

    def test_get_env_bool_false(self) -> None:
        """Test _get_env_bool with false values."""
        for val in ["false", "FALSE", "0", "no"]:
            with patch.dict(os.environ, {"TEST": val}):
                assert _get_env_bool("TEST") is False

    def test_get_env_float(self) -> None:
        """Test _get_env_float parsing."""
        with patch.dict(os.environ, {"TEST": "0.75"}):
            assert _get_env_float("TEST") == 0.75

    def test_get_env_float_invalid(self) -> None:
        """Test _get_env_float with invalid value returns default."""
        with patch.dict(os.environ, {"TEST": "invalid"}):
            assert _get_env_float("TEST", default=1.0) == 1.0


# =============================================================================
# BudObserve Main Class Tests
# =============================================================================


class TestBudObserve:
    """Tests for BudObserve main class."""

    def test_initialization(self) -> None:
        """Test BudObserve initialization."""
        instance = BudObserve()
        assert instance.config is not None
        assert instance.is_configured is False

    def test_initialization_with_config(self) -> None:
        """Test BudObserve initialization with custom config."""
        config = BudObserveConfig(service_name="custom-service")
        instance = BudObserve(config=config)
        assert instance.config.service_name == "custom-service"

    def test_tracer_provider_lazy_init(self) -> None:
        """Test that tracer_provider is lazily initialized via config."""
        config = BudObserveConfig()
        assert config._tracer_provider is None

        # Access triggers creation
        provider = config.tracer_provider
        assert isinstance(provider, ProxyTracerProvider)

        # BudObserve delegates to config
        instance = BudObserve(config=config)
        assert instance.tracer_provider is provider

    def test_meter_provider_lazy_init(self) -> None:
        """Test that meter_provider is lazily initialized via config."""
        config = BudObserveConfig()
        assert config._meter_provider is None

        # Access triggers creation
        provider = config.meter_provider
        assert isinstance(provider, ProxyMeterProvider)

        # BudObserve delegates to config
        instance = BudObserve(config=config)
        assert instance.meter_provider is provider

    def test_logger_provider_lazy_init(self) -> None:
        """Test that logger_provider is lazily initialized via config."""
        config = BudObserveConfig()
        assert config._logger_provider is None

        # Access triggers creation
        provider = config.logger_provider
        assert isinstance(provider, ProxyLoggerProvider)

        # BudObserve delegates to config
        instance = BudObserve(config=config)
        assert instance.logger_provider is provider

    def test_config_configure_updates_settings(self) -> None:
        """Test that config.configure updates configuration settings."""
        config = BudObserveConfig()
        config.configure(
            service_name="configured-service",
            environment="production",
            console_enabled=True,
        )

        assert config.service_name == "configured-service"
        assert config.environment == "production"
        assert config.console_enabled is True
        assert config.is_initialized is True

    def test_budobserve_reflects_config_state(self) -> None:
        """Test that BudObserve reflects config's initialized state."""
        config = BudObserveConfig()
        instance = BudObserve(config=config)

        assert instance.is_configured is False

        config.configure(service_name="test-service")
        assert instance.is_configured is True

    def test_shutdown(self) -> None:
        """Test shutdown doesn't raise."""
        instance = BudObserve()
        # Access providers to create them
        _ = instance.tracer_provider
        _ = instance.meter_provider
        _ = instance.logger_provider

        instance.shutdown()  # Should not raise

    def test_force_flush(self) -> None:
        """Test force_flush returns True."""
        instance = BudObserve()
        # Access providers to create them
        _ = instance.tracer_provider
        _ = instance.meter_provider
        _ = instance.logger_provider

        assert instance.force_flush() is True


class TestGlobalInstance:
    """Tests for global instance and module-level functions."""

    def test_get_default_instance_singleton(self) -> None:
        """Test that get_default_instance returns same instance."""
        instance1 = get_default_instance()
        instance2 = get_default_instance()
        assert instance1 is instance2

    def test_global_config_exists(self) -> None:
        """Test that GLOBAL_CONFIG is available."""
        assert GLOBAL_CONFIG is not None
        assert isinstance(GLOBAL_CONFIG, BudObserveConfig)

    def test_get_default_config(self) -> None:
        """Test get_default_config returns GLOBAL_CONFIG."""
        config = get_default_config()
        assert config is GLOBAL_CONFIG


# =============================================================================
# Thread Safety Tests
# =============================================================================


class TestThreadSafety:
    """Tests for thread safety of proxy providers."""

    def test_tracer_provider_concurrent_access(self) -> None:
        """Test concurrent tracer creation is thread-safe."""
        proxy = ProxyTracerProvider()
        tracers: list[ProxyTracer] = []
        errors: list[Exception] = []

        def get_tracer(name: str) -> None:
            try:
                tracer = proxy.get_tracer(name)
                tracers.append(tracer)
            except Exception as e:
                errors.append(e)

        threads = [Thread(target=get_tracer, args=(f"module-{i}",)) for i in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(tracers) == 10

    def test_meter_provider_concurrent_access(self) -> None:
        """Test concurrent meter creation is thread-safe."""
        proxy = ProxyMeterProvider()
        meters: list[ProxyMeter] = []
        errors: list[Exception] = []

        def get_meter(name: str) -> None:
            try:
                meter = proxy.get_meter(name)
                meters.append(meter)
            except Exception as e:
                errors.append(e)

        threads = [Thread(target=get_meter, args=(f"module-{i}",)) for i in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(meters) == 10


# =============================================================================
# Public API Tests
# =============================================================================


class TestPublicAPI:
    """Tests for public API exported from budobserve package."""

    def test_imports_from_package(self) -> None:
        """Test that all public symbols are importable."""
        from budobserve import (
            DEFAULT_INSTANCE,
            GLOBAL_CONFIG,
            BudObserve,
            BudObserveConfig,
            __version__,
            configure,
            get_default_instance,
        )

        assert __version__ is not None
        assert BudObserve is not None
        assert BudObserveConfig is not None
        assert configure is not None
        assert DEFAULT_INSTANCE is not None
        assert GLOBAL_CONFIG is not None
        assert get_default_instance is not None

    def test_default_instance_is_budobserve(self) -> None:
        """Test that DEFAULT_INSTANCE is a BudObserve."""
        from budobserve import DEFAULT_INSTANCE, BudObserve

        assert isinstance(DEFAULT_INSTANCE, BudObserve)

#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""OpenTelemetry configuration for Pydantic AI instrumentation."""

from typing import Optional

from budmicroframe.commons import logging
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic_ai import Agent

from budprompt.commons.config import app_settings


logger = logging.get_logger(__name__)


class OTelManager:
    """Singleton manager for OpenTelemetry instrumentation.

    Provides centralized configuration and lifecycle management for OpenTelemetry
    tracing with Pydantic AI agent instrumentation.

    Usage:
        from budprompt.shared.otel import otel_manager

        # In application lifespan
        otel_manager.configure()
        ...
        otel_manager.shutdown()
    """

    _instance: Optional["OTelManager"] = None
    _tracer_provider: Optional[TracerProvider] = None
    _is_configured: bool = False

    def __new__(cls) -> "OTelManager":
        """Ensure only one instance exists (Singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def is_enabled(self) -> bool:
        """Check if OpenTelemetry is enabled based on configuration."""
        return not app_settings.otel_sdk_disabled

    @property
    def is_configured(self) -> bool:
        """Check if OpenTelemetry has been configured."""
        return self._is_configured

    @property
    def tracer_provider(self) -> Optional[TracerProvider]:
        """Get the configured TracerProvider instance."""
        return self._tracer_provider

    def configure(self) -> None:
        """Configure OpenTelemetry for Pydantic AI agent instrumentation.

        Sets up the TracerProvider with OTLP HTTP exporter and instruments
        all Pydantic AI agents. Configuration is read from app_settings:
            - OTEL_SDK_DISABLED: Whether OTEL SDK is disabled
            - OTEL_EXPORTER_OTLP_ENDPOINT: OTLP HTTP endpoint
        """
        if self._is_configured:
            logger.warning("OpenTelemetry already configured, skipping")
            return

        if not self.is_enabled:
            logger.info("OpenTelemetry SDK is disabled")
            return

        endpoint = app_settings.otel_exporter_endpoint

        # Create resource with service name
        resource = Resource.create(
            {
                SERVICE_NAME: app_settings.name,
            }
        )

        # Create tracer provider
        self._tracer_provider = TracerProvider(resource=resource)

        # Configure OTLP exporter
        exporter = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")
        span_processor = BatchSpanProcessor(exporter)
        self._tracer_provider.add_span_processor(span_processor)

        # Set as global tracer provider
        trace.set_tracer_provider(self._tracer_provider)

        # Instrument all Pydantic AI agents
        Agent.instrument_all()

        self._is_configured = True
        logger.info(f"OpenTelemetry configured: service_name={app_settings.name}")

    def shutdown(self) -> None:
        """Gracefully shutdown OpenTelemetry.

        Flushes pending spans and releases resources.
        """
        if not self._is_configured:
            return

        if self._tracer_provider:
            self._tracer_provider.shutdown()
            self._tracer_provider = None

        self._is_configured = False
        logger.info("OpenTelemetry shutdown complete")


# Module-level singleton instance
otel_manager = OTelManager()

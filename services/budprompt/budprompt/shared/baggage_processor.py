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

"""BaggageSpanProcessor - copies W3C Baggage entries to span attributes.

This processor runs on every span start and copies specific baggage keys
(bud.project_id, bud.prompt_id, etc.) from the OTEL context to span attributes.
This enables filtering of real-time observability data by business attributes
since all spans in a trace will have these attributes.
"""

from typing import Optional

from opentelemetry import baggage, context
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor


# Keys that should be copied from baggage to span attributes
BAGGAGE_KEYS = [
    "bud.project_id",
    "bud.prompt_id",
    "bud.prompt_version_id",
    "bud.endpoint_id",
    "bud.model_id",
    "bud.api_key_id",
    "bud.api_key_project_id",
    "bud.user_id",
]


class BaggageSpanProcessor(SpanProcessor):
    """SpanProcessor that copies W3C Baggage entries to span attributes.

    This processor is registered FIRST in the TracerProvider so it runs
    before any other processors. It reads baggage from the OTEL context
    and copies the bud.* keys to span attributes.

    Usage:
        from budprompt.shared.baggage_processor import BaggageSpanProcessor

        tracer_provider = TracerProvider(...)
        tracer_provider.add_span_processor(BaggageSpanProcessor())
    """

    def on_start(self, span: Span, parent_context: Optional[context.Context] = None) -> None:
        """Copy baggage entries to span attributes when span starts.

        Args:
            span: The span that is starting
            parent_context: The parent context, or None to use current context
        """
        ctx = parent_context if parent_context is not None else context.get_current()
        for key in BAGGAGE_KEYS:
            value = baggage.get_baggage(key, context=ctx)
            if value:
                span.set_attribute(key, value)

    def on_end(self, span: ReadableSpan) -> None:
        """Process span on end. No action needed for this processor."""
        pass

    def shutdown(self) -> None:
        """Shut down the processor. No resources to release."""
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush any pending spans. No buffering, always returns True."""
        return True

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor, SpanProcessor

# spec §42's structured traces. Deliberately owns a private TracerProvider
# instance rather than going through opentelemetry.trace.set_tracer_provider
# / get_tracer_provider: the OTel API's global provider can only be set
# once per process (a second call is a silent no-op with a logged
# warning), which makes it awkward for tests to swap in an
# InMemorySpanExporter to assert on. Holding our own provider sidesteps
# that entirely — get_tracer() always goes through it directly.
#
# No real OTel collector is stood up here — there's nothing in this
# project's infra that a collector could be verified against in this
# environment (same reasoning as never having stood up a real Qdrant/etc.
# — see docs/design-decisions.md). Defaults to a ConsoleSpanExporter so
# spans are at least visible in process output; tests attach an
# InMemorySpanExporter via add_span_processor() instead (see
# tests/unit/test_telemetry.py).
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))


def get_tracer(name: str):
    return _provider.get_tracer(name)


def add_span_processor(processor: SpanProcessor) -> None:
    """Test-only hook to observe spans without touching the OTel global
    API's provider."""
    _provider.add_span_processor(processor)

from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from core.telemetry import add_span_processor, get_tracer


def test_get_tracer_produces_real_spans_with_attributes():
    """spec §42's structured traces. Attaches an InMemorySpanExporter
    (rather than asserting on the default ConsoleSpanExporter's stdout
    output) so the span's attributes can be inspected directly — this is
    also the pattern tools/registry.py and orchestration/graph.py's own
    tracing could be tested against, not just this module in isolation.
    """
    exporter = InMemorySpanExporter()
    add_span_processor(SimpleSpanProcessor(exporter))

    tracer = get_tracer("incidentlab.test")
    with tracer.start_as_current_span("unit-test-span") as span:
        span.set_attribute("incidentlab.example", "value")

    spans = exporter.get_finished_spans()
    matching = [s for s in spans if s.name == "unit-test-span"]
    assert len(matching) == 1
    assert matching[0].attributes["incidentlab.example"] == "value"
    assert matching[0].end_time is not None

"""OpenTelemetry setup for agent runs. Requires the 'agent' extra."""

from typing import Literal

TelemetryMode = Literal["off", "console", "otlp"]


def setup_telemetry(mode: TelemetryMode = "off") -> None:
    """Enable Strands tracing. "otlp" reads the standard OTEL_EXPORTER_OTLP_*
    environment variables; "console" prints spans to stdout."""
    if mode == "off":
        return
    from strands.telemetry import StrandsTelemetry

    telemetry = StrandsTelemetry()
    if mode == "console":
        telemetry.setup_console_exporter()
    elif mode == "otlp":
        telemetry.setup_otlp_exporter()

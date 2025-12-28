"""Distributed tracing with OpenTelemetry."""

from functools import wraps
from typing import Callable, Optional

import structlog

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False

from ..core.config import settings

logger = structlog.get_logger(__name__)


class TracingManager:
    """Manages OpenTelemetry tracing configuration."""

    def __init__(self):
        self.enabled = TRACING_AVAILABLE and settings.enable_metrics
        self.tracer: Optional[trace.Tracer] = None

        if self.enabled:
            self._setup_tracing()

    def _setup_tracing(self):
        """Setup OpenTelemetry tracing."""
        try:
            # Create resource with service information
            resource = Resource.create(
                {
                    "service.name": "tgstats-bot",
                    "service.version": "0.2.0",
                    "deployment.environment": settings.environment,
                }
            )

            # Create tracer provider
            provider = TracerProvider(resource=resource)

            # Add console exporter for development
            if settings.environment == "development":
                console_exporter = ConsoleSpanExporter()
                provider.add_span_processor(BatchSpanProcessor(console_exporter))

            # Add OTLP exporter if configured (for production)
            otlp_endpoint = getattr(settings, "otlp_endpoint", None)
            if otlp_endpoint:
                otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
                provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

            # Set global tracer provider
            trace.set_tracer_provider(provider)

            # Get tracer instance
            self.tracer = trace.get_tracer(__name__)

            logger.info("tracing_initialized", environment=settings.environment)

        except Exception as e:
            logger.error("tracing_setup_failed", error=str(e))
            self.enabled = False

    def instrument_fastapi(self, app):
        """Instrument FastAPI application."""
        if self.enabled and TRACING_AVAILABLE:
            try:
                FastAPIInstrumentor.instrument_app(app)
                logger.info("fastapi_instrumented")
            except Exception as e:
                logger.error("fastapi_instrumentation_failed", error=str(e))

    def instrument_sqlalchemy(self, engine):
        """Instrument SQLAlchemy engine."""
        if self.enabled and TRACING_AVAILABLE:
            try:
                SQLAlchemyInstrumentor().instrument(engine=engine)
                logger.info("sqlalchemy_instrumented")
            except Exception as e:
                logger.error("sqlalchemy_instrumentation_failed", error=str(e))

    def instrument_redis(self):
        """Instrument Redis client."""
        if self.enabled and TRACING_AVAILABLE:
            try:
                RedisInstrumentor().instrument()
                logger.info("redis_instrumented")
            except Exception as e:
                logger.error("redis_instrumentation_failed", error=str(e))


# Global tracing manager
tracing_manager = TracingManager()


def traced(span_name: Optional[str] = None):
    """
    Decorator for tracing function calls.

    Args:
        span_name: Custom span name (uses function name if not provided)

    Usage:
        @traced("process_message")
        async def process_message(message):
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not tracing_manager.enabled or not tracing_manager.tracer:
                return await func(*args, **kwargs)

            name = span_name or f"{func.__module__}.{func.__name__}"

            with tracing_manager.tracer.start_as_current_span(name) as span:
                # Add function attributes
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)

                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("function.status", "success")
                    return result
                except Exception as e:
                    span.set_attribute("function.status", "error")
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    span.record_exception(e)
                    raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not tracing_manager.enabled or not tracing_manager.tracer:
                return func(*args, **kwargs)

            name = span_name or f"{func.__module__}.{func.__name__}"

            with tracing_manager.tracer.start_as_current_span(name) as span:
                # Add function attributes
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)

                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("function.status", "success")
                    return result
                except Exception as e:
                    span.set_attribute("function.status", "error")
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    span.record_exception(e)
                    raise

        # Return appropriate wrapper based on function type
        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def get_current_span():
    """Get the current active span."""
    if tracing_manager.enabled and TRACING_AVAILABLE:
        return trace.get_current_span()
    return None


def add_span_attribute(key: str, value):
    """Add attribute to current span."""
    span = get_current_span()
    if span:
        span.set_attribute(key, value)

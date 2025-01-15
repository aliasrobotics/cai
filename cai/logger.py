"""
This module provides a logger for tracing inference
operations using OpenTelemetry.
"""

import contextvars
import json
import os
import sys
from functools import wraps
from openinference.instrumentation.openai import OpenAIInstrumentor  # pylint: disable=import-error  # noqa: E501

from opentelemetry import trace, context  # pylint: disable=import-error  # noqa: E501
from opentelemetry import trace as trace_api  # pylint: disable=import-error,reimported  # noqa: E501
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # pylint: disable=import-error  # noqa: E501
    OTLPSpanExporter)  # pylint: disable=import-error  # noqa: E501
from opentelemetry.sdk import trace as trace_sdk  # pylint: disable=import-error  # noqa: E501
from opentelemetry.sdk.resources import Resource  # pylint: disable=import-error  # noqa: E501
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # pylint: disable=import-error  # noqa: E501
from opentelemetry.trace import Status, StatusCode  # pylint: disable=import-error  # noqa: E501

from openinference.semconv.resource import ResourceAttributes  # pylint: disable=import-error,ungrouped-imports  # noqa: E501
from openinference.semconv.trace import SpanAttributes  # pylint: disable=import-error  # noqa: E501

# Instrument OpenAI if tracing is enabled
if os.getenv("CAI_TRACING", "true").lower() == "true":

    # Context variable to store the current span
    current_span = contextvars.ContextVar("current_span", default=None)
    # Add this at the top with other context vars
    current_agent_span = contextvars.ContextVar(
        "current_agent_span", default=None)

    # This will set project name based in the file stacking
    # inferences of a file in a project as per
    # https://docs.arize.com/phoenix/tracing/how-to-tracing/manual-instrumentation/custom-spans
    current_file = os.path.basename(sys.argv[0]).split(".")[0]
    project_name = f"{current_file}"
    # project_name = f"{sys.argv[1]}"
    resource = Resource(
        attributes={
            ResourceAttributes.PROJECT_NAME: project_name})
    tracer_provider = trace_sdk.TracerProvider(resource=resource)
    span_exporter = OTLPSpanExporter("http://11.0.0.1:6006/v1/traces")
    span_processor = SimpleSpanProcessor(span_exporter)
    tracer_provider.add_span_processor(span_processor)
    trace_api.set_tracer_provider(tracer_provider)

    OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)


class ExploitLogger:
    """A class for tracing inference operations using
    OpenTelemetry.

    This class provides decorators and methods to trace
    various aspects of inference operations, including
    individual inferences, chains of operations, function
    calls, and agent functions.

    Sets into the span attributes the following attributes:
        - inference.name
        - span kind
        - llm.model.name
        - status

    NOTE: see https://docs.arize.com/phoenix/tracing/concepts-tracing/what-are-traces  # noqa: E501
          for the general concept of traces and spans.
    """

    def __init__(self, tracing=True):
        self.tracer = trace.get_tracer(__name__)
        self.tracing = tracing  # if False, doesn't log anything
        self.active_agent_name = None

    def get_logger_url(self):
        """Get the current Phoenix logger's log URL."""
        # First try to get span from our context var
        span = current_span.get()

        # If no span in our context var, try getting current span from trace
        # API
        if span is None:
            span = trace.get_current_span()

        # If we still don't have a valid span, check agent span
        if span is None or not span.is_recording():
            span = current_agent_span.get()

        if span is None or not span.is_recording():
            return "No active span found."

        span_context = span.get_span_context()
        trace_id_hex = format(span_context.trace_id, "032x")

        return f"http://11.0.0.1:6006/projects/UHJvamVjdDo1/traces/{
            trace_id_hex}"

    def log_response(self, chain_element_name):
        """Decorator to log the response of a function call.

        Args:
            chain_element_name (str): The name of the chain element.

        Returns:
            Callable: The decorated function.
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.tracing:
                    return func(*args, **kwargs)

                parent_context = context.get_current()

                with self.tracer.start_as_current_span(
                    chain_element_name, context=parent_context
                ) as span:
                    current_span.set(span)
                    span.set_attribute(
                        SpanAttributes.OPENINFERENCE_SPAN_KIND, "CHAIN")
                    span.set_attribute("chain.name", chain_element_name)

                    try:
                        response = func(*args, **kwargs)

                        # Log output only if flow returned from
                        # the decorator
                        if response:
                            # Get last message if there are any messages
                            last_message = (response.messages[-1]
                                            if response.messages else None)

                            markdown_content = (
                                f"## Response Summary\n\n"
                                f"#### Last Message\n"
                                f"```json\n{
                                    json.dumps(
                                        last_message,
                                        indent=2)}\n```\n\n"
                                f"#### Agent\n"
                                f"Name: {
                                    response.agent.name if response.agent else 'No agent'}\n\n"  # noqa: E501  # pylint: disable=line-too-long
                                f"#### Context Variables\n"
                                f"```json\n{
                                    json.dumps(
                                        response.context_variables,
                                        indent=2)}\n```\n\n"
                                f"#### Execution Time\n"
                                f"{response.time:.2f} seconds\n"
                            )
                            span.set_attribute(
                                SpanAttributes.OUTPUT_VALUE, markdown_content
                            )
                            span.set_attribute(
                                SpanAttributes.OUTPUT_MIME_TYPE, "text/plain"
                            )

                        span.set_status(Status(StatusCode.OK))
                        return response
                    except Exception as e:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        raise
                    finally:
                        current_span.set(None)
            return wrapper
        return decorator

    def log_agent(self):
        """Decorator to log the agent.

        Args:
            agent (Agent): The agent to log.

        Returns:
            Callable: The decorated function.
        """
        def decorator(func):
            @wraps(func)
            def wrapper(cai, active_agent, *args, **kwargs):
                if not self.tracing:
                    return func(cai, active_agent, *args, **kwargs)

                if not active_agent:
                    return func(cai, active_agent, *args, **kwargs)

                # Check if we need a new span
                needs_new_span = (
                    not self.active_agent_name or
                    active_agent.name != self.active_agent_name
                )

                if needs_new_span:
                    agent_name = f"Agent: {active_agent.name}"
                    # Create new span
                    with self.tracer.start_as_current_span(
                        agent_name,
                        context=context.get_current()
                    ) as span:
                        self.active_agent_name = active_agent.name
                        current_span.set(span)
                        current_agent_span.set(span)
                        span.set_attribute(
                            SpanAttributes.OPENINFERENCE_SPAN_KIND, "CHAIN")
                        span.set_attribute("chain.name", active_agent.name)

                        try:
                            new_active_agent = func(
                                cai, active_agent, *args, **kwargs)
                            span.set_status(Status(StatusCode.OK))
                            return new_active_agent
                        except Exception as e:
                            span.set_status(Status(StatusCode.ERROR, str(e)))
                            raise
                        finally:
                            agent_changed = (
                                not new_active_agent or
                                new_active_agent.name != active_agent.name
                            )
                            if agent_changed:
                                current_span.set(None)
                                current_agent_span.set(None)
                                self.active_agent_name = None
                else:
                    # Reuse existing span
                    existing_span = current_agent_span.get()
                    if not existing_span:
                        return func(cai, active_agent, *args, **kwargs)

                    token = context.attach(
                        trace.set_span_in_context(existing_span))
                    try:
                        return func(cai, active_agent, *args, **kwargs)
                    finally:
                        context.detach(token)
            return wrapper
        return decorator


# Create a global instance of ExploitLogger
exploit_logger = ExploitLogger(
    tracing=os.getenv("CAI_TRACING", "true").lower() == "true"
)

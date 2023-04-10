# © 2023 SolarWinds Worldwide, LLC. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at:http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

"""This module provides a SolarWinds-specific exporter.

The exporter translates OpenTelemetry spans into SolarWinds Observability events so that the instrumentation data
generated by an OpenTelemetry-based agent can be processed by the SolarWinds backend.
"""

import importlib
import logging
import sys
from typing import Any

from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry.trace import SpanKind
from pkg_resources import get_distribution

from solarwinds_apm.apm_constants import (
    INTL_SWO_OTEL_SCOPE_NAME,
    INTL_SWO_OTEL_SCOPE_VERSION,
    INTL_SWO_SUPPORT_EMAIL,
)
from solarwinds_apm.apm_noop import Context as NoopContext
from solarwinds_apm.apm_noop import Metadata as NoopMetadata

# pylint: disable=import-error,no-name-in-module
from solarwinds_apm.extension.oboe import Context, Metadata
from solarwinds_apm.w3c_transformer import W3CTransformer

logger = logging.getLogger(__name__)


class SolarWindsSpanExporter(SpanExporter):
    """SolarWinds custom span exporter for the SolarWinds backend.
    Initialization requires a liboboe reporter.
    """

    _ASGI_APP_IMPLEMENTATIONS = [
        "fastapi",  # based on starlette, so higher up
        "starlette",
        "channels",
        "quart",
        "sanic",
        "rpc.py",
        "a2wsgi",
    ]
    _ASGI_SERVER_IMPLEMENTATIONS = [
        "uvicorn",
        "hypercorn",
        "daphne",
    ]
    _INTERNAL_TRANSACTION_NAME = "TransactionName"
    _SW_SPAN_KIND = "sw.span_kind"

    def __init__(
        self,
        reporter,
        apm_txname_manager,
        apm_fwkv_manager,
        agent_enabled,
        *args,
        **kw_args,
    ) -> None:
        super().__init__(*args, **kw_args)
        self.reporter = reporter
        self.apm_txname_manager = apm_txname_manager
        self.apm_fwkv_manager = apm_fwkv_manager
        if agent_enabled:
            self.context = Context
            self.metadata = Metadata
        else:
            self.context = NoopContext
            self.metadata = NoopMetadata

    def export(self, spans) -> None:
        """Export to AO events and report via liboboe.

        Note that OpenTelemetry timestamps are in nanoseconds, whereas SWO expects timestamps
        to be in microseconds, thus all times need to be divided by 1000.
        """
        for span in spans:
            md = self._build_metadata(self.metadata, span.get_span_context())
            if span.parent and span.parent.is_valid:
                # If there is a parent, we need to add an edge to this parent to this entry event
                logger.debug("Continue trace from %s", md.toString())
                parent_md = self._build_metadata(self.metadata, span.parent)
                evt = self.context.createEvent()  # TEST
                evt = self.context.createEvent(int(span.start_time / 1000))  # TEST
                evt = self.context.createEntry(
                    md, int(span.start_time / 1000), parent_md
                )
                if span.parent.is_remote:
                    self._add_info_transaction_name(span, evt)
            else:
                # In OpenTelemrtry, there are no events with individual IDs, but only a span ID
                # and trace ID. Thus, the entry event needs to be generated such that it has the
                # same op ID as the span ID of the OTel span.
                logger.debug("Start a new trace %s", md.toString())
                evt = self.context.createEvent()  # TEST
                evt = self.context.createEvent(int(span.start_time / 1000))  # TEST
                evt = self.context.createEntry(md, int(span.start_time / 1000))
                self._add_info_transaction_name(span, evt)

            evt.addInfo("Layer", span.name)
            evt.addInfo(self._SW_SPAN_KIND, span.kind.name)
            evt.addInfo("Language", "Python")
            self._add_info_instrumentation_scope(span, evt)
            self._add_info_instrumented_framework(span, evt)
            for attr_k, attr_v in span.attributes.items():
                evt.addInfo(attr_k, attr_v)
            # self.reporter.sendReport(evt, False)

            for event in span.events:
                if event.name == "exception":
                    self._report_exception_event(event)
                else:
                    self._report_info_event(event)

            evt = self.context.createExit(int(span.end_time / 1000))
            evt.addInfo("Layer", span.name)
            # self.reporter.sendReport(evt, False)

    def _add_info_transaction_name(self, span, evt) -> None:
        """Add transaction name from cache to root span
        then removes from cache"""
        trace_span_id = f"{span.context.trace_id}-{span.context.span_id}"
        txname = self.apm_txname_manager.get(trace_span_id)
        if txname:
            evt.addInfo(self._INTERNAL_TRANSACTION_NAME, txname)
            del self.apm_txname_manager[trace_span_id]
        else:
            logger.warning(
                "There was an issue setting trace TransactionName. "
                "Please contact %s with this issue",
                INTL_SWO_SUPPORT_EMAIL,
            )

    def _add_info_instrumentation_scope(self, span, evt) -> None:
        """Add info from InstrumentationScope of span, if exists"""
        if span.instrumentation_scope is None:
            logger.debug(
                "OTel instrumentation scope is None, so setting empty values."
            )
            evt.addInfo(INTL_SWO_OTEL_SCOPE_NAME, "")
            evt.addInfo(INTL_SWO_OTEL_SCOPE_VERSION, "")
            return

        # name is always string in Otel Python
        evt.addInfo(INTL_SWO_OTEL_SCOPE_NAME, span.instrumentation_scope.name)
        # version may be None
        if span.instrumentation_scope.version is None:
            evt.addInfo(INTL_SWO_OTEL_SCOPE_VERSION, "")
        else:
            evt.addInfo(
                INTL_SWO_OTEL_SCOPE_VERSION, span.instrumentation_scope.version
            )

    # pylint: disable=too-many-branches,too-many-statements
    def _add_info_instrumented_framework(self, span, evt) -> None:
        """Add info to span for which Python framework has been instrumented
        with OTel. Based on instrumentation scope of the span, if present.
        Assumes all valid instrumentation_scope names must be
        `opentelemetry.instrumentation.*`"""
        instr_scope_name = span.instrumentation_scope.name
        if (
            instr_scope_name
            and "opentelemetry.instrumentation" in instr_scope_name
        ):
            framework = instr_scope_name.split(".")[2]
            # Some OTel instrumentation libraries are named not exactly
            # the same as the instrumented libraries!
            # https://github.com/open-telemetry/opentelemetry-python-contrib/blob/main/instrumentation/README.md
            if framework == "aiohttp_client":
                framework = "aiohttp"
            elif framework == "system_metrics":
                framework = "psutil"
            elif framework == "tortoiseorm":
                framework = "tortoise"
            # asgi is implemented over multiple frameworks
            # https://asgi.readthedocs.io/en/latest/implementations.html
            # Use the first best guess framework for name and version
            # TODO Increase precision
            elif framework == "asgi":
                if span.kind == SpanKind.SERVER:
                    for asgi_impl in self._ASGI_SERVER_IMPLEMENTATIONS:
                        try:
                            importlib.import_module(asgi_impl)
                        except (AttributeError, ImportError):
                            continue
                        else:
                            logger.debug(
                                "Setting %s as instrumented ASGI server framework span KV",
                                asgi_impl,
                            )
                            framework = asgi_impl
                            break
                else:
                    # SpanKind.INTERNAL might be common for async
                    for asgi_impl in self._ASGI_APP_IMPLEMENTATIONS:
                        try:
                            importlib.import_module(asgi_impl)
                        except (AttributeError, ImportError):
                            continue
                        else:
                            logger.debug(
                                "Setting %s as instrumented ASGI application framework span KV",
                                asgi_impl,
                            )
                            framework = asgi_impl
                            break

            instr_key = f"Python.{framework}.Version"
            if "grpc_" in framework:
                instr_key = "Python.grpc.Version"

            # Use cached version if available
            cached_version = self.apm_fwkv_manager.get(instr_key)
            if cached_version:
                evt.addInfo(
                    instr_key,
                    cached_version,
                )
                return

            try:
                # There is no mysql version, but mysql.connector version
                if framework == "mysql":
                    importlib.import_module(f"{framework}.connector")
                # urllib has a rich complex history
                elif framework == "urllib":
                    importlib.import_module(f"{framework}.request")
                else:
                    importlib.import_module(framework)

                version_str = ""
                # some Python frameworks don't have top-level __version__
                # and elasticsearch gives a version as (8, 5, 3) not 8.5.3
                if framework == "elasticsearch":
                    version_tuple = sys.modules[framework].__version__
                    version_str = ".".join([str(d) for d in version_tuple])
                elif framework == "mysql":
                    version_str = sys.modules[
                        f"{framework}.connector"
                    ].__version__
                elif framework == "pyramid":
                    version_str = get_distribution(framework).version
                elif framework == "sqlite3":
                    version_str = sys.modules[framework].sqlite_version
                elif framework == "tornado":
                    version_str = sys.modules[framework].version
                elif framework == "urllib":
                    version_str = sys.modules[
                        f"{framework}.request"
                    ].__version__
                else:
                    version_str = sys.modules[framework].__version__

                evt.addInfo(
                    instr_key,
                    version_str,
                )
                # cache for future similar spans
                self.apm_fwkv_manager[instr_key] = version_str

            except (AttributeError, ImportError) as ex:
                # could not import package for whatever reason
                logger.warning(
                    "Version lookup of %s failed, so skipping: %s",
                    framework,
                    ex,
                )

    def _report_exception_event(self, event) -> None:
        evt = self.context.createEvent()  # TEST
        evt = self.context.createEvent(int(event.timestamp / 1000))
        evt.addInfo("Label", "error")
        evt.addInfo("Spec", "error")
        evt.addInfo("ErrorClass", event.attributes.get("exception.type", None))
        evt.addInfo(
            "ErrorMsg", event.attributes.get("exception.message", None)
        )
        evt.addInfo(
            "Backtrace", event.attributes.get("exception.stacktrace", None)
        )
        # add remaining attributes, if any
        for attr_k, attr_v in event.attributes.items():
            if attr_k not in (
                "exception.type",
                "exception.message",
                "exception.stacktrace",
            ):
                evt.addInfo(attr_k, attr_v)
        # self.reporter.sendReport(evt, False)

    def _report_info_event(self, event) -> None:
        print("Found info event")
        print(dir(event))
        print(event)
        evt = self.context.createEvent()  # TEST
        evt = self.context.createEvent(int(event.timestamp / 1000))
        evt.addInfo("Label", "info")
        for attr_k, attr_v in event.attributes.items():
            evt.addInfo(attr_k, attr_v)
        # self.reporter.sendReport(evt, False)

    @staticmethod
    def _build_metadata(metadata, span_context) -> Any:
        return metadata.fromString(
            W3CTransformer.traceparent_from_context(span_context)
        )

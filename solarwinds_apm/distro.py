# © 2023 SolarWinds Worldwide, LLC. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at:http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

"""Module to configure OpenTelemetry to work with SolarWinds backend"""

import logging
import platform
import sys
from os import environ
from typing import Any

from opentelemetry.environment_variables import (
    OTEL_PROPAGATORS,
    OTEL_TRACES_EXPORTER,
)
from opentelemetry.instrumentation.distro import BaseDistro
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.logging.environment_variables import (
    OTEL_PYTHON_LOG_FORMAT,
)
from opentelemetry.instrumentation.version import __version__ as inst_version
from opentelemetry.sdk.environment_variables import OTEL_EXPORTER_OTLP_PROTOCOL
from opentelemetry.sdk.version import __version__ as sdk_version
from opentelemetry.util._importlib_metadata import EntryPoint

from solarwinds_apm.apm_config import SolarWindsApmConfig
from solarwinds_apm.apm_constants import (
    INTL_SWO_DEFAULT_OTLP_COLLECTOR,
    INTL_SWO_DEFAULT_OTLP_EXPORTER,
    INTL_SWO_DEFAULT_OTLP_EXPORTER_GRPC,
    INTL_SWO_DEFAULT_PROPAGATORS,
    INTL_SWO_DEFAULT_TRACES_EXPORTER,
)
from solarwinds_apm.version import __version__ as apm_version

_EXPORTER_BY_OTLP_PROTOCOL = {
    "grpc": INTL_SWO_DEFAULT_OTLP_EXPORTER_GRPC,
    "http/protobuf": INTL_SWO_DEFAULT_OTLP_EXPORTER,
}
_SQLCOMMENTERS = [
    "django",
    "flask",
    "psycopg",
    "psycopg2",
    "sqlalchemy",
]

logger = logging.getLogger(__name__)


class SolarWindsDistro(BaseDistro):
    """OpenTelemetry Distro for SolarWinds reporting environment"""

    def _log_python_runtime(self):
        """Logs Python runtime info, with any warnings"""
        python_vers = platform.python_version()
        logger.info("Python %s", python_vers)

        # https://devguide.python.org/versions/
        if sys.version_info.major == 3 and sys.version_info.minor < 8:
            logger.error(
                "Obsolete: Python %s is at end-of-life and support "
                "by APM Python and OpenTelemetry has been dropped. Please upgrade.",
                python_vers,
            )

    def _log_runtime(self):
        """Logs APM Python runtime info (high debug level)"""
        logger.info("SolarWinds APM Python %s", apm_version)
        self._log_python_runtime()
        logger.info("OpenTelemetry %s/%s", sdk_version, inst_version)

    def _get_token_from_service_key(self):
        """Return token portion of service_key if set, else None"""
        service_key = environ.get("SW_APM_SERVICE_KEY")
        if not service_key:
            logger.debug("Missing service key")
            return None
        # Key must be at least one char + ":" + at least one other char
        key_parts = [p for p in service_key.split(":") if len(p) > 0]
        if len(key_parts) != 2:
            logger.debug("Incorrect service key format")
            return None
        return key_parts[0]

    def _configure_otlp_env_defaults(
        self,
        signal_type: str,
        header_token: str,
        otlp_protocol: str,
    ) -> None:
        """Configure env defaults for OTLP signal export by HTTP or gRPC to SWO"""
        protocol_env_var = f"OTEL_EXPORTER_OTLP_{signal_type.upper()}_PROTOCOL"
        exporter_env_var = f"OTEL_{signal_type.upper()}_EXPORTER"
        endpoint_env_var = f"OTEL_EXPORTER_OTLP_{signal_type.upper()}_ENDPOINT"
        headers_env_var = f"OTEL_EXPORTER_OTLP_{signal_type.upper()}_HEADERS"

        environ.setdefault(protocol_env_var, otlp_protocol)
        environ.setdefault(
            exporter_env_var, _EXPORTER_BY_OTLP_PROTOCOL[otlp_protocol]
        )
        environ.setdefault(
            endpoint_env_var,
            f"{INTL_SWO_DEFAULT_OTLP_COLLECTOR}/v1/{signal_type}",
        )
        if header_token:
            environ.setdefault(
                headers_env_var, f"authorization=Bearer%20{header_token}"
            )

    def _configure_logs_export_otlp_env_defaults(
        self,
        header_token: str,
        otlp_protocol: str,
    ) -> None:
        """Configure env defaults for OTLP logs signal export by HTTP or gRPC to SWO"""
        self._configure_otlp_env_defaults("logs", header_token, otlp_protocol)

    def _configure_metrics_export_otlp_env_defaults(
        self,
        header_token: str,
        otlp_protocol: str,
    ) -> None:
        """Configure env defaults for OTLP metrics signal export by HTTP or gRPC to SWO"""
        self._configure_otlp_env_defaults(
            "metrics", header_token, otlp_protocol
        )

    def _configure_traces_export_otlp_env_defaults(
        self,
        header_token: str,
        otlp_protocol: Any = None,
    ) -> None:
        """Configure env defaults for OTLP traces signal export by APM protocol
        to SWO, else follow provided OTLP protocol (HTTP or gRPC)"""
        self._configure_otlp_env_defaults(
            "traces", header_token, otlp_protocol
        )

    def _configure(self, **kwargs):
        """Configure default OTel components for APM Python.

        This is a sitecustomize callee of the opentelemetry-instrument entrypoint.
        """
        self._log_runtime()

        # Propagators, log format defaults and semconv the same
        # whether APM Python uses OTLP and/or legacy mode
        environ.setdefault(
            OTEL_PROPAGATORS, ",".join(INTL_SWO_DEFAULT_PROPAGATORS)
        )
        # Default for LoggingInstrumentor
        environ.setdefault(
            OTEL_PYTHON_LOG_FORMAT,
            "%(asctime)s %(levelname)s [%(name)s] [%(filename)s:%(lineno)d] [trace_id=%(otelTraceID)s span_id=%(otelSpanID)s trace_flags=%(otelTraceSampled)02d resource.service.name=%(otelServiceName)s] - %(message)s",
        )
        # TODO: Support other signal types when available
        # Always opt into new semconv for all instrumentors (if supported)
        environ["OTEL_SEMCONV_STABILITY_OPT_IN"] = self.get_semconv_opt_in()

        # setdefaults for OTLP export if protocol is unset or valid,
        # with the exception of OTEL_TRACES_EXPORTER if legacy.
        # Does not setdefaults if invalid protocol.
        # All values can still be configured by user (SolarWindsApmConfig).
        environ.setdefault(
            OTEL_EXPORTER_OTLP_PROTOCOL,
            "http/protobuf",
        )
        # Protocol is the above default or what user has set
        otlp_protocol = environ.get(OTEL_EXPORTER_OTLP_PROTOCOL)

        is_legacy = SolarWindsApmConfig.calculate_is_legacy()

        if otlp_protocol:
            if otlp_protocol in _EXPORTER_BY_OTLP_PROTOCOL:
                header_token = self._get_token_from_service_key()
                if not header_token:
                    logger.debug(
                        "Setting OTLP export defaults without SWO token"
                    )

                if is_legacy:
                    environ.setdefault(
                        OTEL_TRACES_EXPORTER, INTL_SWO_DEFAULT_TRACES_EXPORTER
                    )
                else:
                    self._configure_traces_export_otlp_env_defaults(
                        header_token, otlp_protocol
                    )

                # We do OTLP export setdefault if legacy or not
                # in case SW_APM_EXPORT_METRICS_ENABLED
                self._configure_logs_export_otlp_env_defaults(
                    header_token, otlp_protocol
                )
                self._configure_metrics_export_otlp_env_defaults(
                    header_token, otlp_protocol
                )

            else:
                logger.warning(
                    "Invalid OTLP export protocol configured. Skipping setting of default export configuration."
                )

    def load_instrumentor(self, entry_point: EntryPoint, **kwargs):
        """Takes a collection of instrumentation entry points
        and activates them by instantiating and calling instrument()
        on each one. This is a method override to pass additional
        arguments to each entry point. This function is called for every
        individual instrumentor by upstream sitecustomize.

        For enabling sqlcommenting:
        - OTEL_SQLCOMMENTER_ENABLED is deprecated
        - All instrumentors enabled if OTEL_SQLCOMMENTER_ENABLED=true
        - If OTEL_SQLCOMMENTER_ENABLED=false, SW_APM_ENABLED_SQLCOMMENT enables
          individual instrumentors if in _SQLCOMMENTERS (each is false by default)
        """
        # If we're in Lambda environment, then we skip loading
        # AwsLambdaInstrumentor because we assume the wrapper
        # has done it for us already
        if entry_point.name == "aws-lambda":
            if SolarWindsApmConfig.calculate_is_lambda():
                return

        # If OTEL_SQLCOMMENTER_ENABLED=true, set `enable` for all instrumentors.
        # Assumes sqlcommenting kwargs are ignored if sqlcommenting is not implemented
        # for the current instrumentation library.
        if self.enable_commenter():
            # For Flask ORM, sqlalchemy, psycopg2
            kwargs["enable_commenter"] = True
            # For Django ORM
            kwargs["is_sql_commentor_enabled"] = True

            # Assumes this value can be empty
            # Note: Django ORM reads options in settings.py instead
            # https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/django/django.html
            kwargs["commenter_options"] = self.detect_commenter_options()

            logger.debug(
                "(Deprecated) Enabling sqlcommenter for %s with %s",
                entry_point.name,
                kwargs,
            )

        elif entry_point.name in _SQLCOMMENTERS:
            entry_point_setting = self.get_enable_commenter_env_map().get(
                entry_point.name
            )
            if entry_point_setting is True:
                if entry_point.name == "django":
                    kwargs["is_sql_commentor_enabled"] = True
                else:
                    kwargs["enable_commenter"] = True
                    # Assumes this value can be empty
                    # Note: Django ORM reads options in settings.py instead
                    # https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/django/django.html
                    kwargs["commenter_options"] = (
                        self.detect_commenter_options()
                    )
                logger.debug(
                    "Enabling sqlcommenter for %s with %s",
                    entry_point.name,
                    kwargs,
                )

        try:
            instrumentor: BaseInstrumentor = entry_point.load()
        except Exception as ex:  # pylint: disable=broad-except
            logger.error(
                "Could not load instrumentor %s: %s",
                entry_point.name,
                ex,
            )
            return
        instrumentor().instrument(**kwargs)

    def enable_commenter(self) -> bool:
        """Enable sqlcommenter feature, if implemented"""
        enable_commenter = environ.get("OTEL_SQLCOMMENTER_ENABLED", "")
        if enable_commenter.lower() == "true":
            logger.warning(
                "Deprecated: OTEL_SQLCOMMENTER_ENABLED support will be removed in a future release. Please use SW_APM_ENABLED_SQLCOMMENT instead."
            )
            return True
        return False

    def get_enable_commenter_env_map(self) -> dict:
        """Return a map of which instrumentors will have sqlcomment enabled,
        if implemented. Default is False for each instrumentor in _SQLCOMMENTERS.

        Reads env SW_APM_ENABLED_SQLCOMMENT as a comma-separated string of KVs
        paired by equals signs, e.g. 'django=true,sqlalchemy=false'."""
        env_commenter_items = environ.get("SW_APM_ENABLED_SQLCOMMENT", "")
        env_commenter_map = {instr: False for instr in _SQLCOMMENTERS}
        if env_commenter_items:
            for item in env_commenter_items.split(","):
                try:
                    key, value = item.split("=", maxsplit=1)
                except ValueError as exc:
                    logger.warning(
                        "Invalid sqlcommenter key value at pair %s: %s",
                        item,
                        exc,
                    )
                    continue

                instrumentor_name = key.strip().lower()
                if instrumentor_name in _SQLCOMMENTERS:
                    env_v_bool = SolarWindsApmConfig.convert_to_bool(
                        value.strip()
                    )
                    if env_v_bool is not None:
                        env_commenter_map[instrumentor_name] = env_v_bool

        return env_commenter_map

    def detect_commenter_options(self):
        """Returns commenter options dict parsed from environment, if any

        OTEL_SQLCOMMENTER_OPTIONS is deprecated (along with OTEL_SQLCOMMENTER_ENABLED).
        Users should update to use SW_APM_OPTIONS_SQLCOMMENT instead"""
        commenter_opts = {}
        commenter_opts_env_depr = environ.get("OTEL_SQLCOMMENTER_OPTIONS")
        commenter_opts_env = environ.get("SW_APM_OPTIONS_SQLCOMMENT")

        opt_items = []
        if commenter_opts_env_depr:
            logger.warning(
                "Deprecated: OTEL_SQLCOMMENTER_OPTIONS support will be removed in a future release. Please use SW_APM_OPTIONS_SQLCOMMENT instead."
            )
            opt_items = commenter_opts_env_depr.split(",")
        elif commenter_opts_env:
            opt_items = commenter_opts_env.split(",")
        else:
            return commenter_opts

        for opt_item in opt_items:
            opt_k = ""
            opt_v = ""
            try:
                opt_k, opt_v = opt_item.split("=", maxsplit=1)
            except ValueError as exc:
                logger.warning(
                    "Invalid key-value pair for sqlcommenter option %s: %s",
                    opt_item,
                    exc,
                )
            opt_v_bool = SolarWindsApmConfig.convert_to_bool(opt_v.strip())
            if opt_v_bool is not None:
                commenter_opts[opt_k.strip()] = opt_v_bool

        return commenter_opts

    def get_semconv_opt_in(self):
        """
        Always returns semconv config as opt-into new, stable HTTP only

        See also:
        https://github.com/open-telemetry/opentelemetry-python-contrib/blob/0a231e57f9722e6101194c6b38695addf23ab950/opentelemetry-instrumentation/src/opentelemetry/instrumentation/_semconv.py#L93-L99
        """
        # TODO: Support other signal types when available
        # return environ.get("OTEL_SEMCONV_STABILITY_OPT_IN")

        return "http"

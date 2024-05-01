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

from opentelemetry.environment_variables import (
    OTEL_METRICS_EXPORTER,
    OTEL_PROPAGATORS,
    OTEL_TRACES_EXPORTER,
)
from opentelemetry.instrumentation.distro import BaseDistro
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.logging.environment_variables import (
    OTEL_PYTHON_LOG_CORRELATION,
    OTEL_PYTHON_LOG_FORMAT,
)
from opentelemetry.instrumentation.version import __version__ as inst_version
from opentelemetry.sdk.environment_variables import OTEL_EXPORTER_OTLP_PROTOCOL
from opentelemetry.sdk.version import __version__ as sdk_version
from pkg_resources import EntryPoint

from solarwinds_apm.apm_config import SolarWindsApmConfig
from solarwinds_apm.apm_constants import (
    INTL_SWO_DEFAULT_OTLP_EXPORTER,
    INTL_SWO_DEFAULT_OTLP_EXPORTER_GRPC,
    INTL_SWO_DEFAULT_PROPAGATORS,
    INTL_SWO_DEFAULT_TRACES_EXPORTER,
)
from solarwinds_apm.apm_userconfig import SolarWindsApmUserConfig
from solarwinds_apm.version import __version__ as apm_version

_EXPORTER_BY_OTLP_PROTOCOL = {
    "grpc": INTL_SWO_DEFAULT_OTLP_EXPORTER_GRPC,
    "http/protobuf": INTL_SWO_DEFAULT_OTLP_EXPORTER,
}

logger = logging.getLogger(__name__)


class SolarWindsDistro(BaseDistro):
    """OpenTelemetry Distro for SolarWinds reporting environment"""

    def _log_python_runtime(self):
        """Logs Python runtime info, with any warnings"""
        python_vers = platform.python_version()
        logger.info("Python %s", python_vers)

        # https://devguide.python.org/versions/
        if sys.version_info.major == 3 and sys.version_info.minor < 8:
            logger.warning(
                "Deprecation: Python %s is at end-of-life and support "
                "by APM Python will be dropped in a future release. Please upgrade.",
                python_vers,
            )

    def _log_runtime(self):
        """Logs APM Python runtime info (high debug level)"""
        logger.info("SolarWinds APM Python %s", apm_version)
        self._log_python_runtime()
        logger.info("OpenTelemetry %s/%s", sdk_version, inst_version)

    def _set_user_config(self):
        """Create UserConfig and set in environment for APM components configuration"""
        user_config = SolarWindsApmUserConfig()
        user_config.write_to_env_file()
        return user_config

    def _configure(self, **kwargs):
        """Configure default OTel exporter and propagators"""
        self._log_runtime()

        # TODO available to load_instrumentor
        self._set_user_config()

        # Set log format depending on if log correlation enabled,
        # for APM Python OR logging instrumentor
        otel_log_correlation = (
            environ.get(OTEL_PYTHON_LOG_CORRELATION, "false").lower() == "true"
        )
        if otel_log_correlation:
            environ.setdefault(
                OTEL_PYTHON_LOG_FORMAT,
                "%(asctime)s %(levelname)s [%(name)s] [%(filename)s:%(lineno)d] [trace_id=%(otelTraceID)s span_id=%(otelSpanID)s trace_flags=%(otelTraceSampled)02d resource.service.name=%(otelServiceName)s] - %(message)s",
            )
        else:
            environ.setdefault(
                OTEL_PYTHON_LOG_FORMAT,
                "%(asctime)s %(levelname)s [%(name)s] [%(filename)s:%(lineno)d] - %(message)s",
            )

        otlp_protocol = environ.get(OTEL_EXPORTER_OTLP_PROTOCOL)
        if otlp_protocol in _EXPORTER_BY_OTLP_PROTOCOL:
            # If users set OTEL_EXPORTER_OTLP_PROTOCOL
            # as one of Otel SDK's `http/protobuf` or `grpc`,
            # then the matching exporters are mapped by default
            environ.setdefault(
                OTEL_METRICS_EXPORTER,
                _EXPORTER_BY_OTLP_PROTOCOL[otlp_protocol],
            )
            environ.setdefault(
                OTEL_TRACES_EXPORTER, _EXPORTER_BY_OTLP_PROTOCOL[otlp_protocol]
            )
        else:
            # Else users need to specify OTEL_METRICS_EXPORTER.
            # Otherwise, no metrics will generated and no metrics exporter
            # will be initialized.
            environ.setdefault(
                OTEL_TRACES_EXPORTER, INTL_SWO_DEFAULT_TRACES_EXPORTER
            )

        environ.setdefault(
            OTEL_PROPAGATORS, ",".join(INTL_SWO_DEFAULT_PROPAGATORS)
        )

    def load_instrumentor(self, entry_point: EntryPoint, **kwargs):
        """Takes a collection of instrumentation entry points
        and activates them by instantiating and calling instrument()
        on each one. This is a method override to pass additional
        arguments to each entry point.
        """
        # TODO
        # Set log_handlers for logging instrumentor. Assumes instrumentor
        # only creates handler if context correlation enabled. Assumes
        # kwargs ignored if not implemented for current instrumentation library

        # TODO
        # Use file handler if filepath configured by user

        # Set enable for sqlcommenter. Assumes kwargs ignored if not
        # implemented for current instrumentation library
        if self.enable_commenter():
            # instrumentation for Flask ORM, sqlalchemy, psycopg2
            kwargs["enable_commenter"] = True
            # instrumentation for Django ORM
            kwargs["is_sql_commentor_enabled"] = True

            # Assumes can be empty and any KVs not used
            # by current library are ignored
            # Note: Django ORM accepts options in settings.py
            # https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/django/django.html
            kwargs["commenter_options"] = self.detect_commenter_options()
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
        # TODO: Update if changed in OTel spec:
        # https://github.com/open-telemetry/opentelemetry-specification/issues/3560
        enable_commenter = environ.get("OTEL_SQLCOMMENTER_ENABLED", "")
        if enable_commenter.lower() == "true":
            return True
        return False

    def detect_commenter_options(self):
        """Returns commenter options dict parsed from environment, if any"""
        commenter_opts = {}
        commenter_opts_env = environ.get("OTEL_SQLCOMMENTER_OPTIONS")
        if commenter_opts_env:
            for opt_item in commenter_opts_env.split(","):
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

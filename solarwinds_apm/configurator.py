# © 2023 SolarWinds Worldwide, LLC. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at:http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

"""Module to initialize OpenTelemetry SDK components and liboboe to work with SolarWinds backend"""

import importlib
import logging
import math
import os
import platform
import sys
import time
from typing import TYPE_CHECKING, Any

from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.environment_variables import (
    OTEL_LOGS_EXPORTER,
    OTEL_METRICS_EXPORTER,
    OTEL_PROPAGATORS,
    OTEL_TRACES_EXPORTER,
)
from opentelemetry.instrumentation.dependencies import (
    get_dist_dependency_conflicts,
)
from opentelemetry.instrumentation.environment_variables import (
    OTEL_PYTHON_DISABLED_INSTRUMENTATIONS,
)
from opentelemetry.instrumentation.propagators import (
    set_global_response_propagator,
)
from opentelemetry.metrics import set_meter_provider
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk._configuration import _OTelSDKConfigurator
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.environment_variables import (
    _OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED,
)
from opentelemetry.sdk.metrics import Histogram, MeterProvider
from opentelemetry.sdk.metrics.export import (
    AggregationTemporality,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
)
from opentelemetry.util._importlib_metadata import entry_points, version

from solarwinds_apm import apm_logging
from solarwinds_apm.apm_config import SolarWindsApmConfig
from solarwinds_apm.apm_constants import (
    INTL_SWO_DEFAULT_PROPAGATORS,
    INTL_SWO_DEFAULT_TRACES_EXPORTER,
    INTL_SWO_SUPPORT_EMAIL,
)
from solarwinds_apm.apm_fwkv_manager import SolarWindsFrameworkKvManager
from solarwinds_apm.apm_oboe_codes import OboeReporterCode
from solarwinds_apm.apm_txname_manager import SolarWindsTxnNameManager
from solarwinds_apm.response_propagator import (
    SolarWindsTraceResponsePropagator,
)
from solarwinds_apm.trace import (
    ServiceEntryIdSpanProcessor,
    SolarWindsInboundMetricsSpanProcessor,
    SolarWindsOTLPMetricsSpanProcessor,
    TxnNameCalculatorProcessor,
    TxnNameCleanupProcessor,
)
from solarwinds_apm.version import __version__

if TYPE_CHECKING:
    from solarwinds_apm.extension.oboe import Event, OboeAPI, Reporter

solarwinds_apm_logger = apm_logging.logger
logger = logging.getLogger(__name__)


class SolarWindsConfigurator(_OTelSDKConfigurator):
    """OpenTelemetry Configurator for initializing APM logger and SolarWinds-reporting SDK components"""

    # Agent process start time, which is supposed to be a constant. -- don't modify it.
    _AGENT_START_TIME = time.time() * 1e6
    # Cannot set as env default because not part of OTel Python _KNOWN_SAMPLERS
    # https://github.com/open-telemetry/opentelemetry-python/blob/main/opentelemetry-sdk/src/opentelemetry/sdk/trace/sampling.py#L364-L380
    _DEFAULT_SW_TRACES_SAMPLER = "solarwinds_sampler"
    _STDLIB_PKGS = ["asyncio", "threading"]

    def _configure(self, **kwargs: int) -> None:
        """Configure SolarWinds APM and OTel components"""
        apm_txname_manager = SolarWindsTxnNameManager()
        apm_fwkv_manager = SolarWindsFrameworkKvManager()
        apm_config = SolarWindsApmConfig()
        oboe_api = apm_config.oboe_api

        # Reporter may be no-op e.g. disabled, lambda
        reporter = self._initialize_solarwinds_reporter(apm_config)
        self._configure_otel_components(
            apm_txname_manager,
            apm_fwkv_manager,
            apm_config,
            reporter,
            oboe_api,
        )

        if apm_config.get("legacy") is False:
            logger.debug("No init event outside legacy mode")
            return

        # Report reporter init status event after everything is done.
        init_event = self._create_init_event(reporter, apm_config)
        if init_event:
            self._report_init_event(reporter, init_event)
        else:
            logger.error(
                "There was an issue with generating the reporter init message."
            )

    # TODO update pylint disable when drop py38 support
    def _configure_otel_components(
        self,
        apm_txname_manager: SolarWindsTxnNameManager,
        apm_fwkv_manager: SolarWindsFrameworkKvManager,
        apm_config: SolarWindsApmConfig,
        reporter: "Reporter",
        oboe_api: "OboeAPI",
    ) -> None:
        """Configure OTel sampler, exporter, propagator, response propagator"""
        self._configure_sampler(
            apm_config,
            reporter,
            oboe_api,
        )
        if apm_config.agent_enabled:
            # set MeterProvider first via metrics_exporter config
            self._configure_metrics_exporter(apm_config)
            # This processor only defines on_start
            self._configure_service_entry_id_span_processor()

            # The txnname calculator span processor must be registered
            # before the rest of the processors with defined on_end
            self._configure_txnname_calculator_span_processor(
                apm_txname_manager,
            )
            self._configure_inbound_metrics_span_processor(
                apm_txname_manager,
                apm_config,
            )
            self._configure_otlp_metrics_span_processors(
                apm_txname_manager,
                apm_config,
                oboe_api,
            )
            # The txnname cleanup span processor must be registered
            # after the rest of the processors with defined on_end
            self._configure_txnname_cleanup_span_processor(
                apm_txname_manager,
            )

            self._configure_traces_exporter(
                reporter,
                apm_txname_manager,
                apm_fwkv_manager,
                apm_config,
            )
            self._configure_logs_exporter(apm_config)
            self._configure_propagator()
            self._configure_response_propagator()
        else:
            # Warning: This may still set OTEL_PROPAGATORS if set because OTel API
            logger.error("Tracing disabled. Not setting propagators.")

    def _configure_sampler(
        self,
        apm_config: SolarWindsApmConfig,
        reporter: "Reporter",
        oboe_api: "OboeAPI",
    ) -> None:
        """Always configure SolarWinds OTel sampler, or none if disabled"""
        if not apm_config.agent_enabled:
            logger.error("Tracing disabled. Using OTel no-op tracer provider.")
            trace.set_tracer_provider(trace.NoOpTracerProvider())
            return
        try:
            sampler = next(
                iter(
                    entry_points(
                        group="opentelemetry_traces_sampler",
                        name=self._DEFAULT_SW_TRACES_SAMPLER,
                    )
                )
            ).load()(apm_config, reporter, oboe_api)
        except Exception as ex:
            logger.exception("A exception was raised: %s", ex)
            logger.exception(
                "Failed to load configured sampler %s. "
                "Please reinstall or contact %s.",
                self._DEFAULT_SW_TRACES_SAMPLER,
                INTL_SWO_SUPPORT_EMAIL,
            )
            raise
        trace.set_tracer_provider(
            TracerProvider(
                sampler=sampler,
                resource=Resource.create(
                    {
                        "sw.apm.version": __version__,
                        "sw.data.module": "apm",
                        "service.name": apm_config.service_name,
                    }
                ),
            ),
        )

    def _configure_service_entry_id_span_processor(
        self,
    ) -> None:
        """Configure ServiceEntryIdSpanProcessor"""
        trace.get_tracer_provider().add_span_processor(
            ServiceEntryIdSpanProcessor()
        )

    def _configure_txnname_calculator_span_processor(
        self,
        apm_txname_manager: SolarWindsTxnNameManager,
    ) -> None:
        """Configure TxnNameCalculatorSpanProcessor"""
        trace.get_tracer_provider().add_span_processor(
            TxnNameCalculatorProcessor(
                apm_txname_manager,
            )
        )

    def _configure_txnname_cleanup_span_processor(
        self,
        apm_txname_manager: SolarWindsTxnNameManager,
    ) -> None:
        """Configure TxnNameCleanupSpanProcessor"""
        trace.get_tracer_provider().add_span_processor(
            TxnNameCleanupProcessor(
                apm_txname_manager,
            )
        )

    def _configure_inbound_metrics_span_processor(
        self,
        apm_txname_manager: SolarWindsTxnNameManager,
        apm_config: SolarWindsApmConfig,
    ) -> None:
        """Configure SolarWindsInboundMetricsSpanProcessor only if solarwinds_exporter
        for traces will also be loaded.

        Note: if config's extension is no-op, the processor will run
        but will not export inbound metrics."""
        # SolarWindsDistro._configure does setdefault before this is called
        environ_exporter = os.environ.get(
            OTEL_TRACES_EXPORTER,
        )
        if not environ_exporter:
            logger.debug(
                "No OTEL_TRACES_EXPORTER set, skipping init of inbound metrics processor."
            )
            return
        environ_exporter_names = environ_exporter.split(",")
        if INTL_SWO_DEFAULT_TRACES_EXPORTER not in environ_exporter_names:
            logger.debug(
                "Skipping init of inbound metrics processor because not exporting AO-proto traces."
            )
            return

        trace.get_tracer_provider().add_span_processor(
            SolarWindsInboundMetricsSpanProcessor(
                apm_txname_manager,
                apm_config,
            )
        )

    def _configure_otlp_metrics_span_processors(
        self,
        apm_txname_manager: SolarWindsTxnNameManager,
        apm_config: SolarWindsApmConfig,
        oboe_api: "OboeAPI",
    ) -> None:
        """Configure SolarWindsOTLPMetricsSpanProcessor (including OTLP meters)
        if metrics exporters are configured and set up i.e. by _configure_metrics_exporter
        """
        # SolarWindsDistro._configure does setdefault before this is called
        environ_exporter = os.environ.get(
            OTEL_METRICS_EXPORTER,
        )
        if not environ_exporter:
            logger.debug(
                "No OTEL_METRICS_EXPORTER set, skipping init of metrics processors"
            )
            return

        trace.get_tracer_provider().add_span_processor(
            SolarWindsOTLPMetricsSpanProcessor(
                apm_txname_manager,
                apm_config,
                oboe_api,
            )
        )

    def _configure_traces_exporter(
        self,
        reporter: "Reporter",
        apm_txname_manager: SolarWindsTxnNameManager,
        apm_fwkv_manager: SolarWindsFrameworkKvManager,
        apm_config: SolarWindsApmConfig,
    ) -> None:
        """Configure traces exporters if agent enabled.
        Links to global TracerProvider.

        Initialization of SolarWinds exporter requires a liboboe reporter
        If `reporter` is no-op, the SW exporter will not export spans."""
        if not apm_config.agent_enabled:
            logger.error(
                "APM Python library disabled. Cannot set traces exporters."
            )
            return

        # SolarWindsDistro._configure does setdefault before this is called
        environ_exporter = os.environ.get(
            OTEL_TRACES_EXPORTER,
        )
        if not environ_exporter:
            logger.debug(
                "No OTEL_TRACES_EXPORTER set, skipping init of traces exporter."
            )
            return
        environ_exporter_names = environ_exporter.split(",")

        for exporter_name in environ_exporter_names:
            exporter = None
            try:
                if exporter_name == INTL_SWO_DEFAULT_TRACES_EXPORTER:
                    exporter = next(
                        iter(
                            entry_points(
                                group="opentelemetry_traces_exporter",
                                name=exporter_name,
                            )
                        )
                    ).load()(
                        reporter,
                        apm_txname_manager,
                        apm_fwkv_manager,
                        apm_config,
                    )
                else:
                    exporter = next(
                        iter(
                            # pylint: disable=too-many-function-args
                            entry_points(
                                group="opentelemetry_traces_exporter",
                                name=exporter_name,
                            )
                        )
                    ).load()()
            except Exception as ex:
                logger.exception("A exception was raised: %s", ex)
                # At this point any non-default OTEL_TRACES_EXPORTER has
                # been checked by ApmConfig so exception here means
                # something quite wrong
                logger.exception(
                    "Failed to load configured OTEL_TRACES_EXPORTER. "
                    "Please reinstall or contact %s.",
                    INTL_SWO_SUPPORT_EMAIL,
                )
                raise

            if apm_config.is_lambda:
                logger.debug(
                    "Setting trace with SimpleSpanProcessor using %s",
                    exporter_name,
                )
                span_processor = SimpleSpanProcessor(exporter)
            else:
                logger.debug(
                    "Setting trace with BatchSpanProcessor using %s",
                    exporter_name,
                )
                span_processor = BatchSpanProcessor(exporter)

            trace.get_tracer_provider().add_span_processor(span_processor)

    def _configure_metrics_exporter(
        self,
        apm_config: SolarWindsApmConfig,
    ) -> None:
        """Configure OTel OTLP metrics exporters if enabled and agent enabled.
        Settings precedence: OTEL_* > SW_APM_EXPORT_METRICS_ENABLED.
        Links to new metric readers and global MeterProvider."""
        if not apm_config.agent_enabled:
            logger.error(
                "APM Python library disabled. Cannot set metrics exporters."
            )
            return

        if not apm_config.get("export_metrics_enabled"):
            logger.debug(
                "APM OTLP metrics export disabled. Skipping init of metrics exporters"
            )
            return

        # SolarWindsDistro._configure does setdefault before this is called
        environ_exporter = os.environ.get(
            OTEL_METRICS_EXPORTER,
        )
        if not environ_exporter:
            logger.debug(
                "No OTEL_METRICS_EXPORTER set, skipping init of metrics exporters"
            )
            return
        environ_exporter_names = environ_exporter.split(",")

        # Report all histograms with delta aggregation, including response_time
        temporality_delta = {Histogram: AggregationTemporality.DELTA}
        metric_readers = []
        for exporter_name in environ_exporter_names:
            exporter = None
            try:
                exporter = next(
                    iter(
                        entry_points(
                            group="opentelemetry_metrics_exporter",
                            name=exporter_name,
                        )
                    )
                ).load()(preferred_temporality=temporality_delta)
            except Exception as ex:
                logger.exception("A exception was raised: %s", ex)
                logger.exception(
                    "Failed to load configured OTEL_METRICS_EXPORTER. "
                    "Please reinstall or contact %s.",
                    INTL_SWO_SUPPORT_EMAIL,
                )
                raise

            logger.debug(
                "Creating PeriodicExportingMetricReader using %s",
                exporter_name,
            )

            reader = None
            if apm_config.is_lambda:
                # Inf interval to not invoke periodic collection
                reader = PeriodicExportingMetricReader(
                    exporter,
                    export_interval_millis=math.inf,
                )
            else:
                # Use default interval 60s else OTEL_METRIC_EXPORT_INTERVAL
                reader = PeriodicExportingMetricReader(
                    exporter,
                )
            metric_readers.append(reader)

        # Use configured Resource attributes then merge with
        # custom service.name and sw.trace_span_mode
        resource = trace.get_tracer_provider().get_tracer(__name__).resource
        sw_resource = Resource.create(
            {
                "sw.apm.version": __version__,
                "sw.data.module": "apm",
                "service.name": apm_config.service_name,
            }
        ).merge(resource)

        provider = MeterProvider(
            resource=sw_resource,
            metric_readers=metric_readers,
        )
        set_meter_provider(provider)

    def _configure_logs_exporter(
        self,
        apm_config: SolarWindsApmConfig,
    ) -> None:
        """Configure OTel OTLP logs exporters if enabled and agent enabled.
        Settings precedence: OTEL_* > SW_APM_EXPORT_LOGS_ENABLED.
        Links to new global LoggerProvider."""
        if not apm_config.agent_enabled:
            logger.error(
                "APM Python library disabled. Cannot set logs exporters."
            )
            return

        otel_ev = os.environ.get(
            _OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED
        )
        otlp_log_enabled = SolarWindsApmConfig.convert_to_bool(otel_ev)
        sw_enabled = apm_config.get("export_logs_enabled")
        if otlp_log_enabled is False:
            logger.debug(
                "OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED false. Skipping init of logs exporters"
            )
            return

        # If otel_ev is True, ignore sw_enabled.
        # If otel_ev is None (unset or could not convert to bool)
        # then sw_enabled determines logs export setup.
        if not otlp_log_enabled and sw_enabled is False:
            logger.debug(
                "APM OTLP logs export disabled. Skipping init of logs exporters"
            )
            return

        # SolarWindsDistro._configure does setdefault before this is called
        environ_exporter = os.environ.get(
            OTEL_LOGS_EXPORTER,
        )
        if not environ_exporter:
            logger.debug(
                "No OTEL_LOGS_EXPORTER set, skipping init of logs exporters"
            )
            return

        environ_exporter_names = environ_exporter.split(",")

        # Use configured Resource attributes then merge with
        # custom service.name and sw.trace_span_mode
        resource = trace.get_tracer_provider().get_tracer(__name__).resource
        sw_resource = Resource.create(
            {
                "sw.apm.version": __version__,
                "sw.data.module": "apm",
                "service.name": apm_config.service_name,
            }
        ).merge(resource)

        logger_provider = LoggerProvider(
            resource=sw_resource,
        )
        set_logger_provider(logger_provider)

        for exporter_name in environ_exporter_names:
            exporter = None
            try:
                exporter = next(
                    iter(
                        entry_points(
                            group="opentelemetry_logs_exporter",
                            name=exporter_name,
                        )
                    )
                ).load()()
            except Exception as ex:
                logger.exception("A exception was raised: %s", ex)
                logger.exception(
                    "Failed to load configured OTEL_LOGS_EXPORTER. "
                    "Please reinstall or contact %s.",
                    INTL_SWO_SUPPORT_EMAIL,
                )
                raise

            logger.debug(
                "Setting logs with BatchLogRecordProcessor using %s",
                exporter_name,
            )
            logs_processor = BatchLogRecordProcessor(exporter)

            logger_provider.add_log_record_processor(logs_processor)

        # Create and attach OTLP handler to root logger
        log_handler = LoggingHandler(
            level=logging.NOTSET,
            logger_provider=logger_provider,
        )
        logging.getLogger().addHandler(log_handler)

    def _configure_propagator(self) -> None:
        """Configure CompositePropagator with SolarWinds and other propagators, default or environment configured"""
        propagators = []

        # SolarWindsDistro._configure does setdefault so this shouldn't
        # be None, but safer and more explicit this way
        environ_propagators_names = os.environ.get(
            OTEL_PROPAGATORS,
            ",".join(INTL_SWO_DEFAULT_PROPAGATORS),
        ).split(",")

        for propagator_name in environ_propagators_names:
            try:
                propagators.append(
                    next(
                        iter(
                            entry_points(
                                group="opentelemetry_propagator",
                                name=propagator_name,
                            )
                        )
                    ).load()()
                )
            except Exception:
                logger.exception(
                    "Failed to load configured propagator %s",
                    propagator_name,
                )
                raise
        logger.debug(
            "Setting CompositePropagator with %s",
            environ_propagators_names,
        )
        set_global_textmap(CompositePropagator(propagators))

    def _configure_response_propagator(self) -> None:
        # Set global HTTP response propagator
        set_global_response_propagator(SolarWindsTraceResponsePropagator())

    def _initialize_solarwinds_reporter(
        self,
        apm_config: SolarWindsApmConfig,
    ) -> "Reporter":
        """Initialize SolarWinds reporter used by sampler and exporter, using SolarWindsApmConfig.
        This establishes collector and sampling settings in a background thread.

        Note: if config's extension is no-op, this has no effect."""
        reporter_kwargs = {
            "hostname_alias": apm_config.get("hostname_alias"),
            "log_type": apm_config.get("log_type"),
            "log_level": apm_config.get("debug_level"),
            "log_file_path": apm_config.get("log_filepath"),
            "max_transactions": apm_config.get("max_transactions"),
            "max_flush_wait_time": apm_config.get("max_flush_wait_time"),
            "events_flush_interval": apm_config.get("events_flush_interval"),
            "max_request_size_bytes": apm_config.get("max_request_size_bytes"),
            "reporter": apm_config.get("reporter"),
            "host": apm_config.get("collector"),
            "service_key": apm_config.get("service_key"),
            "certificates": apm_config.certificates,
            "buffer_size": apm_config.get("bufsize"),
            "trace_metrics": apm_config.get("trace_metrics"),
            "histogram_precision": apm_config.get("histogram_precision"),
            "token_bucket_capacity": -1,  # always unset
            "token_bucket_rate": -1,  # always unset
            "file_single": apm_config.get("reporter_file_single"),
            "ec2_metadata_timeout": apm_config.get("ec2_metadata_timeout"),
            "grpc_proxy": apm_config.get("proxy"),
            "stdout_clear_nonblocking": 0,
            "metric_format": apm_config.metric_format,
        }

        return apm_config.extension.Reporter(**reporter_kwargs)

    # pylint: disable=too-many-branches,too-many-statements
    def _add_all_instrumented_python_framework_versions(
        self,
        version_keys,
    ) -> dict:
        """Updates version_keys with versions of Python frameworks that have been
        instrumented with installed (bootstrapped) OTel instrumentation libraries.
        Borrowed from opentelemetry-instrumentation sitecustomize. Intended for
        creating init event.

        Example output:
        {
            "Python.Urllib.Version": "3.9",
            "Python.Requests.Version": "2.28.1",
            "Python.Django.Version": "4.1.4",
            "Python.Psycopg2.Version": "2.9.5 (dt dec pq3 ext lo64)",
            "Python.Sqlite3.Version": "3.34.1",
            "Python.Logging.Version": "0.5.1.2",
        }
        """
        package_to_exclude = os.environ.get(
            OTEL_PYTHON_DISABLED_INSTRUMENTATIONS, []
        )
        if isinstance(package_to_exclude, str):
            package_to_exclude = package_to_exclude.split(",")
            package_to_exclude = [x.strip() for x in package_to_exclude]

        for entry_point in iter(
            entry_points(group="opentelemetry_instrumentor")
        ):
            if entry_point.name in package_to_exclude:
                logger.debug(
                    "Skipping version lookup for library %s because excluded",
                    entry_point.name,
                )
                continue

            try:
                conflict = get_dist_dependency_conflicts(entry_point.dist)
                if conflict:
                    # TODO Unnecessary tortoiseorm bootstrap will be fixed upstream
                    # https://github.com/open-telemetry/opentelemetry-python-contrib/pull/2409
                    if (
                        "tortoise-orm" in conflict.required
                        and conflict.found is None
                    ):
                        logger.debug(
                            "Init event version lookup for library %s skipped due to known pydantic/tortoiseorm bootstrap conflict: %s",
                            entry_point.name,
                            conflict,
                        )
                    else:
                        logger.debug(
                            "Init event version lookup for library %s skipped due to conflict: %s",
                            entry_point.name,
                            conflict,
                        )
                    continue
            except Exception as ex:  # pylint: disable=broad-except
                logger.debug(
                    "Init event version conflict check of %s failed, so skipping: %s",
                    entry_point.name,
                    ex,
                )
                continue

            # Set up Instrumented Library Versions KVs with several special cases
            entry_point_name = entry_point.name
            # Some OTel instrumentation library entry point names are not exactly
            # the same as their corresponding instrumented libraries
            # https://github.com/open-telemetry/opentelemetry-python-contrib/blob/main/instrumentation/README.md
            if entry_point_name == "aiohttp-client":
                entry_point_name = "aiohttp"
            # Both client/server instrumentors instrument `aiohttp`
            # so key is potentially overwritten, not duplicated
            elif entry_point_name == "aiohttp-server":
                entry_point_name = "aiohttp"
            elif entry_point_name == "aio-pika":
                entry_point_name = "aio_pika"
            elif "grpc_" in entry_point_name:
                entry_point_name = "grpc"
            elif entry_point_name == "system_metrics":
                entry_point_name = "psutil"
            elif entry_point_name == "tortoiseorm":
                entry_point_name = "tortoise"

            # Remove any underscores and convert to UpperCamelCase
            # e.g. aio_pika becomes Python.AioPika.Version
            middle = "".join(
                part.capitalize() for part in entry_point_name.split("_")
            )
            instr_key = f"Python.{middle}.Version"
            try:
                # There is no mysql version, but mysql.connector version
                if entry_point_name == "mysql":
                    importlib.import_module(f"{entry_point_name}.connector")
                # urllib has a rich complex history
                elif entry_point_name == "urllib":
                    importlib.import_module(f"{entry_point_name}.request")
                else:
                    importlib.import_module(entry_point_name)

                # some Python frameworks don't have top-level __version__
                if entry_point_name in self._STDLIB_PKGS:
                    logger.debug(
                        "Using Python version for library %s because part of Python standard library in Python 3.8+",
                        entry_point.name,
                    )
                    version_keys[instr_key] = platform.python_version()
                # elasticsearch gives a version as (8, 5, 3) not 8.5.3
                elif entry_point_name == "elasticsearch":
                    version_tuple = sys.modules[entry_point_name].__version__
                    version_keys[instr_key] = ".".join(
                        [str(d) for d in version_tuple]
                    )
                elif entry_point_name == "mysql":
                    version_keys[instr_key] = sys.modules[
                        f"{entry_point_name}.connector"
                    ].__version__
                elif entry_point_name == "pyramid":
                    version_keys[instr_key] = version(entry_point_name)
                elif entry_point_name == "sqlite3":
                    version_keys[instr_key] = sys.modules[
                        entry_point_name
                    ].sqlite_version
                elif entry_point_name == "tornado":
                    version_keys[instr_key] = sys.modules[
                        entry_point_name
                    ].version
                elif entry_point_name == "urllib":
                    version_keys[instr_key] = sys.modules[
                        f"{entry_point_name}.request"
                    ].__version__
                else:
                    version_keys[instr_key] = sys.modules[
                        entry_point_name
                    ].__version__

            except (AttributeError, ImportError) as ex:
                # could not import package for whatever reason
                logger.warning(
                    "Version lookup of %s failed, so skipping: %s",
                    entry_point_name,
                    ex,
                )

        return version_keys

    # pylint: disable=too-many-locals
    def _create_init_event(
        self,
        reporter: "Reporter",
        apm_config: SolarWindsApmConfig,
        layer: str = "Python",
        keys: dict = None,
    ) -> Any:
        """Create a Reporter init event if the reporter is ready."""
        if apm_config.get("legacy") is False:
            logger.debug("Skipping init event outside legacy mode")
            return None

        reporter_ready = False
        if reporter.init_status in (
            OboeReporterCode.OBOE_INIT_OK,
            OboeReporterCode.OBOE_INIT_ALREADY_INIT,
        ):
            reporter_ready = apm_config.agent_enabled
        if not reporter_ready:
            if apm_config.agent_enabled:
                logger.error(
                    "Failed to initialize the reporter, error code=%s (%s). Not sending init message.",
                    reporter.init_status,
                    OboeReporterCode.get_text_code(reporter.init_status),
                )
            else:
                logger.warning("Agent disabled. Not sending init message.")
            return None

        version_keys = {}
        version_keys["__Init"] = True

        # Use configured Resource attributes to set telemetry.sdk.*
        resource_attributes = (
            trace.get_tracer_provider()
            .get_tracer(__name__)
            .resource.attributes
        )
        for ra_k, ra_v in resource_attributes.items():
            # Do not include OTEL SERVICE_NAME in __Init message
            if ra_k != SERVICE_NAME:
                version_keys[ra_k] = ra_v

        # liboboe adds key Hostname for us
        try:
            version_keys["process.runtime.version"] = (
                f"{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}"
            )
        except (AttributeError, IndexError) as ex:
            logger.warning("Could not retrieve Python version: %s", ex)
        version_keys["process.runtime.name"] = sys.implementation.name
        version_keys["process.runtime.description"] = sys.version
        version_keys["process.executable.path"] = sys.executable

        version_keys["APM.Version"] = __version__
        version_keys["APM.Extension.Version"] = (
            apm_config.extension.Config.getVersionString()
        )

        version_keys = self._add_all_instrumented_python_framework_versions(
            version_keys
        )

        if keys:
            version_keys.update(keys)

        md = apm_config.extension.Metadata.makeRandom(True)
        if not md.isValid():
            logger.warning(
                "Warning: Could not generate Metadata for reporter init. Skipping init message."
            )
            return None
        apm_config.extension.Context.set(md)
        evt = md.createEvent()
        evt.addInfo("Layer", layer)
        for ver_k, ver_v in version_keys.items():
            evt.addInfo(ver_k, ver_v)
        return evt

    def _report_init_event(
        self,
        reporter: "Reporter",
        init_event: "Event",
    ) -> None:
        """Report the APM library's init event message and log its send status."""
        status = reporter.sendStatus(init_event)
        logger.info("Reporter initialized successfully: %s", status)

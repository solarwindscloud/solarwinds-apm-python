# © 2023 SolarWinds Worldwide, LLC. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at:http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

import pytest

# ==================================================================
# Configurator stdlib fixtures
# ==================================================================

@pytest.fixture(name="mock_sys")
def mock_sys(mocker):
    mock_version_info = mocker.PropertyMock()
    mock_version_info.return_value = [3, 11, 12]
    mock_version = mocker.PropertyMock()
    mock_version.return_value = "foo-runtime"
    mock_exec = mocker.PropertyMock()
    mock_exec.return_value = "/foo/path"

    mock_sys = mocker.patch(
        "solarwinds_apm.configurator.sys"
    )
    type(mock_sys).version_info = mock_version_info
    type(mock_sys).version = mock_version
    type(mock_sys).executable = mock_exec
    type(mock_sys).implementation = mocker.PropertyMock()
    type(mock_sys).implementation.name = "foo-name"

    return mock_sys

@pytest.fixture(name="mock_sys_error_version_info")
def mock_sys_error_version_info(mocker):
    mock_version_info = mocker.PropertyMock()
    mock_version_info.return_value = []
    mock_version = mocker.PropertyMock()
    mock_version.return_value = "foo-runtime"
    mock_exec = mocker.PropertyMock()
    mock_exec.return_value = "/foo/path"

    mock_sys = mocker.patch(
        "solarwinds_apm.configurator.sys"
    )
    type(mock_sys).version_info = mock_version_info
    type(mock_sys).version = mock_version
    type(mock_sys).executable = mock_exec
    type(mock_sys).implementation = mocker.PropertyMock()
    type(mock_sys).implementation.name = "foo-name"

    return mock_sys

# ==================================================================
# Configurator Otel fixtures
# ==================================================================

@pytest.fixture(name="mock_set_global_textmap")
def mock_set_global_textmap(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.set_global_textmap",
    )

@pytest.fixture(name="mock_set_global_response_propagator")
def mock_set_global_response_propagator(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.set_global_response_propagator",
    )

@pytest.fixture(name="mock_composite_propagator")
def mock_composite_propagator(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.CompositePropagator",
    )

@pytest.fixture(name="mock_bsprocessor")
def mock_bsprocessor(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.BatchSpanProcessor",
    )

@pytest.fixture(name="mock_ssprocessor")
def mock_ssprocessor(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SimpleSpanProcessor",
    )

@pytest.fixture(name="mock_pemreader")
def mock_pemreader(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.PeriodicExportingMetricReader",
    )

@pytest.fixture(name="mock_blprocessor")
def mock_blprocessor(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.BatchLogRecordProcessor",
    )

@pytest.fixture(name="mock_tracerprovider")
def mock_tracerprovider(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.TracerProvider"
    )

@pytest.fixture(name="mock_meterprovider")
def mock_meterprovider(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.MeterProvider",
    )

@pytest.fixture(name="mock_loggerprovider")
def mock_loggerprovider(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.LoggerProvider",
    )

@pytest.fixture(name="mock_logginghandler")
def mock_logginghandler(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.LoggingHandler",
    )

# ==================================================================
# Configurator APM Python ApmConfig mocks
# ==================================================================

def get_apmconfig_mocks(
    mocker,
    enabled=True,
    is_lambda=False,
    md_is_valid=True,
    export_logs_enabled=True,
    export_metrics_enabled=True,
    legacy=False,
):
    # mock the extension that is linked to ApmConfig
    mock_ext_config = mocker.Mock()
    mock_ext_config.configure_mock(
        **{
            "getVersionString": mocker.Mock(return_value="1.1.1")
        }
    )

    mock_ext_context = mocker.Mock()
    mock_ext_context.configure_mock(
        **{
            "set": mocker.Mock()
        }
    )

    mock_event = mocker.Mock()
    mock_event.configure_mock(
        **{
            "addInfo": mocker.Mock()
        }
    )
    mock_create_event = mocker.Mock(return_value=mock_event)

    mock_make_random = mocker.Mock()
    mock_make_random.configure_mock(
        **{
            "isValid": mocker.Mock(return_value=md_is_valid),
            "createEvent": mock_create_event
        }
    )

    mock_ext_metadata = mocker.Mock()
    mock_ext_metadata.configure_mock(
        **{
            "makeRandom": mock_make_random
        }
    )

    mock_ext = mocker.Mock()
    mock_ext.configure_mock(
        **{
            "Config": mock_ext_config,
            "Context": mock_ext_context,
            "Metadata": mock_ext_metadata,
        }
    )

    def get_side_effect(param):
        if param == "export_metrics_enabled":
            return export_metrics_enabled
        elif param == "export_logs_enabled":
            return export_logs_enabled
        elif param == "legacy":
            return legacy
        else:
            return "foo"

    mock_apmconfig = mocker.Mock()
    mock_apmconfig.configure_mock(
        **{
            "agent_enabled": enabled,
            "get": mocker.Mock(side_effect=get_side_effect),
            "service_name": "foo-service",
            "is_lambda": is_lambda,
            "extension": mock_ext,
            "oboe_api": mocker.Mock(),
        }
    )
    return mock_apmconfig

@pytest.fixture(name="mock_apmconfig_disabled")
def mock_apmconfig_disabled(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsApmConfig",
        get_apmconfig_mocks(
            mocker,
            enabled=False,
        )
    )

@pytest.fixture(name="mock_apmconfig_enabled")
def mock_apmconfig_enabled(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsApmConfig",
        get_apmconfig_mocks(
            mocker,
        )
    )

@pytest.fixture(name="mock_apmconfig_enabled_legacy")
def mock_apmconfig_enabled_legacy(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsApmConfig",
        get_apmconfig_mocks(
            mocker,
            legacy=True,
        )
    )

@pytest.fixture(name="mock_apmconfig_enabled_md_invalid")
def mock_apmconfig_enabled_md_invalid(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsApmConfig",
        get_apmconfig_mocks(
            mocker,
            md_is_valid=False,
            legacy=True,
        )
    )

@pytest.fixture(name="mock_apmconfig_enabled_is_lambda")
def mock_apmconfig_enabled_is_lambda(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsApmConfig",
        get_apmconfig_mocks(
            mocker,
            is_lambda=True,
        )
    )

@pytest.fixture(name="mock_apmconfig_logs_enabled_false")
def mock_apmconfig_logs_enabled_false(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsApmConfig",
        get_apmconfig_mocks(
            mocker,
            export_logs_enabled=False
        )
    )

@pytest.fixture(name="mock_apmconfig_logs_enabled_none")
def mock_apmconfig_logs_enabled_none(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsApmConfig",
        get_apmconfig_mocks(
            mocker,
            export_logs_enabled=None
        )
    )

@pytest.fixture(name="mock_apmconfig_metrics_enabled_false")
def mock_apmconfig_metrics_enabled_false(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsApmConfig",
        get_apmconfig_mocks(
            mocker,
            export_metrics_enabled=False,
        )
    )

@pytest.fixture(name="mock_apmconfig_metrics_enabled_none")
def mock_apmconfig_metrics_enabled_none(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsApmConfig",
        get_apmconfig_mocks(
            mocker,
            export_metrics_enabled=None,
        )
    )

@pytest.fixture(name="mock_apmconfig_enabled_reporter_settings")
def mock_apmconfig_enabled_reporter_settings(mocker):
    mock_reporter = mocker.Mock()
    mock_ext = mocker.Mock()
    mock_ext.configure_mock(
        **{
            "Reporter": mock_reporter
        }
    )

    mock_apmconfig = mocker.Mock()
    mock_apmconfig.configure_mock(
        **{
            "agent_enabled": True,
            "certificates": "foo-certs",
            "extension": mock_ext,
            "get": mocker.Mock(return_value="foo"),
            "service_name": "foo-service",
            "metric_format": "bar"
        }
    )
    return mock_apmconfig

# ==================================================================
# Configurator APM Python extension mocks
# ==================================================================

def get_extension_mocks(
    mocker,
    status_code=0,
):
    mock_reporter = mocker.Mock()
    mock_reporter.configure_mock(
        **{
            "init_status": status_code,
            "sendStatus": mocker.Mock()
        }
    )

    mock_ext = mocker.Mock()
    mock_ext.configure_mock(
        **{
            "Reporter": mock_reporter
        }
    )
    return mock_ext

@pytest.fixture(name="mock_extension")
def mock_extension(mocker):
    return get_extension_mocks(mocker)

@pytest.fixture(name="mock_extension_status_code_already_init")
def mock_extension_status_code_already_init(mocker):
    return get_extension_mocks(mocker, -1)

@pytest.fixture(name="mock_extension_status_code_invalid_protocol")
def mock_extension_status_code_invalid_protocol(mocker):
    return get_extension_mocks(mocker, 2)

# ==================================================================
# Configurator APM Python configurator mocks
# ==================================================================

def add_fw_versions(input_dict):
    input_dict.update({"foo-fw": "bar-version"})
    return input_dict

@pytest.fixture(name="mock_fw_versions")
def mock_fw_versions(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsConfigurator._add_all_instrumented_python_framework_versions",
        side_effect=add_fw_versions
    )

@pytest.fixture(name="mock_config_serviceentryid_processor")
def mock_config_serviceentryid_processor(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsConfigurator._configure_service_entry_id_span_processor"
    )

@pytest.fixture(name="mock_config_inbound_processor")
def mock_config_inbound_processor(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsConfigurator._configure_inbound_metrics_span_processor"
    )

@pytest.fixture(name="mock_config_otlp_processors")
def mock_config_otlp_processors(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsConfigurator._configure_otlp_metrics_span_processors"
    )

@pytest.fixture(name="mock_config_traces_exp")
def mock_config_traces_exp(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsConfigurator._configure_traces_exporter"
    )

@pytest.fixture(name="mock_config_metrics_exp")
def mock_config_metrics_exp(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsConfigurator._configure_metrics_exporter"
    )

@pytest.fixture(name="mock_config_logs_exp")
def mock_config_logs_exp(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsConfigurator._configure_logs_exporter"
    )

@pytest.fixture(name="mock_config_propagator")
def mock_config_propagator(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsConfigurator._configure_propagator"
    )

@pytest.fixture(name="mock_config_response_propagator")
def mock_config_response_propagator(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsConfigurator._configure_response_propagator"
    )

@pytest.fixture(name="mock_init_sw_reporter")
def mock_init_sw_reporter(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsConfigurator._initialize_solarwinds_reporter"
    )

@pytest.fixture(name="mock_config_otel_components")
def mock_config_otel_components(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsConfigurator._configure_otel_components"
    )

@pytest.fixture(name="mock_create_init")
def mock_create_init(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsConfigurator._create_init_event"
    )

@pytest.fixture(name="mock_create_init_fail")
def mock_create_init_fail(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsConfigurator._create_init_event",
        return_value=None,
    )

@pytest.fixture(name="mock_report_init")
def mock_report_init(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsConfigurator._report_init_event"
    )


@pytest.fixture(name="mock_txn_name_manager_init")
def mock_txn_name_manager_init(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsTxnNameManager"
    )

@pytest.fixture(name="mock_fwkv_manager_init")
def mock_fwkv_manager_init(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.SolarWindsFrameworkKvManager"
    )

@pytest.fixture(name="mock_oboe_api_obj")
def mock_oboe_api_obj(mocker):
    return mocker.Mock()


# ==================================================================
# Configurator APM Python other mocks
# ==================================================================

@pytest.fixture(name="mock_apm_version")
def mock_apm_version(mocker):
    return mocker.patch(
        "solarwinds_apm.configurator.__version__",
        new="0.0.0",
    )

@pytest.fixture(name="mock_fwkv_manager")
def mock_fwkv_manager(mocker):
    return mocker.patch(
        "solarwinds_apm.apm_fwkv_manager.SolarWindsFrameworkKvManager"
    )

@pytest.fixture(name="mock_meter_manager")
def mock_meter_manager(mocker):
    return mocker.patch(
        "solarwinds_apm.apm_meter_manager.SolarWindsMeterManager"
    )

@pytest.fixture(name="mock_txn_name_manager")
def mock_txn_name_manager(mocker):
    return mocker.patch(
        "solarwinds_apm.apm_txname_manager.SolarWindsTxnNameManager"
    )
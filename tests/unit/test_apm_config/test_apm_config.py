# © 2023 SolarWinds Worldwide, LLC. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at:http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

import logging
import os
import pytest

from opentelemetry.sdk.resources import Resource

from solarwinds_apm import apm_config
from solarwinds_apm.apm_constants import (
    INTL_SWO_AO_COLLECTOR,
    INTL_SWO_AO_STG_COLLECTOR,
)

# pylint: disable=unused-import
from .fixtures.env_vars import fixture_mock_env_vars

@pytest.fixture
def setup_caplog():
    apm_logger = logging.getLogger("solarwinds_apm")
    apm_logger.propagate = True


class TestSolarWindsApmConfig:
    """
    Note: mock_env_vars test fixture sets values for OTEL_PROPAGATORS
    and OTEL_TRACES_EXPORTER. SW_APM_SERVICE_KEY is required.
    SW_APM_AGENT_ENABLED is optional.
    """

    @pytest.fixture(autouse=True)
    def before_and_after_each(self):
        # Save any env vars for later just in case
        old_service_key = os.environ.get("SW_APM_SERVICE_KEY", None)
        if old_service_key:
            del os.environ["SW_APM_SERVICE_KEY"]
        old_env_lambda_name = os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
        if old_env_lambda_name:
            del os.environ["AWS_LAMBDA_FUNCTION_NAME"]
        old_env_trans_name = os.environ.get("SW_APM_TRANSACTION_NAME")
        if old_env_trans_name:
            del os.environ["SW_APM_TRANSACTION_NAME"]
        old_debug_level = os.environ.get("SW_APM_DEBUG_LEVEL")
        if old_debug_level:
            del os.environ["SW_APM_DEBUG_LEVEL"]
        old_log_type = os.environ.get("SW_APM_LOG_TYPE")
        if old_log_type:
            del os.environ["SW_APM_LOG_TYPE"]
        old_collector = os.environ.get("SW_APM_COLLECTOR", None)
        if old_collector:
            del os.environ["SW_APM_COLLECTOR"]
        old_trustedpath = os.environ.get("SW_APM_TRUSTEDPATH", None)
        if old_trustedpath:
            del os.environ["SW_APM_TRUSTEDPATH"]
        old_expt_logs = os.environ.get("SW_APM_EXPORT_LOGS_ENABLED", None)
        if old_expt_logs:
            del os.environ["SW_APM_EXPORT_LOGS_ENABLED"]
        old_expt_metrics = os.environ.get("SW_APM_EXPORT_METRICS_ENABLED", None)
        if old_expt_metrics:
            del os.environ["SW_APM_EXPORT_METRICS_ENABLED"]

        # Wait for test
        yield

        # Restore old env vars
        if old_service_key:
            os.environ["SW_APM_SERVICE_KEY"] = old_service_key
        if old_env_lambda_name:
            os.environ["AWS_LAMBDA_FUNCTION_NAME"] = old_env_lambda_name
        if old_env_trans_name:
            os.environ["SW_APM_TRANSACTION_NAME"] = old_env_trans_name
        if old_debug_level:
            os.environ["SW_APM_DEBUG_LEVEL"] = old_debug_level
        if old_log_type:
            os.environ["SW_APM_LOG_TYPE"] = old_log_type
        if old_collector:
            os.environ["SW_APM_COLLECTOR"] = old_collector
        if old_trustedpath:
            os.environ["SW_APM_TRUSTEDPATH"] = old_trustedpath
        if old_expt_logs:
            os.environ["SW_APM_EXPORT_LOGS_ENABLED"] = old_expt_logs
        if old_expt_metrics:
            os.environ["SW_APM_EXPORT_METRICS_ENABLED"] = old_expt_metrics

    def _mock_service_key(self, mocker, service_key):
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": service_key,
        })
        mock_entry_points = mocker.patch(
            "solarwinds_apm.apm_config.entry_points"
        )
        mock_points = mocker.MagicMock()
        mock_points.__iter__.return_value = ["foo"]
        mock_entry_points.configure_mock(
            return_value=mock_points
        )

    def test__init_invalid_service_key_format(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": "incorrect_format",
        })
        test_config = apm_config.SolarWindsApmConfig()
        assert not test_config.agent_enabled
        assert test_config.service_name == ""
        assert test_config.get("service_key") == "incorrect_format"

    def test__init_invalid_service_key_format_otel_service_name_and_resource_attrs(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": "incorrect_format",
            "OTEL_SERVICE_NAME": "wont_be_used",
            "OTEL_RESOURCE_ATTRIBUTES": "service.name=also_unused"
        })
        test_config = apm_config.SolarWindsApmConfig()
        assert not test_config.agent_enabled
        assert test_config.service_name == ""
        assert test_config.get("service_key") == "incorrect_format"

    def test__init_valid_service_key_format_agent_enabled_false(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": "service_key_with:sw_service_name",
            "SW_APM_AGENT_ENABLED": "false",
        })
        test_config = apm_config.SolarWindsApmConfig()
        assert not test_config.agent_enabled
        assert test_config.service_name == ""
        assert test_config.get("service_key") == "service_key_with:sw_service_name"

    def test__init_valid_service_key_format_agent_enabled_true_default(
        self,
        mocker,
        mock_env_vars,
    ):
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": "service_key_with:sw_service_name",
        })
        test_config = apm_config.SolarWindsApmConfig()
        assert test_config.agent_enabled
        assert test_config.service_name == "sw_service_name"
        assert test_config.get("service_key") == "service_key_with:sw_service_name"

    def test__init_valid_service_key_format_agent_enabled_true_explicit(
        self,
        mocker,
        mock_env_vars,
    ):
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": "service_key_with:sw_service_name",
            "SW_APM_AGENT_ENABLED": "true",
        })
        test_config = apm_config.SolarWindsApmConfig()
        assert test_config.agent_enabled
        assert test_config.service_name == "sw_service_name"
        assert test_config.get("service_key") == "service_key_with:sw_service_name"

    def test__init_valid_service_key_format_otel_service_name(
        self,
        mocker,
        mock_env_vars,
    ):
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": "service_key_with:sw_service_name",
            "OTEL_SERVICE_NAME": "from_otel_env"
        })
        # Otel picks up os mock if Resource.create here (same as default arg)
        test_config = apm_config.SolarWindsApmConfig(Resource.create())
        assert test_config.agent_enabled
        assert test_config.service_name == "from_otel_env"
        assert test_config.get("service_key") == "service_key_with:from_otel_env"

    def test__init_valid_service_key_format_otel_service_name_and_resource_attrs(
        self,
        mocker,
        mock_env_vars,
    ):
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": "service_key_with:sw_service_name",
            "OTEL_SERVICE_NAME": "from_otel_env",
            "OTEL_RESOURCE_ATTRIBUTES": "service.name=also_from_otel_env_unused"
        })
        # Otel picks up os mock if Resource.create here (same as default arg)
        test_config = apm_config.SolarWindsApmConfig(Resource.create())
        assert test_config.agent_enabled
        assert test_config.service_name == "from_otel_env"
        assert test_config.get("service_key") == "service_key_with:from_otel_env"

    def test__init_valid_service_key_format_otel_resource_attrs(
        self,
        mocker,
        mock_env_vars,
    ):
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": "service_key_with:sw_service_name",
            "OTEL_RESOURCE_ATTRIBUTES": "service.name=also_from_otel_env_used_this_time"
        })
        # Otel picks up os mock if Resource.create here (same as default arg)
        test_config = apm_config.SolarWindsApmConfig(Resource.create())
        assert test_config.agent_enabled
        assert test_config.service_name == "also_from_otel_env_used_this_time"
        assert test_config.get("service_key") == "service_key_with:also_from_otel_env_used_this_time"

    def test__init_valid_service_key_format_empty_otel_service_name(
        self,
        mocker,
        mock_env_vars,
    ):
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": "service_key_with:sw_service_name",
            "OTEL_SERVICE_NAME": "",
        })
        # Otel picks up os mock if Resource.create here (same as default arg)
        test_config = apm_config.SolarWindsApmConfig(Resource.create())
        assert test_config.agent_enabled
        assert test_config.service_name == "sw_service_name"
        assert test_config.get("service_key") == "service_key_with:sw_service_name"

    def test__init_valid_service_key_format_empty_otel_service_name_and_resource_attrs(
        self,
        mocker,
        mock_env_vars,
    ):
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": "service_key_with:sw_service_name",
            "OTEL_SERVICE_NAME": "",
            "OTEL_RESOURCE_ATTRIBUTES": "",
        })
        # Otel picks up os mock if Resource.create here (same as default arg)
        test_config = apm_config.SolarWindsApmConfig(Resource.create())
        assert test_config.agent_enabled
        assert test_config.service_name == "sw_service_name"
        assert test_config.get("service_key") == "service_key_with:sw_service_name"

    def test__init_valid_service_key_format_otel_resource_attrs_without_name(
        self,
        mocker,
        mock_env_vars,
    ):
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": "service_key_with:sw_service_name",
            "OTEL_RESOURCE_ATTRIBUTES": "foo=bar,telemetry.sdk.version=whatever-i-want-baby",
        })
        # Otel picks up os mock if Resource.create here (same as default arg)
        test_config = apm_config.SolarWindsApmConfig(Resource.create())
        assert test_config.agent_enabled
        assert test_config.service_name == "sw_service_name"
        assert test_config.get("service_key") == "service_key_with:sw_service_name"

    def test__init_custom_transction_names_env_vars(self, mocker):
        mocker.patch.dict(
            os.environ,
            {
                "AWS_LAMBDA_FUNCTION_NAME": "foo-lambda",
                "SW_APM_TRANSACTION_NAME": "foo-trans-name",
            },
        )

        config = apm_config.SolarWindsApmConfig()
        assert config.lambda_function_name == "foo-lambda"
        assert config.get("transaction_name") == "foo-trans-name"

    def test__init_oboe_api_and_options_defaults(self, mocker):
        mock_level = mocker.PropertyMock()
        mock_type = mocker.PropertyMock()
        mock_logging_options = mocker.Mock()
        type(mock_logging_options).level = mock_level
        type(mock_logging_options).type = mock_type

        mock_oboe_api_options_obj = mocker.Mock()
        type(mock_oboe_api_options_obj).logging_options = mock_logging_options

        mock_oboe_api_options_swig = mocker.Mock(
            return_value=mock_oboe_api_options_obj
        )
        mock_oboe_api_swig = mocker.Mock()
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig._get_extension_components",
            return_value=(
                "unused",
                mocker.Mock(),
                mock_oboe_api_swig,
                mock_oboe_api_options_swig,
            )
        )

        apm_config.SolarWindsApmConfig()
        mock_oboe_api_options_swig.assert_called_once()
        # default values used
        mock_level.assert_called_once_with(2)
        mock_type.assert_called_once_with(0)
        mock_oboe_api_swig.assert_called_once()

    def test__init_oboe_api_and_options_configured_invalid(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_DEBUG_LEVEL": "not-valid",
            "SW_APM_LOG_TYPE": "nor-this",
        })

        mock_level = mocker.PropertyMock()
        mock_type = mocker.PropertyMock()
        mock_logging_options = mocker.Mock()
        type(mock_logging_options).level = mock_level
        type(mock_logging_options).type = mock_type

        mock_oboe_api_options_obj = mocker.Mock()
        type(mock_oboe_api_options_obj).logging_options = mock_logging_options

        mock_oboe_api_options_swig = mocker.Mock(
            return_value=mock_oboe_api_options_obj
        )
        mock_oboe_api_swig = mocker.Mock()
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig._get_extension_components",
            return_value=(
                "unused",
                mocker.Mock(),
                mock_oboe_api_swig,
                mock_oboe_api_options_swig,
            )
        )

        apm_config.SolarWindsApmConfig()
        mock_oboe_api_options_swig.assert_called_once()
        # default values used instead
        mock_level.assert_called_once_with(2)
        mock_type.assert_called_once_with(0)
        mock_oboe_api_swig.assert_called_once()

    def test__init_oboe_api_and_options_configured_valid(self, mocker):
        # Save any debug_level, log_type env var for later
        mocker.patch.dict(os.environ, {
            "SW_APM_DEBUG_LEVEL": "6",
            "SW_APM_LOG_TYPE": "1",
        })

        mock_level = mocker.PropertyMock()
        mock_type = mocker.PropertyMock()
        mock_logging_options = mocker.Mock()
        type(mock_logging_options).level = mock_level
        type(mock_logging_options).type = mock_type

        mock_oboe_api_options_obj = mocker.Mock()
        type(mock_oboe_api_options_obj).logging_options = mock_logging_options

        mock_oboe_api_options_swig = mocker.Mock(
            return_value=mock_oboe_api_options_obj
        )
        mock_oboe_api_swig = mocker.Mock()
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig._get_extension_components",
            return_value=(
                "unused",
                mocker.Mock(),
                mock_oboe_api_swig,
                mock_oboe_api_options_swig,
            )
        )
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.update_log_settings"
        )

        apm_config.SolarWindsApmConfig()
        mock_oboe_api_options_swig.assert_called_once()
        mock_level.assert_called_once_with(6)
        mock_type.assert_called_once_with(1)
        mock_oboe_api_swig.assert_called_once()

    def test__init_ao_settings_helpers_called(self, mocker):
        mock_metric_format = mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig._calculate_metric_format"
        )
        mock_certs = mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig._calculate_certificates"
        )
        mock_logs_enabled = mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig._calculate_logs_enabled"
        )

        apm_config.SolarWindsApmConfig()
        mock_metric_format.assert_called_once()
        mock_certs.assert_called_once()
        mock_logs_enabled.assert_called_once()

    def test_calculate_metric_format_no_collector(self, mocker):
        assert apm_config.SolarWindsApmConfig()._calculate_metric_format() == 2

    def test_calculate_metric_format_not_ao(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": "foo-collector-not-ao"
        })
        assert apm_config.SolarWindsApmConfig()._calculate_metric_format() == 2

    def test_calculate_metric_format_ao_prod(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": INTL_SWO_AO_COLLECTOR
        })
        assert apm_config.SolarWindsApmConfig()._calculate_metric_format() == 1

    def test_calculate_metric_format_ao_staging(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": INTL_SWO_AO_STG_COLLECTOR
        })
        assert apm_config.SolarWindsApmConfig()._calculate_metric_format() == 1

    def test_calculate_metric_format_ao_prod_with_port(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": "{}:123".format(INTL_SWO_AO_COLLECTOR)
        })
        assert apm_config.SolarWindsApmConfig()._calculate_metric_format() == 1

    def test_calculate_certificates_no_collector(self):
        # Save any collector and trustedpath in os for later
        assert apm_config.SolarWindsApmConfig()._calculate_certificates() == ""

    def test_calculate_certificates_not_ao(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": "foo-collector-not-ao"
        })
        assert apm_config.SolarWindsApmConfig()._calculate_certificates() == ""

    def test_calculate_certificates_ao_prod_no_trustedpath(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": INTL_SWO_AO_COLLECTOR
        })
        mock_get_public_cert = mocker.patch(
            "solarwinds_apm.apm_config.get_public_cert"
        )
        mock_get_public_cert.configure_mock(return_value="foo")
        assert apm_config.SolarWindsApmConfig()._calculate_certificates() == "foo"

    def test_calculate_certificates_ao_staging_no_trustedpath(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": INTL_SWO_AO_STG_COLLECTOR
        })
        mock_get_public_cert = mocker.patch(
            "solarwinds_apm.apm_config.get_public_cert"
        )
        mock_get_public_cert.configure_mock(return_value="foo")
        assert apm_config.SolarWindsApmConfig()._calculate_certificates() == "foo"

    def test_calculate_certificates_ao_prod_with_port_no_trustedpath(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": "{}:123".format(INTL_SWO_AO_COLLECTOR)
        })
        mock_get_public_cert = mocker.patch(
            "solarwinds_apm.apm_config.get_public_cert"
        )
        mock_get_public_cert.configure_mock(return_value="foo")
        assert apm_config.SolarWindsApmConfig()._calculate_certificates() == "foo"

    def test_calculate_certificates_not_ao_trustedpath_file_missing(self, mocker):
        """Non-AO collector, trustedpath set, but file missing --> use empty string"""
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": "foo-collector-not-ao",
            "SW_APM_TRUSTEDPATH": "/no/file/here"
        })
        mock_read_text = mocker.Mock()
        mock_read_text.side_effect = FileNotFoundError("no file there")
        mock_pathlib_path = mocker.Mock()
        mock_pathlib_path.configure_mock(
            **{
                "read_text": mock_read_text
            }
        )
        mocker.patch("solarwinds_apm.apm_config.Path").configure_mock(return_value=mock_pathlib_path)
        mock_get_public_cert = mocker.patch(
            "solarwinds_apm.apm_config.get_public_cert"
        )
        mock_get_public_cert.configure_mock(return_value="foo")
        assert apm_config.SolarWindsApmConfig()._calculate_certificates() == ""

    def test_calculate_certificates_ao_prod_trustedpath_file_missing(self, mocker):
        """AO collector, trustedpath set, but file missing --> use bundled cert"""
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": INTL_SWO_AO_COLLECTOR,
            "SW_APM_TRUSTEDPATH": "/no/file/here"
        })
        mock_read_text = mocker.Mock()
        mock_read_text.side_effect = FileNotFoundError("no file there")
        mock_pathlib_path = mocker.Mock()
        mock_pathlib_path.configure_mock(
            **{
                "read_text": mock_read_text
            }
        )
        mocker.patch("solarwinds_apm.apm_config.Path").configure_mock(return_value=mock_pathlib_path)
        mock_get_public_cert = mocker.patch(
            "solarwinds_apm.apm_config.get_public_cert"
        )
        mock_get_public_cert.configure_mock(return_value="foo")
        assert apm_config.SolarWindsApmConfig()._calculate_certificates() == "foo"

    def test_calculate_certificates_not_ao_trustedpath_file_present(self, mocker):
        """Note: if file exists, same behaviour if file contains valid cert or not"""
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": "foo-collector-not-ao",
            "SW_APM_TRUSTEDPATH": "/there/is/a/file/here"
        })
        mock_read_text = mocker.Mock()
        mock_read_text.configure_mock(return_value="bar")
        mock_pathlib_path = mocker.Mock()
        mock_pathlib_path.configure_mock(
            **{
                "read_text": mock_read_text
            }
        )
        mocker.patch("solarwinds_apm.apm_config.Path").configure_mock(return_value=mock_pathlib_path)
        mock_get_public_cert = mocker.patch(
            "solarwinds_apm.apm_config.get_public_cert"
        )
        mock_get_public_cert.configure_mock(return_value="foo")
        assert apm_config.SolarWindsApmConfig()._calculate_certificates() == "bar"

    def test_calculate_certificates_ao_prod_trustedpath_file_present(self, mocker):
        """Note: if file exists, same behaviour if file contains valid cert or not"""
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": INTL_SWO_AO_COLLECTOR,
            "SW_APM_TRUSTEDPATH": "/there/is/a/file/here"
        })
        mock_read_text = mocker.Mock()
        mock_read_text.configure_mock(return_value="bar")
        mock_pathlib_path = mocker.Mock()
        mock_pathlib_path.configure_mock(
            **{
                "read_text": mock_read_text
            }
        )
        mocker.patch("solarwinds_apm.apm_config.Path").configure_mock(return_value=mock_pathlib_path)
        mock_get_public_cert = mocker.patch(
            "solarwinds_apm.apm_config.get_public_cert"
        )
        mock_get_public_cert.configure_mock(return_value="foo")
        assert apm_config.SolarWindsApmConfig()._calculate_certificates() == "bar"

    def test_calculate_logs_enabled_no_collector_enabled(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": "",
            "SW_APM_EXPORT_LOGS_ENABLED": "true",
        })
        assert apm_config.SolarWindsApmConfig()._calculate_logs_enabled() == True

    def test_calculate_logs_enabled_no_collector_disabled(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": "",
            "SW_APM_EXPORT_LOGS_ENABLED": "false",
        })
        assert apm_config.SolarWindsApmConfig()._calculate_logs_enabled() == False

    def test_calculate_logs_enabled_not_ao_enabled(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": "some-other-collector",
            "SW_APM_EXPORT_LOGS_ENABLED": "true",
        })
        assert apm_config.SolarWindsApmConfig()._calculate_logs_enabled() == True

    def test_calculate_logs_enabled_not_ao_disabled(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": "some-other-collector",
            "SW_APM_EXPORT_LOGS_ENABLED": "false",
        })
        assert apm_config.SolarWindsApmConfig()._calculate_logs_enabled() == False

    def test_calculate_logs_enabled_ao_prod(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": INTL_SWO_AO_COLLECTOR,
            "SW_APM_EXPORT_LOGS_ENABLED": "true",
        })
        assert apm_config.SolarWindsApmConfig()._calculate_logs_enabled() == False

    def test_calculate_logs_enabled_ao_staging(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": INTL_SWO_AO_STG_COLLECTOR,
            "SW_APM_EXPORT_LOGS_ENABLED": "true",
        })
        assert apm_config.SolarWindsApmConfig()._calculate_logs_enabled() == False

    def test_calculate_logs_enabled_ao_prod_with_port(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": "{}:123".format(INTL_SWO_AO_COLLECTOR),
            "SW_APM_EXPORT_LOGS_ENABLED": "true",
        })
        assert apm_config.SolarWindsApmConfig()._calculate_logs_enabled() == False

    def test_calculate_metrics_enabled_no_collector_enabled(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": "",
            "SW_APM_EXPORT_METRICS_ENABLED": "true",
        })
        assert apm_config.SolarWindsApmConfig()._calculate_metrics_enabled() == True

    def test_calculate_metrics_enabled_no_collector_disabled(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": "",
            "SW_APM_EXPORT_METRICS_ENABLED": "false",
        })
        assert apm_config.SolarWindsApmConfig()._calculate_metrics_enabled() == False

    def test_calculate_metrics_enabled_not_ao_enabled(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": "some-other-collector",
            "SW_APM_EXPORT_METRICS_ENABLED": "true",
        })
        assert apm_config.SolarWindsApmConfig()._calculate_metrics_enabled() == True

    def test_calculate_metrics_enabled_not_ao_disabled(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": "some-other-collector",
            "SW_APM_EXPORT_METRICS_ENABLED": "false",
        })
        assert apm_config.SolarWindsApmConfig()._calculate_metrics_enabled() == False

    def test_calculate_metrics_enabled_ao_prod(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": INTL_SWO_AO_COLLECTOR,
            "SW_APM_EXPORT_METRICS_ENABLED": "true",
        })
        assert apm_config.SolarWindsApmConfig()._calculate_metrics_enabled() == False

    def test_calculate_metrics_enabled_ao_staging(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": INTL_SWO_AO_STG_COLLECTOR,
            "SW_APM_EXPORT_METRICS_ENABLED": "true",
        })
        assert apm_config.SolarWindsApmConfig()._calculate_metrics_enabled() == False

    def test_calculate_metrics_enabled_ao_prod_with_port(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_COLLECTOR": "{}:123".format(INTL_SWO_AO_COLLECTOR),
            "SW_APM_EXPORT_METRICS_ENABLED": "true",
        })
        assert apm_config.SolarWindsApmConfig()._calculate_metrics_enabled() == False

    def test_mask_service_key_no_key_empty_default(self, mocker):
        mock_entry_points = mocker.patch(
            "solarwinds_apm.apm_config.entry_points"
        )
        mock_points = mocker.MagicMock()
        mock_points.__iter__.return_value = ["foo"]
        mock_entry_points.configure_mock(
            return_value=mock_points
        )
        assert apm_config.SolarWindsApmConfig().mask_service_key() == ""

    def test_mask_service_key_empty_key(self, mocker):
        self._mock_service_key(mocker, "")
        assert apm_config.SolarWindsApmConfig().mask_service_key() == ""

    def test_mask_service_key_whitespace_key(self, mocker):
        self._mock_service_key(mocker, " ")
        assert apm_config.SolarWindsApmConfig().mask_service_key() == " "

    def test_mask_service_key_invalid_format_no_colon(self, mocker):
        self._mock_service_key(mocker, "a")
        assert apm_config.SolarWindsApmConfig().mask_service_key() == "a<invalid_format>"
        self._mock_service_key(mocker, "abcd")
        assert apm_config.SolarWindsApmConfig().mask_service_key() == "abcd<invalid_format>"
        self._mock_service_key(mocker, "abcde")
        assert apm_config.SolarWindsApmConfig().mask_service_key() == "abcd...<invalid_format>"
        self._mock_service_key(mocker, "abcdefgh")
        assert apm_config.SolarWindsApmConfig().mask_service_key() == "abcd...<invalid_format>"
        self._mock_service_key(mocker, "abcd1efgh")
        assert apm_config.SolarWindsApmConfig().mask_service_key() == "abcd...<invalid_format>"
        self._mock_service_key(mocker, "CyUuit1W--8RVmUXX6_cVjTWemaUyBh1ruL0nMPiFdrPo1iiRnO31_pwiUCPzdzv9UMHK6I")
        assert apm_config.SolarWindsApmConfig().mask_service_key() == "CyUu...<invalid_format>"

    def test_mask_service_key_less_than_9_char_token(
        self,
        mocker,
        mock_env_vars,
    ):
        self._mock_service_key(mocker, ":foo-bar")
        assert apm_config.SolarWindsApmConfig().mask_service_key() == ":foo-bar"
        self._mock_service_key(mocker, "a:foo-bar")
        assert apm_config.SolarWindsApmConfig().mask_service_key() == "a:foo-bar"
        self._mock_service_key(mocker, "ab:foo-bar")
        assert apm_config.SolarWindsApmConfig().mask_service_key() == "ab:foo-bar"
        self._mock_service_key(mocker, "abc:foo-bar")
        assert apm_config.SolarWindsApmConfig().mask_service_key() == "abc:foo-bar"
        self._mock_service_key(mocker, "abcd:foo-bar")
        assert apm_config.SolarWindsApmConfig().mask_service_key() == "abcd:foo-bar"
        self._mock_service_key(mocker, "abcde:foo-bar")
        assert apm_config.SolarWindsApmConfig().mask_service_key() == "abcde:foo-bar"
        self._mock_service_key(mocker, "abcdef:foo-bar")
        assert apm_config.SolarWindsApmConfig().mask_service_key() == "abcdef:foo-bar"
        self._mock_service_key(mocker, "abcdefg:foo-bar")
        assert apm_config.SolarWindsApmConfig().mask_service_key() == "abcdefg:foo-bar"
        self._mock_service_key(mocker, "abcdefgh:foo-bar")
        assert apm_config.SolarWindsApmConfig().mask_service_key() == "abcdefgh:foo-bar"

    def test_mask_service_key_9_or_more_char_token(
        self,
        mocker,
        mock_env_vars,
    ):
        self._mock_service_key(mocker, "abcd1efgh:foo-bar")
        assert apm_config.SolarWindsApmConfig().mask_service_key() == "abcd...efgh:foo-bar"
        self._mock_service_key(mocker, "abcd12efgh:foo-bar")
        assert apm_config.SolarWindsApmConfig().mask_service_key() == "abcd...efgh:foo-bar"
        self._mock_service_key(mocker, "abcd123efgh:foo-bar")
        assert apm_config.SolarWindsApmConfig().mask_service_key() == "abcd...efgh:foo-bar"
        self._mock_service_key(mocker, "abcd1234567890efgh:foo-bar")
        assert apm_config.SolarWindsApmConfig().mask_service_key() == "abcd...efgh:foo-bar"
        self._mock_service_key(mocker, "CyUuit1W--8RVmUXX6_cVjTWemaUyBh1ruL0nMPiFdrPo1iiRnO31_pwiUCPzdzv9UMHK6I:foo-bar")
        assert apm_config.SolarWindsApmConfig().mask_service_key() == "CyUu...HK6I:foo-bar"

    def test_config_mask_service_key(
        self,
        mocker,
        mock_env_vars,
    ):
        self._mock_service_key(mocker, "valid-and-long:key")
        assert apm_config.SolarWindsApmConfig()._config_mask_service_key().get("service_key") == "vali...long:key"

    def test_str(
        self,
        mocker,
        mock_env_vars,
    ):
        self._mock_service_key(mocker, "valid-and-long:key")
        result = str(apm_config.SolarWindsApmConfig())
        assert "vali...long:key" in result
        assert "agent_enabled" in result
        assert "solarwinds_apm.extension.oboe.Context" in result

    # pylint:disable=unused-argument
    def test_set_config_value_invalid_key(self, caplog, setup_caplog, mock_env_vars):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("invalid_key", "foo")
        assert test_config.get("invalid_key", None) is None
        assert "Ignore invalid configuration key" in caplog.text

    # pylint:disable=unused-argument
    def test_set_config_value_default_ec2(self, caplog, setup_caplog, mock_env_vars):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("ec2_metadata_timeout", "9999")
        assert test_config.get("ec2_metadata_timeout") == 1000
        assert "Ignore config option" in caplog.text

    # pylint:disable=unused-argument
    def test_set_config_value_default_proxy(self, caplog, setup_caplog, mock_env_vars):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("proxy", "not-valid-url")
        assert test_config.get("proxy") == ""
        assert "Ignore config option" in caplog.text

    # pylint:disable=unused-argument
    def test_set_config_value_default_tracing_mode(self, caplog, setup_caplog, mock_env_vars):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("tracing_mode", "not-valid-mode")
        assert test_config.get("tracing_mode") == -1
        assert "Ignore config option" in caplog.text

    # pylint:disable=unused-argument
    def test_set_config_value_default_trigger_trace(self, caplog, setup_caplog, mock_env_vars):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("trigger_trace", "not-valid-mode")
        assert test_config.get("trigger_trace") == 1
        assert "Ignore config option" in caplog.text

    # pylint:disable=unused-argument
    def test_set_config_value_default_reporter(self, caplog, setup_caplog, mock_env_vars):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("reporter", "not-valid-mode")
        assert test_config.get("reporter") == ""
        assert "Ignore config option" in caplog.text

    # pylint:disable=unused-argument
    def test_set_config_value_default_debug_level(self, caplog, setup_caplog, mock_env_vars):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("debug_level", "not-valid-level")
        assert test_config.get("debug_level") == 2
        assert "Ignore config option" in caplog.text
    def test_set_config_value_default_log_type(
        self,
        caplog,
        setup_caplog,
        mock_env_vars,
    ):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("log_type", "not-valid-level")
        assert test_config.get("log_type") == 0
        assert "Ignore config option" in caplog.text

    def test_set_config_value_default_export_logs_enabled(
        self,
    ):
        test_config = apm_config.SolarWindsApmConfig()
        assert test_config.get("export_logs_enabled") == False

    def test_set_config_value_ignore_export_logs_enabled(
        self,
        caplog,
        setup_caplog,
        mock_env_vars,
    ):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("export_logs_enabled", "not-valid")
        assert test_config.get("export_logs_enabled") == False
        assert "Ignore config option" in caplog.text
    def test_set_config_value_set_export_logs_enabled_false(
        self,
        caplog,
        setup_caplog,
        mock_env_vars,
    ):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("export_logs_enabled", "false")
        assert test_config.get("export_logs_enabled") == False
        assert "Ignore config option" not in caplog.text

    def test_set_config_value_set_export_logs_enabled_false_mixed_case(
        self,
        caplog,
        setup_caplog,
        mock_env_vars,
    ):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("export_logs_enabled", "fALsE")
        assert test_config.get("export_logs_enabled") == False
        assert "Ignore config option" not in caplog.text

    def test_set_config_value_set_export_logs_enabled_true(
        self,
        caplog,
        setup_caplog,
        mock_env_vars,
    ):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("export_logs_enabled", "true")
        assert test_config.get("export_logs_enabled") == True
        assert "Ignore config option" not in caplog.text

    def test_set_config_value_set_export_logs_enabled_true_mixed_case(
        self,
        caplog,
        setup_caplog,
        mock_env_vars,
    ):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("export_logs_enabled", "tRUe")
        assert test_config.get("export_logs_enabled") == True
        assert "Ignore config option" not in caplog.text

    def test_set_config_value_default_export_metrics_enabled(
        self,
    ):
        test_config = apm_config.SolarWindsApmConfig()
        assert test_config.get("export_metrics_enabled") == False

    def test_set_config_value_ignore_export_metrics_enabled(
        self,
        caplog,
        setup_caplog,
        mock_env_vars,
    ):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("export_metrics_enabled", "not-valid")
        assert test_config.get("export_metrics_enabled") == False
        assert "Ignore config option" in caplog.text
    def test_set_config_value_set_export_metrics_enabled_false(
        self,
        caplog,
        setup_caplog,
        mock_env_vars,
    ):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("export_metrics_enabled", "false")
        assert test_config.get("export_metrics_enabled") == False
        assert "Ignore config option" not in caplog.text

    def test_set_config_value_set_export_metrics_enabled_false_mixed_case(
        self,
        caplog,
        setup_caplog,
        mock_env_vars,
    ):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("export_metrics_enabled", "fALsE")
        assert test_config.get("export_metrics_enabled") == False
        assert "Ignore config option" not in caplog.text

    def test_set_config_value_set_export_metrics_enabled_true(
        self,
        caplog,
        setup_caplog,
        mock_env_vars,
    ):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("export_metrics_enabled", "true")
        assert test_config.get("export_metrics_enabled") == True
        assert "Ignore config option" not in caplog.text

    def test_set_config_value_set_export_metrics_enabled_true_mixed_case(
        self,
        caplog,
        setup_caplog,
        mock_env_vars,
    ):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("export_metrics_enabled", "tRUe")
        assert test_config.get("export_metrics_enabled") == True
        assert "Ignore config option" not in caplog.text

    def test__update_service_key_name_not_agent_enabled(self):
        test_config = apm_config.SolarWindsApmConfig()
        result = test_config._update_service_key_name(
            False,
            "foo",
            "bar"
        )
        assert result == "foo"

    def test__update_service_key_name_empty_service_name(self):
        test_config = apm_config.SolarWindsApmConfig()
        result = test_config._update_service_key_name(
            True,
            "foo",
            ""
        )
        assert result == "foo"

    def test__update_service_key_name_not_agent_enabled_and_empty_service_name(self):
        test_config = apm_config.SolarWindsApmConfig()
        result = test_config._update_service_key_name(
            False,
            "foo",
            ""
        )
        assert result == "foo"

    def test__update_service_key_name_agent_enabled_and_service_name_ok(self):
        test_config = apm_config.SolarWindsApmConfig()
        result = test_config._update_service_key_name(
            True,
            "valid_key_with:foo-service",
            "bar-service"
        )
        assert result == "valid_key_with:bar-service"

    def test__update_service_key_name_agent_enabled_and_service_name_ok_but_service_key_missing(self):
        test_config = apm_config.SolarWindsApmConfig()
        result = test_config._update_service_key_name(
            True,
            None,
            "bar-service"
        )
        assert result is None

    def test__update_service_key_name_agent_enabled_and_service_name_ok_but_service_key_empty(self):
        test_config = apm_config.SolarWindsApmConfig()
        result = test_config._update_service_key_name(
            True,
            "",
            "bar-service"
        )
        assert result == ""

    def test__update_service_key_name_agent_enabled_and_service_name_ok_but_service_key_no_delimiter(self):
        test_config = apm_config.SolarWindsApmConfig()
        result = test_config._update_service_key_name(
            True,
            "weird-key-no-delimiter",
            "bar-service"
        )
        assert result == "weird-key-no-delimiter"

    def test__update_service_key_name_agent_enabled_and_service_name_ok_service_key_multiple_delimiter(self):
        test_config = apm_config.SolarWindsApmConfig()
        result = test_config._update_service_key_name(
            True,
            "weird-key:with:2-delimiters",
            "bar-service"
        )
        # Updates everything after first delim
        assert result == "weird-key:bar-service"

    def test_update_log_settings(self, mocker):
        mock_log_filepath = mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.update_log_filepath"
        )
        mock_log_type = mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.update_log_type"
        )
        # init includes update_log_settings()
        apm_config.SolarWindsApmConfig()
        mock_log_filepath.assert_called_once()
        mock_log_type.assert_called_once()

    def test_update_log_filepath_none(self, mocker):
        mock_exists = mocker.patch("solarwinds_apm.apm_config.os.path.exists")
        mock_makedirs = mocker.patch("solarwinds_apm.apm_config.os.makedirs")

        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("log_filepath", "")
        test_config._set_config_value("log_type", 2)
        test_config.update_log_filepath()
        mock_exists.assert_not_called()
        mock_makedirs.assert_not_called()
        assert test_config.get("log_filepath") == ""
        assert test_config.get("log_type") == 2

    def test_update_log_filepath_no_parent_path(self, mocker):
        mock_exists = mocker.patch("solarwinds_apm.apm_config.os.path.exists")
        mock_makedirs = mocker.patch("solarwinds_apm.apm_config.os.makedirs")

        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("log_filepath", "foo")
        test_config._set_config_value("log_type", 2)
        test_config.update_log_filepath()
        mock_exists.assert_not_called()
        mock_makedirs.assert_not_called()
        assert test_config.get("log_filepath") == "foo"
        assert test_config.get("log_type") == 2

    def test_update_log_filepath_path_exists(self, mocker):
        mock_exists = mocker.patch("solarwinds_apm.apm_config.os.path.exists", return_value=True)
        mock_makedirs = mocker.patch("solarwinds_apm.apm_config.os.makedirs")

        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("log_filepath", "/path/to/foo")
        test_config._set_config_value("log_type", 2)
        test_config.update_log_filepath()
        mock_exists.assert_called_once_with("/path/to")
        mock_makedirs.assert_not_called()
        assert test_config.get("log_filepath") == "/path/to/foo"
        assert test_config.get("log_type") == 2

    def test_update_log_filepath_create_path(self, mocker):
        mock_exists = mocker.patch("solarwinds_apm.apm_config.os.path.exists", return_value=False)
        mock_makedirs = mocker.patch("solarwinds_apm.apm_config.os.makedirs")

        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("log_filepath", "/path/to/foo")
        test_config._set_config_value("log_type", 2)
        test_config.update_log_filepath()
        mock_exists.assert_called_once_with("/path/to")
        mock_makedirs.assert_called_once_with("/path/to")
        assert test_config.get("log_filepath") == "/path/to/foo"
        assert test_config.get("log_type") == 2

    def test_update_log_filepath_cannot_create_reset_settings(self, mocker):
        mock_exists = mocker.patch("solarwinds_apm.apm_config.os.path.exists", return_value=False)
        mock_makedirs = mocker.patch(
            "solarwinds_apm.apm_config.os.makedirs",
            side_effect=FileNotFoundError("mock error")
        )

        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("log_filepath", "/path/to/foo")
        test_config._set_config_value("log_type", 2)
        test_config.update_log_filepath()
        mock_exists.assert_called_once_with("/path/to")
        mock_makedirs.assert_called_once_with("/path/to")
        assert test_config.get("log_filepath") == ""
        assert test_config.get("log_type") == 0

    def test_update_log_type_no_change(self):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("debug_level", 2)
        test_config._set_config_value("log_type", 0)
        test_config._set_config_value("log_filepath", "")
        test_config.update_log_type()
        assert test_config.get("debug_level") == 2
        assert test_config.get("log_type") == 0
        assert test_config.get("log_filepath") == ""

    def test_update_log_type_disabled(self):        
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("debug_level", -1)
        test_config._set_config_value("log_type", 0)
        test_config._set_config_value("log_filepath", "")
        test_config.update_log_type()
        assert test_config.get("debug_level") == -1
        assert test_config.get("log_type") == 4
        assert test_config.get("log_filepath") == ""

    def test_update_log_type_log_filepath(self):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("debug_level", 1)
        test_config._set_config_value("log_type", 0)
        test_config._set_config_value("log_filepath", "some-file-path")
        test_config.update_log_type()
        assert test_config.get("debug_level") == 1
        assert test_config.get("log_type") == 2
        assert test_config.get("log_filepath") == "some-file-path"

    def test_update_log_type_log_filepath_but_disabled(self):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("debug_level", -1)
        test_config._set_config_value("log_type", 0)
        test_config._set_config_value("log_filepath", "some-file-path")
        test_config.update_log_type()
        assert test_config.get("debug_level") == -1
        assert test_config.get("log_type") == 4
        assert test_config.get("log_filepath") == "some-file-path"

    def test_update_log_filepath_for_reporter_empty(self):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("log_filepath", "")
        test_config.update_log_filepath_for_reporter()
        assert test_config.get("log_filepath") == ""

    def test_update_log_filepath_for_reporter_no_ext(self):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("log_filepath", "/path/to/foo")
        test_config.update_log_filepath_for_reporter()
        assert test_config.get("log_filepath") == "/path/to/foo_ext"

    def test_update_log_filepath_for_reporter_ext(self):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("log_filepath", "/path/to/foo.log")
        test_config.update_log_filepath_for_reporter()
        assert test_config.get("log_filepath") == "/path/to/foo_ext.log"

    def test_update_log_filepath_for_reporter_ext_multiple_dots(self):
        test_config = apm_config.SolarWindsApmConfig()
        test_config._set_config_value("log_filepath", "/path/to/foo.abc.def.xyz")
        test_config.update_log_filepath_for_reporter()
        assert test_config.get("log_filepath") == "/path/to/foo.abc.def_ext.xyz"

    def test_convert_to_bool_bool_true(self):
        test_config = apm_config.SolarWindsApmConfig()
        assert test_config.convert_to_bool(True)

    def test_convert_to_bool_bool_false(self):
        test_config = apm_config.SolarWindsApmConfig()
        assert not test_config.convert_to_bool(False)

    def test_convert_to_bool_int(self):
        test_config = apm_config.SolarWindsApmConfig()
        assert test_config.convert_to_bool(0) is None

    def test_convert_to_bool_str_invalid(self):
        test_config = apm_config.SolarWindsApmConfig()
        assert test_config.convert_to_bool("not-true-nor-false") is None

    def test_convert_to_bool_str_true(self):
        test_config = apm_config.SolarWindsApmConfig()
        assert test_config.convert_to_bool("true")

    def test_convert_to_bool_str_true_mixed_case(self):
        test_config = apm_config.SolarWindsApmConfig()
        assert test_config.convert_to_bool("tRuE")

    def test_convert_to_bool_str_false(self):
        test_config = apm_config.SolarWindsApmConfig()
        assert not test_config.convert_to_bool("false")

    def test_convert_to_bool_str_false_mixed_case(self):
        test_config = apm_config.SolarWindsApmConfig()
        assert not test_config.convert_to_bool("fAlSE")

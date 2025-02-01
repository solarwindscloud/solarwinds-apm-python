# © 2023 SolarWinds Worldwide, LLC. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at:http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

import os

from solarwinds_apm import apm_config

# pylint: disable=unused-import
from .fixtures.cnf_dict import (
    fixture_cnf_dict,
    fixture_cnf_dict_enabled_false,
    fixture_cnf_dict_enabled_false_mixed_case,
)

# pylint: disable=unused-import
from .fixtures.env_vars import fixture_mock_env_vars

class TestSolarWindsApmConfigAgentEnabled:
    def test_calculate_agent_enabled_service_key_missing(self, mocker):
        # Save any service key in os for later
        old_service_key = os.environ.get("SW_APM_SERVICE_KEY", None)
        if old_service_key:
            del os.environ["SW_APM_SERVICE_KEY"]
        mocker.patch.dict(os.environ, {
            "SW_APM_AGENT_ENABLED": "true",
        })
        mock_entry_points = mocker.patch(
            "solarwinds_apm.apm_config.entry_points"
        )
        mock_points = mocker.MagicMock()
        mock_points.__iter__.return_value = ["foo"]
        mock_entry_points.configure_mock(
            return_value=mock_points
        )
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.update_log_settings"
        )
        mock_apm_logging = mocker.patch(
            "solarwinds_apm.apm_config.apm_logging"
        )
        mock_apm_logging.configure_mock(
            **{
                "set_sw_log_type": mocker.Mock(),
                "set_sw_log_level": mocker.Mock(),
                "ApmLoggingLevel.default_level": mocker.Mock(return_value=2)
            }
        )

        resulting_config = apm_config.SolarWindsApmConfig()
        assert not resulting_config._calculate_agent_enabled()
        assert resulting_config.service_name == ""
        # Restore that service key
        if old_service_key:
            os.environ["SW_APM_SERVICE_KEY"] = old_service_key

    def test_calculate_agent_enabled_service_key_env_var_set_cnf_file_ignored(   
        self,
        mocker,
        fixture_cnf_dict,
        mock_env_vars
    ):
        # Save any service key in os for later
        old_service_key = os.environ.get("SW_APM_SERVICE_KEY", None)
        # Save any collector in os for later
        old_collector = os.environ.get("SW_APM_COLLECTOR", None)
        if old_collector:
            del os.environ["SW_APM_COLLECTOR"]

        mock_entry_points = mocker.patch(
            "solarwinds_apm.apm_config.entry_points"
        )
        mock_points = mocker.MagicMock()
        mock_points.__iter__.return_value = ["foo"]
        mock_entry_points.configure_mock(
            return_value=mock_points
        )
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": "valid:key-will-be-used",
        })
        mock_get_cnf_dict = mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.get_cnf_dict"
        )
        # Includes "serviceKey": "not-good-to-put-here:still-could-be-used"
        mock_get_cnf_dict.configure_mock(
            return_value=fixture_cnf_dict
        )
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.update_log_settings"
        )
        mock_apm_logging = mocker.patch(
            "solarwinds_apm.apm_config.apm_logging"
        )
        mock_apm_logging.configure_mock(
            **{
                "set_sw_log_type": mocker.Mock(),
                "set_sw_log_level": mocker.Mock(),
                "ApmLoggingLevel.default_level": mocker.Mock(return_value=2)
            }
        )

        resulting_config = apm_config.SolarWindsApmConfig()
        assert resulting_config.get("service_key") == "valid:key-will-be-used"
        assert resulting_config.agent_enabled
        assert resulting_config.service_name == "key-will-be-used"

        # Restore old collector
        if old_collector:
            os.environ["SW_APM_COLLECTOR"] = old_collector
        # Restore that service key
        if old_service_key:
            os.environ["SW_APM_SERVICE_KEY"] = old_service_key

    def test_calculate_agent_enabled_service_key_env_var_not_set_cnf_file_used(   
        self,
        mocker,
        fixture_cnf_dict,
        mock_env_vars,
    ):
        # Save any service key in os for later
        old_service_key = os.environ.get("SW_APM_SERVICE_KEY", None)
        if old_service_key:
            del os.environ["SW_APM_SERVICE_KEY"]
        # Save any collector in os for later
        old_collector = os.environ.get("SW_APM_COLLECTOR", None)
        if old_collector:
            del os.environ["SW_APM_COLLECTOR"]

        mock_entry_points = mocker.patch(
            "solarwinds_apm.apm_config.entry_points"
        )
        mock_points = mocker.MagicMock()
        mock_points.__iter__.return_value = ["foo"]
        mock_entry_points.configure_mock(
            return_value=mock_points
        )

        mock_get_cnf_dict = mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.get_cnf_dict"
        )
        # Includes "serviceKey": "not-good-to-put-here:still-could-be-used"
        mock_get_cnf_dict.configure_mock(
            return_value=fixture_cnf_dict
        )
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.update_log_settings"
        )
        mock_apm_logging = mocker.patch(
            "solarwinds_apm.apm_config.apm_logging"
        )
        mock_apm_logging.configure_mock(
            **{
                "set_sw_log_type": mocker.Mock(),
                "set_sw_log_level": mocker.Mock(),
                "ApmLoggingLevel.default_level": mocker.Mock(return_value=2)
            }
        )

        resulting_config = apm_config.SolarWindsApmConfig()
        assert resulting_config.get("service_key") == "not-good-to-put-here:still-could-be-used"
        assert resulting_config.agent_enabled
        assert resulting_config.service_name == "still-could-be-used"

        # Restore old collector
        if old_collector:
            os.environ["SW_APM_COLLECTOR"] = old_collector
        # Restore that service key
        if old_service_key:
            os.environ["SW_APM_SERVICE_KEY"] = old_service_key

    def test_calculate_agent_enabled_service_key_bad_format(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": "invalidkey",
            "SW_APM_AGENT_ENABLED": "true",
        })
        mock_entry_points = mocker.patch(
            "solarwinds_apm.apm_config.entry_points"
        )
        mock_points = mocker.MagicMock()
        mock_points.__iter__.return_value = ["foo"]
        mock_entry_points.configure_mock(
            return_value=mock_points
        )
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.update_log_settings"
        )
        mock_apm_logging = mocker.patch(
            "solarwinds_apm.apm_config.apm_logging"
        )
        mock_apm_logging.configure_mock(
            **{
                "set_sw_log_type": mocker.Mock(),
                "set_sw_log_level": mocker.Mock(),
                "ApmLoggingLevel.default_level": mocker.Mock(return_value=2)
            }
        )
        resulting_config = apm_config.SolarWindsApmConfig()
        assert not resulting_config._calculate_agent_enabled()
        assert resulting_config.service_name == ""

    def test_calculate_agent_enabled_service_key_ok(
        self,
        mocker,
        mock_env_vars,
    ):
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": "valid:key",
        })
        mock_entry_points = mocker.patch(
            "solarwinds_apm.apm_config.entry_points"
        )
        mock_points = mocker.MagicMock()
        mock_points.__iter__.return_value = ["foo"]
        mock_entry_points.configure_mock(
            return_value=mock_points
        )
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.update_log_settings"
        )
        mock_apm_logging = mocker.patch(
            "solarwinds_apm.apm_config.apm_logging"
        )
        mock_apm_logging.configure_mock(
            **{
                "set_sw_log_type": mocker.Mock(),
                "set_sw_log_level": mocker.Mock(),
                "ApmLoggingLevel.default_level": mocker.Mock(return_value=2)
            }
        )
        resulting_config = apm_config.SolarWindsApmConfig()
        assert resulting_config._calculate_agent_enabled()
        assert resulting_config.service_name == "key"

    def test_calculate_agent_enabled_env_var_true(
        self,
        mocker,
        mock_env_vars,
    ):
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": "valid:key",
            "SW_APM_AGENT_ENABLED": "true",
        })
        mock_entry_points = mocker.patch(
            "solarwinds_apm.apm_config.entry_points"
        )
        mock_points = mocker.MagicMock()
        mock_points.__iter__.return_value = ["foo"]
        mock_entry_points.configure_mock(
            return_value=mock_points
        )
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.update_log_settings"
        )
        mock_apm_logging = mocker.patch(
            "solarwinds_apm.apm_config.apm_logging"
        )
        mock_apm_logging.configure_mock(
            **{
                "set_sw_log_type": mocker.Mock(),
                "set_sw_log_level": mocker.Mock(),
                "ApmLoggingLevel.default_level": mocker.Mock(return_value=2)
            }
        )
        resulting_config = apm_config.SolarWindsApmConfig()
        assert resulting_config._calculate_agent_enabled()
        assert resulting_config.service_name == "key"

    def test_calculate_agent_enabled_env_var_false(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": "valid:key",
            "SW_APM_AGENT_ENABLED": "false",
        })
        mock_entry_points = mocker.patch(
            "solarwinds_apm.apm_config.entry_points"
        )
        mock_points = mocker.MagicMock()
        mock_points.__iter__.return_value = ["foo"]
        mock_entry_points.configure_mock(
            return_value=mock_points
        )
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.update_log_settings"
        )
        mock_apm_logging = mocker.patch(
            "solarwinds_apm.apm_config.apm_logging"
        )
        mock_apm_logging.configure_mock(
            **{
                "set_sw_log_type": mocker.Mock(),
                "set_sw_log_level": mocker.Mock(),
                "ApmLoggingLevel.default_level": mocker.Mock(return_value=2)
            }
        )
        resulting_config = apm_config.SolarWindsApmConfig()
        assert not resulting_config._calculate_agent_enabled()
        assert resulting_config.service_name == ""

    def test_calculate_agent_enabled_env_var_false_mixed_case(self, mocker):
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": "valid:key",
            "SW_APM_AGENT_ENABLED": "fALsE",
        })
        mock_entry_points = mocker.patch(
            "solarwinds_apm.apm_config.entry_points"
        )
        mock_points = mocker.MagicMock()
        mock_points.__iter__.return_value = ["foo"]
        mock_entry_points.configure_mock(
            return_value=mock_points
        )
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.update_log_settings"
        )
        mock_apm_logging = mocker.patch(
            "solarwinds_apm.apm_config.apm_logging"
        )
        mock_apm_logging.configure_mock(
            **{
                "set_sw_log_type": mocker.Mock(),
                "set_sw_log_level": mocker.Mock(),
                "ApmLoggingLevel.default_level": mocker.Mock(return_value=2)
            }
        )
        resulting_config = apm_config.SolarWindsApmConfig()
        assert not resulting_config._calculate_agent_enabled()
        assert resulting_config.service_name == ""

    def test_calculate_agent_enabled_env_var_not_set_cnf_file_false(
        self,
        mocker,
        fixture_cnf_dict_enabled_false,
    ):
        mock_entry_points = mocker.patch(
            "solarwinds_apm.apm_config.entry_points"
        )
        mock_points = mocker.MagicMock()
        mock_points.__iter__.return_value = ["foo"]
        mock_entry_points.configure_mock(
            return_value=mock_points
        )
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": "valid:key",
        })
        mock_get_cnf_dict = mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.get_cnf_dict"
        )
        # cnf with "agentEnabled": False
        mock_get_cnf_dict.configure_mock(
            return_value=fixture_cnf_dict_enabled_false
        )
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.update_log_settings"
        )
        mock_apm_logging = mocker.patch(
            "solarwinds_apm.apm_config.apm_logging"
        )
        mock_apm_logging.configure_mock(
            **{
                "set_sw_log_type": mocker.Mock(),
                "set_sw_log_level": mocker.Mock(),
                "ApmLoggingLevel.default_level": mocker.Mock(return_value=2)
            }
        )
        resulting_config = apm_config.SolarWindsApmConfig()
        assert not resulting_config.agent_enabled
        assert resulting_config.service_name == ""

    def test_calculate_agent_enabled_env_var_not_set_cnf_file_false_mixed_case(
        self,
        mocker,
        fixture_cnf_dict_enabled_false_mixed_case,
    ):
        mock_entry_points = mocker.patch(
            "solarwinds_apm.apm_config.entry_points"
        )
        mock_points = mocker.MagicMock()
        mock_points.__iter__.return_value = ["foo"]
        mock_entry_points.configure_mock(
            return_value=mock_points
        )
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": "valid:key",
        })
        mock_get_cnf_dict = mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.get_cnf_dict"
        )
        # cnf with "agentEnabled": False
        mock_get_cnf_dict.configure_mock(
            return_value=fixture_cnf_dict_enabled_false_mixed_case
        )
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.update_log_settings"
        )
        mock_apm_logging = mocker.patch(
            "solarwinds_apm.apm_config.apm_logging"
        )
        mock_apm_logging.configure_mock(
            **{
                "set_sw_log_type": mocker.Mock(),
                "set_sw_log_level": mocker.Mock(),
                "ApmLoggingLevel.default_level": mocker.Mock(return_value=2)
            }
        )
        resulting_config = apm_config.SolarWindsApmConfig()
        assert not resulting_config.agent_enabled
        assert resulting_config.service_name == ""

    def test_calculate_agent_enabled_env_var_true_cnf_file_false(
        self,
        mocker,
        fixture_cnf_dict_enabled_false,
        mock_env_vars,
    ):
        mock_entry_points = mocker.patch(
            "solarwinds_apm.apm_config.entry_points"
        )
        mock_points = mocker.MagicMock()
        mock_points.__iter__.return_value = ["foo"]
        mock_entry_points.configure_mock(
            return_value=mock_points
        )
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": "valid:key",
            "SW_APM_AGENT_ENABLED": "true",
        })
        mock_get_cnf_dict = mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.get_cnf_dict"
        )
        mock_get_cnf_dict.configure_mock(
            return_value=fixture_cnf_dict_enabled_false
        )
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.update_log_settings"
        )
        mock_apm_logging = mocker.patch(
            "solarwinds_apm.apm_config.apm_logging"
        )
        mock_apm_logging.configure_mock(
            **{
                "set_sw_log_type": mocker.Mock(),
                "set_sw_log_level": mocker.Mock(),
                "ApmLoggingLevel.default_level": mocker.Mock(return_value=2)
            }
        )
        resulting_config = apm_config.SolarWindsApmConfig()
        assert resulting_config.agent_enabled
        assert resulting_config.service_name == "key"

    def test_calculate_agent_enabled_env_var_false_cnf_file_true(
        self,
        mocker,
        fixture_cnf_dict,
    ):
        mock_entry_points = mocker.patch(
            "solarwinds_apm.apm_config.entry_points"
        )
        mock_points = mocker.MagicMock()
        mock_points.__iter__.return_value = ["foo"]
        mock_entry_points.configure_mock(
            return_value=mock_points
        )
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": "valid:key",
            "SW_APM_AGENT_ENABLED": "false",
        })
        mock_get_cnf_dict = mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.get_cnf_dict"
        )
        mock_get_cnf_dict.configure_mock(
            return_value=fixture_cnf_dict
        )
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.update_log_settings"
        )
        mock_apm_logging = mocker.patch(
            "solarwinds_apm.apm_config.apm_logging"
        )
        mock_apm_logging.configure_mock(
            **{
                "set_sw_log_type": mocker.Mock(),
                "set_sw_log_level": mocker.Mock(),
                "ApmLoggingLevel.default_level": mocker.Mock(return_value=2)
            }
        )

        # cnf file fixture has "agentEnabled": True
        resulting_config = apm_config.SolarWindsApmConfig()
        assert not resulting_config.agent_enabled
        assert resulting_config.service_name == ""

    def test_calculate_agent_enabled_ok_all_env_vars(
        self,
        mocker,
        mock_env_vars,
    ):
        mocker.patch.dict(os.environ, {
            "OTEL_PROPAGATORS": "foo,tracecontext,bar,solarwinds_propagator",
            "OTEL_TRACES_EXPORTER": "solarwinds_exporter,foo",
            "SW_APM_SERVICE_KEY": "valid:key",
            "SW_APM_AGENT_ENABLED": "true",
        })
        mock_entry_points = mocker.patch(
            "solarwinds_apm.apm_config.entry_points"
        )
        mock_points = mocker.MagicMock()
        mock_points.__iter__.return_value = ["foo"]
        mock_entry_points.configure_mock(
            return_value=mock_points
        )
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.update_log_settings"
        )
        mock_apm_logging = mocker.patch(
            "solarwinds_apm.apm_config.apm_logging"
        )
        mock_apm_logging.configure_mock(
            **{
                "set_sw_log_type": mocker.Mock(),
                "set_sw_log_level": mocker.Mock(),
                "ApmLoggingLevel.default_level": mocker.Mock(return_value=2)
            }
        )
        resulting_config = apm_config.SolarWindsApmConfig()
        assert resulting_config._calculate_agent_enabled()
        assert resulting_config.service_name == "key"

    def test_calculate_agent_enabled_no_sw_propagator(self, mocker):
        mocker.patch.dict(os.environ, {
            "OTEL_PROPAGATORS": "tracecontext,baggage",
            "SW_APM_SERVICE_KEY": "valid:key",
        })
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.update_log_settings"
        )
        mock_apm_logging = mocker.patch(
            "solarwinds_apm.apm_config.apm_logging"
        )
        mock_apm_logging.configure_mock(
            **{
                "set_sw_log_type": mocker.Mock(),
                "set_sw_log_level": mocker.Mock(),
                "ApmLoggingLevel.default_level": mocker.Mock(return_value=2)
            }
        )
        resulting_config = apm_config.SolarWindsApmConfig()
        assert not resulting_config._calculate_agent_enabled()
        assert resulting_config.service_name == ""

    def test_calculate_agent_enabled_no_tracecontext_propagator(self, mocker):
        mocker.patch.dict(os.environ, {
            "OTEL_PROPAGATORS": "solarwinds_propagator",
            "SW_APM_SERVICE_KEY": "valid:key",
        })
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.update_log_settings"
        )
        mock_apm_logging = mocker.patch(
            "solarwinds_apm.apm_config.apm_logging"
        )
        mock_apm_logging.configure_mock(
            **{
                "set_sw_log_type": mocker.Mock(),
                "set_sw_log_level": mocker.Mock(),
                "ApmLoggingLevel.default_level": mocker.Mock(return_value=2)
            }
        )
        resulting_config = apm_config.SolarWindsApmConfig()
        assert not resulting_config._calculate_agent_enabled()
        assert resulting_config.service_name == ""

    def test_calculate_agent_enabled_sw_before_tracecontext_propagator(self, mocker):
        mocker.patch.dict(os.environ, {
            "OTEL_PROPAGATORS": "solarwinds_propagator,tracecontext",
            "SW_APM_SERVICE_KEY": "valid:key",
        })
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.update_log_settings"
        )
        mock_apm_logging = mocker.patch(
            "solarwinds_apm.apm_config.apm_logging"
        )
        mock_apm_logging.configure_mock(
            **{
                "set_sw_log_type": mocker.Mock(),
                "set_sw_log_level": mocker.Mock(),
                "ApmLoggingLevel.default_level": mocker.Mock(return_value=2)
            }
        )
        resulting_config = apm_config.SolarWindsApmConfig()
        assert not resulting_config._calculate_agent_enabled()
        assert resulting_config.service_name == ""

    def test_calculate_agent_enabled_sw_before_baggage_propagator(self, mocker):
        mocker.patch.dict(os.environ, {
            "OTEL_PROPAGATORS": "tracecontext,solarwinds_propagator,baggage",
            "SW_APM_SERVICE_KEY": "valid:key",
        })
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.update_log_settings"
        )
        mock_apm_logging = mocker.patch(
            "solarwinds_apm.apm_config.apm_logging"
        )
        mock_apm_logging.configure_mock(
            **{
                "set_sw_log_type": mocker.Mock(),
                "set_sw_log_level": mocker.Mock(),
                "ApmLoggingLevel.default_level": mocker.Mock(return_value=2)
            }
        )
        resulting_config = apm_config.SolarWindsApmConfig()
        assert not resulting_config._calculate_agent_enabled()
        assert resulting_config.service_name == ""

    def test_calculate_agent_enabled_sw_after_baggage_propagator(
        self,
        mocker,
        mock_env_vars,
    ):
        mocker.patch.dict(os.environ, {
            "OTEL_PROPAGATORS": "tracecontext,baggage,solarwinds_propagator",
            "SW_APM_SERVICE_KEY": "valid:key",
        })
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.update_log_settings"
        )
        mock_apm_logging = mocker.patch(
            "solarwinds_apm.apm_config.apm_logging"
        )
        mock_apm_logging.configure_mock(
            **{
                "set_sw_log_type": mocker.Mock(),
                "set_sw_log_level": mocker.Mock(),
                "ApmLoggingLevel.default_level": mocker.Mock(return_value=2)
            }
        )
        resulting_config = apm_config.SolarWindsApmConfig()
        assert resulting_config._calculate_agent_enabled()
        assert resulting_config.service_name == "key"

    def test_calculate_agent_enabled_sw_but_no_such_other_exporter(
        self,
        mocker,
        mock_env_vars,
    ):
        mocker.patch.dict(os.environ, {
            "OTEL_TRACES_EXPORTER": "solarwinds_exporter,not-valid",
            "SW_APM_SERVICE_KEY": "valid:key",
        })
        mock_entry_points = mocker.patch(
            "solarwinds_apm.apm_config.entry_points"
        )
        mock_entry_points.configure_mock(
            side_effect=StopIteration("mock error")
        )
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.update_log_settings"
        )
        mock_apm_logging = mocker.patch(
            "solarwinds_apm.apm_config.apm_logging"
        )
        mock_apm_logging.configure_mock(
            **{
                "set_sw_log_type": mocker.Mock(),
                "set_sw_log_level": mocker.Mock(),
                "ApmLoggingLevel.default_level": mocker.Mock(return_value=2)
            }
        )
        resulting_config = apm_config.SolarWindsApmConfig()
        assert not resulting_config._calculate_agent_enabled()
        assert resulting_config.service_name == ""

    def test_calculate_agent_enabled_sw_and_two_other_valid_exporters(
        self,
        mocker,
        mock_env_vars,
    ):
        mocker.patch.dict(os.environ, {
            "OTEL_TRACES_EXPORTER": "foo,solarwinds_exporter,bar",
            "SW_APM_SERVICE_KEY": "valid:key",
        })
        mock_entry_points = mocker.patch(
            "solarwinds_apm.apm_config.entry_points"
        )
        mock_points = mocker.MagicMock()
        mock_points.__iter__.return_value = ["foo", "bar"]
        mock_entry_points.configure_mock(
            return_value=mock_points
        )
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.update_log_settings"
        )
        mock_apm_logging = mocker.patch(
            "solarwinds_apm.apm_config.apm_logging"
        )
        mock_apm_logging.configure_mock(
            **{
                "set_sw_log_type": mocker.Mock(),
                "set_sw_log_level": mocker.Mock(),
                "ApmLoggingLevel.default_level": mocker.Mock(return_value=2)
            }
        )
        resulting_config = apm_config.SolarWindsApmConfig()
        assert resulting_config._calculate_agent_enabled()
        assert resulting_config.service_name == "key"

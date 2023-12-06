# © 2023 SolarWinds Worldwide, LLC. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at:http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

from solarwinds_apm import configurator

class TestConfiguratorInitializeReporter:
    def test_configurator_initialize_sw_reporter(
        self,
        mocker,
        mock_apmconfig_enabled_reporter_settings,
    ):
        test_configurator = configurator.SolarWindsConfigurator()
        test_configurator._initialize_solarwinds_reporter(
            mock_apmconfig_enabled_reporter_settings,
        )

        mock_apmconfig_enabled_reporter_settings.extension.Reporter.assert_called_once_with(
            **{
                "hostname_alias": "foo",
                "log_level": "foo",
                "log_file_path": "foo",
                "max_transactions": "foo",
                "max_flush_wait_time": "foo",
                "events_flush_interval": "foo",
                "max_request_size_bytes": "foo",
                "reporter": "foo",
                "host": "foo",
                "service_key": "foo",
                "certificates": "foo-certs",
                "buffer_size": "foo",
                "trace_metrics": "foo",
                "histogram_precision": "foo",
                "token_bucket_capacity": "foo",
                "token_bucket_rate": "foo",
                "file_single": "foo",
                "ec2_metadata_timeout": "foo",
                "grpc_proxy": "foo",
                "stdout_clear_nonblocking": 0,
                "metric_format": "bar",
                "log_type": 0,
            }
        )

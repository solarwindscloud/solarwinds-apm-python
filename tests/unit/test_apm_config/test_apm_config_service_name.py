# © 2024 SolarWinds Worldwide, LLC. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at:http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

import os

from opentelemetry.sdk.resources import Resource

from solarwinds_apm import apm_config

# pylint: disable=unused-import
from .fixtures.env_vars import fixture_mock_env_vars

class TestSolarWindsApmConfigServiceName:
    def test__calculate_service_name_is_lambda(self, mocker):
        mock_calc_proto = mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig._calculate_service_name_apm_proto"
        )
        mock_calc_lambda = mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig._calculate_service_name_lambda"
        )
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.calculate_is_lambda",
            return_value=True,
        )
        test_config = apm_config.SolarWindsApmConfig("foo")
        test_config._calculate_service_name(
            True,
            {},
        )
        mock_calc_proto.assert_not_called()
        # called twice because of init, and we call again
        mock_calc_lambda.assert_has_calls(
            [
                mocker.call("foo"),
                mocker.call({}),
            ]
        )

    def test__calculate_service_name_not_is_lambda(self, mocker):
        mock_calc_proto = mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig._calculate_service_name_apm_proto"
        )
        mock_calc_lambda = mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig._calculate_service_name_lambda"
        )
        mocker.patch(
            "solarwinds_apm.apm_config.SolarWindsApmConfig.calculate_is_lambda",
            return_value=False,
        )
        test_config = apm_config.SolarWindsApmConfig("foo")
        test_config._calculate_service_name(
            True,
            {},
        )
        # called twice because of init, and we call again
        mock_calc_proto.assert_has_calls(
            [
                mocker.call(False, "foo"),
                mocker.call(True, {}),
            ]
        )
        mock_calc_lambda.assert_not_called()


class TestSolarWindsApmConfigServiceNameApmProto:
    def test__calculate_service_name_apm_proto_agent_disabled(self):
        test_config = apm_config.SolarWindsApmConfig()
        result = test_config._calculate_service_name_apm_proto(
            False,
            {}
        )
        assert result == ""

    def test__calculate_service_name_apm_proto_no_otel_service_name(
        self,
        mocker,
        mock_env_vars,
    ):
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": "service_key_with:sw_service_name",
        })
        test_config = apm_config.SolarWindsApmConfig()
        result = test_config._calculate_service_name_apm_proto(
            True,
            Resource.create({"service.name": None})
        )
        assert result == "sw_service_name"

    def test__calculate_service_name_apm_proto_default_unknown_otel_service_name(
        self,
        mocker,
        mock_env_vars,
    ):
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": "service_key_with:sw_service_name",
        })
        test_config = apm_config.SolarWindsApmConfig()
        result = test_config._calculate_service_name_apm_proto(
            True,
            # default is unknown_service
            Resource.create()
        )
        assert result == "sw_service_name"

    def test__calculate_service_name_apm_proto_use_otel_service_name(
        self,
        mocker,
        mock_env_vars,
    ):
        mocker.patch.dict(os.environ, {
            "SW_APM_SERVICE_KEY": "service_key_with:sw_service_name",
        })
        test_config = apm_config.SolarWindsApmConfig()
        result = test_config._calculate_service_name_apm_proto(
            True,
            Resource.create({"service.name": "foobar"})
        )
        assert result == "foobar"

class TestSolarWindsApmConfigServiceNameLambda:
    def test__calculate_service_name_lambda_no_otel_name(
        self,
        mocker,
    ):
        mocker.patch.dict(os.environ, {
            "AWS_LAMBDA_FUNCTION_NAME": "foo-fn",
        })
        test_config = apm_config.SolarWindsApmConfig()
        result = test_config._calculate_service_name_lambda(
            Resource.create({})
        )
        assert result == "foo-fn"

    def test__calculate_service_name_lambda_empty_otel_name(
        self,
        mocker,
    ):
        mocker.patch.dict(os.environ, {
            "AWS_LAMBDA_FUNCTION_NAME": "foo-fn",
        })
        test_config = apm_config.SolarWindsApmConfig()
        result = test_config._calculate_service_name_lambda(
            Resource.create({"service.name": ""})
        )
        assert result == "foo-fn"

    def test__calculate_service_name_lambda_otel_name_unknown(
        self,
        mocker,
    ):
        mocker.patch.dict(os.environ, {
            "AWS_LAMBDA_FUNCTION_NAME": "foo-fn",
        })
        test_config = apm_config.SolarWindsApmConfig()
        result = test_config._calculate_service_name_lambda(
            Resource.create({"service.name": "unknown_service"})
        )
        assert result == "foo-fn"

    def test__calculate_service_name_lambda_otel_name_ok(
        self,
        mocker,
    ):
        test_config = apm_config.SolarWindsApmConfig()
        result = test_config._calculate_service_name_lambda(
            Resource.create({"service.name": "foo-service-name"})
        )
        assert result == "foo-service-name"

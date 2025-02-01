# © 2023 SolarWinds Worldwide, LLC. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at:http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

from solarwinds_apm import configurator

from .fixtures.trace import get_trace_mocks

class TestConfiguratorCreateInitEvent:
    def test_configurator_create_init_is_lambda(
        self,
        mocker,
        mock_sys,
        mock_apm_version,
        mock_fw_versions,
        mock_extension,
        mock_apmconfig_enabled_is_lambda,
    ):
        trace_mocks = get_trace_mocks(mocker)

        test_configurator = configurator.SolarWindsConfigurator()
        result = test_configurator._create_init_event(
            mock_extension.Reporter,
            mock_apmconfig_enabled_is_lambda,
        )

        assert result is None

        # Otel and APM methods not called
        trace_mocks.get_tracer_provider().get_tracer().resource.attributes.items.assert_not_called()
        mock_fw_versions.assert_not_called()

        # Extension methods not called
        mock_apmconfig_enabled_is_lambda.extension.Config.getVersionString.assert_not_called()
        assert mocker.call(True,) not in mock_apmconfig_enabled_is_lambda.extension.Metadata.makeRandom.mock_calls
        mock_apmconfig_enabled_is_lambda.extension.Context.set.assert_not_called()
        mock_apmconfig_enabled_is_lambda.extension.Metadata.makeRandom().createEvent().addInfo.assert_not_called()

    def test_configurator_create_init_bad_init_status_disabled(
        self,
        mocker,
        mock_sys,
        mock_apm_version,
        mock_fw_versions,
        mock_extension_status_code_invalid_protocol,
        mock_apmconfig_disabled,
    ):
        trace_mocks = get_trace_mocks(mocker)

        test_configurator = configurator.SolarWindsConfigurator()
        result = test_configurator._create_init_event(
            mock_extension_status_code_invalid_protocol.Reporter,
            mock_apmconfig_disabled,
        )

        assert result is None

        # Otel and APM methods not called
        trace_mocks.get_tracer_provider().get_tracer().resource.attributes.items.assert_not_called()
        mock_fw_versions.assert_not_called()

        # Extension methods not called
        mock_apmconfig_disabled.extension.Config.getVersionString.assert_not_called()
        assert mocker.call(True,) not in mock_apmconfig_disabled.extension.Metadata.makeRandom.mock_calls
        mock_apmconfig_disabled.extension.Context.set.assert_not_called()
        mock_apmconfig_disabled.extension.Metadata.makeRandom().createEvent().addInfo.assert_not_called()

    def test_configurator_create_init_bad_init_status_enabled(
        self,
        mocker,
        mock_sys,
        mock_apm_version,
        mock_fw_versions,
        mock_extension_status_code_invalid_protocol,
        mock_apmconfig_enabled,
    ):
        trace_mocks = get_trace_mocks(mocker)

        test_configurator = configurator.SolarWindsConfigurator()
        result = test_configurator._create_init_event(
            mock_extension_status_code_invalid_protocol.Reporter,
            mock_apmconfig_enabled,
        )

        assert result is None

        # Otel and APM methods not called
        trace_mocks.get_tracer_provider().get_tracer().resource.attributes.items.assert_not_called()
        mock_fw_versions.assert_not_called()

        # Extension methods not called
        mock_apmconfig_enabled.extension.Config.getVersionString.assert_not_called()
        assert mocker.call(True,) not in mock_apmconfig_enabled.extension.Metadata.makeRandom.mock_calls
        mock_apmconfig_enabled.extension.Context.set.assert_not_called()
        mock_apmconfig_enabled.extension.Metadata.makeRandom().createEvent().addInfo.assert_not_called()

    def test_configurator_create_init_ok_init_status_disabled(
        self,
        mocker,
        mock_sys,
        mock_apm_version,
        mock_fw_versions,
        mock_extension,
        mock_apmconfig_disabled,
    ):
        trace_mocks = get_trace_mocks(mocker)

        test_configurator = configurator.SolarWindsConfigurator()
        result = test_configurator._create_init_event(
            mock_extension.Reporter,
            mock_apmconfig_disabled,
        )

        assert result is None

        # Otel and APM methods not called
        trace_mocks.get_tracer_provider().get_tracer().resource.attributes.items.assert_not_called()
        mock_fw_versions.assert_not_called()

        # Extension methods not called
        mock_apmconfig_disabled.extension.Config.getVersionString.assert_not_called()
        assert mocker.call(True,) not in mock_apmconfig_disabled.extension.Metadata.makeRandom.mock_calls
        mock_apmconfig_disabled.extension.Context.set.assert_not_called()
        mock_apmconfig_disabled.extension.Metadata.makeRandom().createEvent().addInfo.assert_not_called()

    def test_configurator_create_init_already_init_status_disabled(
        self,
        mocker,
        mock_sys,
        mock_apm_version,
        mock_fw_versions,
        mock_extension_status_code_already_init,
        mock_apmconfig_disabled,
    ):
        trace_mocks = get_trace_mocks(mocker)

        test_configurator = configurator.SolarWindsConfigurator()
        result = test_configurator._create_init_event(
            mock_extension_status_code_already_init.Reporter,
            mock_apmconfig_disabled,
        )

        assert result is None

        # Otel and APM methods not called
        trace_mocks.get_tracer_provider().get_tracer().resource.attributes.items.assert_not_called()
        mock_fw_versions.assert_not_called()

        # Extension methods not called
        mock_apmconfig_disabled.extension.Config.getVersionString.assert_not_called()
        assert mocker.call(True,) not in mock_apmconfig_disabled.extension.Metadata.makeRandom.mock_calls
        mock_apmconfig_disabled.extension.Context.set.assert_not_called()
        mock_apmconfig_disabled.extension.Metadata.makeRandom().createEvent().addInfo.assert_not_called()

    def test_configurator_legacy_create_init_invalid_md(
        self,
        mocker,
        mock_sys,
        mock_apm_version,
        mock_fw_versions,
        mock_extension,
        mock_apmconfig_enabled_md_invalid,
    ):
        trace_mocks = get_trace_mocks(mocker)

        test_configurator = configurator.SolarWindsConfigurator()
        result = test_configurator._create_init_event(
            mock_extension.Reporter,
            mock_apmconfig_enabled_md_invalid,
        )

        assert isinstance(
            result,
            type(mock_apmconfig_enabled_md_invalid.extension.Metadata.makeRandom().createEvent()),
        )

        # Otel and APM methods called
        trace_mocks.get_tracer_provider().get_tracer().resource.attributes.items.assert_called_once()
        mock_fw_versions.assert_called_once()

        # Some extension methods called
        mock_apmconfig_enabled_md_invalid.extension.Config.getVersionString.assert_called_once()

    def test_configurator_legacy_create_init_bad_sys_py_version_still_creates_without_runtime_version(
        self,
        mocker,
        mock_sys_error_version_info,
        mock_apm_version,
        mock_fw_versions,
        mock_extension,
        mock_apmconfig_enabled_legacy,
    ):
        trace_mocks = get_trace_mocks(mocker)

        test_configurator = configurator.SolarWindsConfigurator()
        result = test_configurator._create_init_event(
            mock_extension.Reporter,
            mock_apmconfig_enabled_legacy,
        )

        assert isinstance(
            result,
            type(mock_apmconfig_enabled_legacy.extension.Metadata.makeRandom().createEvent()),
        )

        # Otel and APM methods called
        trace_mocks.get_tracer_provider().get_tracer().resource.attributes.items.assert_called_once()
        mock_fw_versions.assert_called_once()

        # Extension methods called
        mock_apmconfig_enabled_legacy.extension.Config.getVersionString.assert_called_once()
        mock_apmconfig_enabled_legacy.extension.Metadata.makeRandom.assert_has_calls(
            [
                mocker.call(True,),  # makeRandom(True)
            ]
        )
        mock_apmconfig_enabled_legacy.extension.Context.set.assert_called_once()
        mock_apmconfig_enabled_legacy.extension.Metadata.makeRandom().createEvent().addInfo.assert_has_calls(
            [
                mocker.call("Layer", "Python"),
                mocker.call("__Init", True),
                mocker.call("process.runtime.name", "foo-name"),
                mocker.call("process.runtime.description", "foo-runtime"),
                mocker.call("process.executable.path", "/foo/path"),
                mocker.call("APM.Version", "0.0.0"),
                mocker.call("APM.Extension.Version", "1.1.1"),
                mocker.call("foo-fw", "bar-version")
            ]
        )

    def test_configurator_create_init(
        self,
        mocker,
        mock_sys,
        mock_apm_version,
        mock_fw_versions,
        mock_extension,
        mock_apmconfig_enabled_legacy,
    ):
        trace_mocks = get_trace_mocks(mocker)

        # Test!
        test_configurator = configurator.SolarWindsConfigurator()
        result = test_configurator._create_init_event(
            mock_extension.Reporter,
            mock_apmconfig_enabled_legacy,
        )

        assert isinstance(
            result,
            type(mock_apmconfig_enabled_legacy.extension.Metadata.makeRandom().createEvent()),
        )

        # Otel and APM methods called
        trace_mocks.get_tracer_provider().get_tracer().resource.attributes.items.assert_called_once()
        mock_fw_versions.assert_called_once()

        # Extension methods called
        mock_apmconfig_enabled_legacy.extension.Config.getVersionString.assert_called_once()
        mock_apmconfig_enabled_legacy.extension.Metadata.makeRandom.assert_has_calls(
            [
                mocker.call(True,),  # makeRandom(True)
            ]
        )
        mock_apmconfig_enabled_legacy.extension.Context.set.assert_called_once()
        mock_apmconfig_enabled_legacy.extension.Metadata.makeRandom().createEvent().addInfo.assert_has_calls(
            [
                mocker.call("Layer", "Python"),
                mocker.call("__Init", True),
                mocker.call("process.runtime.version", "3.11.12"),
                mocker.call("process.runtime.name", "foo-name"),
                mocker.call("process.runtime.description", "foo-runtime"),
                mocker.call("process.executable.path", "/foo/path"),
                mocker.call("APM.Version", "0.0.0"),
                mocker.call("APM.Extension.Version", "1.1.1"),
                mocker.call("foo-fw", "bar-version")
            ]
        )

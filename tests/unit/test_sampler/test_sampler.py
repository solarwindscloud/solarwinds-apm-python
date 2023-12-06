# © 2023 SolarWinds Worldwide, LLC. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at:http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

import pytest

from opentelemetry.sdk.trace.sampling import (
    Decision, StaticSampler
)
from opentelemetry.trace.span import SpanContext, TraceState

import solarwinds_apm.extension.oboe
from solarwinds_apm.sampler import _SwSampler, ParentBasedSwSampler

# pylint: disable=unused-import
from .fixtures.parent_span_context import (
    fixture_parent_span_context_invalid,
    fixture_parent_span_context_valid_remote,
)
from .fixtures.sampler import (
    config_get,
    fixture_swsampler,
)
from .fixtures.span_id_from_sw import fixture_mock_span_id_from_sw
from .fixtures.sw_from_span_and_decision import fixture_mock_sw_from_span_and_decision

# Mock Fixtures, autoused ===========================================

@pytest.fixture(autouse=True)
def fixture_mock_context_getdecisions(mocker, mock_liboboe_decision):
    mocker.patch(
        'solarwinds_apm.extension.oboe.Context.getDecisions',
        return_value=mock_liboboe_decision
    )

@pytest.fixture(autouse=True)
def fixture_mock_trace_flags_from_int(mocker):
    mocker.patch(
        "solarwinds_apm.w3c_transformer.W3CTransformer.trace_flags_from_int",
        return_value="01"
    )

# Mock Fixtures, manually used ======================================

@pytest.fixture(name="mock_liboboe_decision")
def fixture_mock_liboboe_decision():
    return 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11

@pytest.fixture(name="mock_traceparent_from_context")
def fixture_mock_traceparent_from_context(mocker):
    mocker.patch(
        "solarwinds_apm.w3c_transformer.W3CTransformer.traceparent_from_context",
        return_value="foo-bar"
    )

@pytest.fixture(name="mock_xtraceoptions_signed_tt")
def fixture_xtraceoptions_signed_tt(mocker):
    options = mocker.Mock()
    options.trigger_trace = 1
    options.options_header = "foo-bar"
    options.signature = 123456
    options.timestamp = 123456
    options.ignored = ["baz", "qux"]
    return options

@pytest.fixture(name="mock_xtraceoptions_signed_without_tt")
def fixture_xtraceoptions_signed_without_tt(mocker):
    options = mocker.Mock()
    options.trigger_trace = 0
    options.options_header = "foo-bar"
    options.signature = 123456
    options.timestamp = 123456
    options.ignored = ["baz", "qux"]
    return options

@pytest.fixture(name="mock_xtraceoptions_signed_not_tt")
def fixture_xtraceoptions_signed_not_tt(mocker):
    options = mocker.Mock()
    options.trigger_trace = 0
    options.options_header = "foo-bar"
    options.signature = 123456
    options.timestamp = 123456
    options.ignored = ["baz", "qux"]
    return options

@pytest.fixture(name="mock_xtraceoptions_unsigned_tt")
def fixture_xtraceoptions_unsigned_tt(mocker):
    options = mocker.Mock()
    options.trigger_trace = 1
    options.options_header = "foo-bar"
    options.ignored = ["baz", "qux"]
    return options

@pytest.fixture(name="mock_xtraceoptions_no_response")
def fixture_xtraceoptions_no_response(mocker):
    options = mocker.Mock()
    options.include_response = False
    return options

@pytest.fixture(name="mock_xtraceoptions_yes_response")
def fixture_xtraceoptions_yes_response(mocker):
    options = mocker.Mock()
    options.include_response = True
    return options

# Other Fixtures, manually used =====================================

@pytest.fixture(name="decision_auth_valid_sig")
def fixture_decision_auth_valid_sig():
    return {
        "do_metrics": 1,
        "do_sample": 1,
        "auth": 0,
        "auth_msg": "foo-bar",
        "decision_type": 1,
        "status_msg": "baz-qux",
    }

@pytest.fixture(name="decision_auth_invalid_sig")
def fixture_decision_auth_invalid_sig():
    return {
        "do_metrics": 0,
        "do_sample": 0,
        "auth": 1,
        "auth_msg": "foo-bar",
    }

@pytest.fixture(name="decision_not_auth_type_zero")
def fixture_decision_not_auth_type_zero():
    return {
        "do_metrics": 1,
        "do_sample": 1,
        "auth": 0,
        "auth_msg": "foo-bar",
        "decision_type": 0,
        "status_msg": "baz-qux",
    }

@pytest.fixture(name="decision_not_auth_type_nonzero")
def fixture_decision_auth_type_nonzero():
    return {
        "do_metrics": 1,
        "do_sample": 1,
        "auth": 0,
        "auth_msg": "foo-bar",
        "decision_type": -1,
        "status_msg": "baz-qux",
    }

@pytest.fixture(name="decision_signed_tt_traced")
def fixture_decision_signed_tt_traced(mocker):
    """Case 8"""
    return {
        "do_sample": 1,
        "decision_type": 1,
        "auth": 0,
        "auth_msg": "ok",
        "status": 0,
        "status_msg": "ok",
    }

@pytest.fixture(name="decision_non_tt_traced")
def fixture_decision_non_tt_traced(mocker):
    """Case 14"""
    return {
        "do_sample": 1,
        "decision_type": 0,
        "auth": -1,
        "auth_msg": "",
        "status": 0,
        "status_msg": "ok",
    }

@pytest.fixture(name="decision_unsigned_tt_not_traced")
def fixture_decision_unsigned_tt_not_traced(mocker):
    """Case 11 - feature disabled"""
    return {
        "do_sample": 0,
        "decision_type": -1,
        "auth": -1,
        "auth_msg": "",
        "status": -3,
        "status_msg": "trigger-tracing-disabled",
    }

@pytest.fixture(name="parent_span_context_valid_remote_no_tracestate")
def fixture_parent_span_context_valid_remote_no_tracestate():
    return SpanContext(
        trace_id=11112222333344445555666677778888,
        span_id=1111222233334444,
        is_remote=True,
        trace_flags=1,
        trace_state=None,
    )

# The Tests =========================================================

class Test_SwSampler():
    def test_init(self, mocker):
        mock_apm_config = mocker.Mock()
        sampler = _SwSampler(mock_apm_config)
        assert sampler.apm_config == mock_apm_config

    def test_calculate_liboboe_decision_is_lambda(
        self,
        mocker,
        parent_span_context_invalid,
        mock_xtraceoptions_signed_tt,
    ):
        mock_apm_config = mocker.Mock()
        mock_get = mocker.Mock(
            side_effect=config_get
        )
        mock_get_tracing_decision = mocker.Mock()
        mock_get_tracing_decision.configure_mock(
            # returns 11 values
            return_value=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        )
        mock_oboe_api = mocker.Mock()
        mock_oboe_api.configure_mock(
            **{
                "getTracingDecision": mock_get_tracing_decision
            }
        )
        mock_oboe_api_component = mocker.patch(
            "solarwinds_apm.extension.oboe.OboeAPI.__init__",
            return_value=mock_oboe_api
        )
        mock_apm_config.configure_mock(
            **{
                "agent_enabled": True,
                "get": mock_get,
                "oboe_api": mock_oboe_api_component,
                "is_lambda": True,
            }
        )
        test_sampler = _SwSampler(mock_apm_config)

        result = test_sampler.calculate_liboboe_decision(
            parent_span_context_invalid,
            'foo',
            None,
            {'foo': 'bar'},
            mock_xtraceoptions_signed_tt,
        )
        mock_get_tracing_decision.assert_called_once()
        assert result == {
            "do_metrics": 0,
            "do_sample": 1,
            "rate": 2,
            "source": 3,
            "bucket_rate": 4,
            "bucket_cap": 5,
            "decision_type": 6,
            "auth": 7,
            "status_msg": 8,
            "auth_msg": 9,
            "status": 10,
        }

    def test_calculate_liboboe_decision_root_span(
        self,
        fixture_swsampler,
        parent_span_context_invalid,
        mock_xtraceoptions_signed_tt,
    ):
        fixture_swsampler.calculate_liboboe_decision(
            parent_span_context_invalid,
            'foo',
            None,
            {'foo': 'bar'},
            mock_xtraceoptions_signed_tt,
        )
        solarwinds_apm.extension.oboe.Context.getDecisions.assert_called_once_with(
            None,
            None,
            -1,
            -1,
            mock_xtraceoptions_signed_tt.trigger_trace,
            -1,
            mock_xtraceoptions_signed_tt.options_header,
            mock_xtraceoptions_signed_tt.signature,
            mock_xtraceoptions_signed_tt.timestamp
        )

    # pylint:disable=unused-argument
    def test_calculate_liboboe_decision_parent_valid_remote(
        self,
        fixture_swsampler,
        mock_traceparent_from_context,
        parent_span_context_valid_remote,
    ):
        fixture_swsampler.calculate_liboboe_decision(
            parent_span_context_valid_remote,
            'foo',
            None,
            {'foo': 'bar'},
        )
        solarwinds_apm.extension.oboe.Context.getDecisions.assert_called_once_with(
            "foo-bar",
            "123",
            -1,
            -1,
            0,
            -1,
            None,
            None,
            None,
        )

    def test_is_decision_continued_false(self, fixture_swsampler):
        assert not fixture_swsampler.is_decision_continued({
            "rate": 0,
            "source": -1,
            "bucket_rate": -1,
            "bucket_cap": -1,
        })
        assert not fixture_swsampler.is_decision_continued({
            "rate": -1,
            "source": 0,
            "bucket_rate": -1,
            "bucket_cap": -1,
        })
        assert not fixture_swsampler.is_decision_continued({
            "rate": -1,
            "source": -1,
            "bucket_rate": 0,
            "bucket_cap": -1,
        })
        assert not fixture_swsampler.is_decision_continued({
            "rate": -1,
            "source": -1,
            "bucket_rate": -1,
            "bucket_cap": 0,
        })

    def test_is_decision_continued_true(self, fixture_swsampler):
        assert fixture_swsampler.is_decision_continued({
            "rate": -1,
            "source": -1,
            "bucket_rate": -1,
            "bucket_cap": -1,
        })

    def test_otel_decision_from_liboboe(self, fixture_swsampler):
        # assert fixture_swsampler.otel_decision_from_liboboe({
        #     "do_metrics": 0,
        #     "do_sample": 0,
        # }) == Decision.DROP
        # assert fixture_swsampler.otel_decision_from_liboboe({
        #     "do_metrics": 1,
        #     "do_sample": 0,
        # }) == Decision.RECORD_ONLY
        assert fixture_swsampler.otel_decision_from_liboboe({
            "do_metrics": 1,
            "do_sample": 1,
        }) == Decision.RECORD_AND_SAMPLE
        # Technically possible but we don't handle this
        assert fixture_swsampler.otel_decision_from_liboboe({
            "do_metrics": 0,
            "do_sample": 1,
        }) == Decision.RECORD_AND_SAMPLE

    def test_create_xtraceoptions_response_value_auth_valid_sig(
        self,
        fixture_swsampler,
        decision_auth_valid_sig,
        parent_span_context_valid_remote,
        mock_xtraceoptions_signed_tt,
    ):
        response_val = fixture_swsampler.create_xtraceoptions_response_value(
            decision_auth_valid_sig,
            parent_span_context_valid_remote,
            mock_xtraceoptions_signed_tt,
        )
        assert response_val == "auth####foo-bar;trigger-trace####baz-qux;ignored####baz....qux"

    def test_create_xtraceoptions_response_value_auth_invalid_sig(
        self,
        fixture_swsampler,
        decision_auth_invalid_sig,
        parent_span_context_valid_remote,
        mock_xtraceoptions_signed_tt,
    ):
        response_val = fixture_swsampler.create_xtraceoptions_response_value(
            decision_auth_invalid_sig,
            parent_span_context_valid_remote,
            mock_xtraceoptions_signed_tt,
        )
        assert response_val == "auth####foo-bar"

    def test_create_xtraceoptions_response_value_tt_unauth_type_nonzero_root_span(
        self,
        fixture_swsampler,
        decision_not_auth_type_nonzero,
        parent_span_context_invalid,
        mock_xtraceoptions_signed_tt,
    ):
        response_val = fixture_swsampler.create_xtraceoptions_response_value(
            decision_not_auth_type_nonzero,
            parent_span_context_invalid,
            mock_xtraceoptions_signed_tt,
        )
        assert response_val == "auth####foo-bar;trigger-trace####baz-qux;ignored####baz....qux"

    def test_create_xtraceoptions_response_value_tt_unauth_type_nonzero_parent_span_remote(
        self,
        fixture_swsampler,
        decision_not_auth_type_nonzero,
        parent_span_context_valid_remote,
        mock_xtraceoptions_signed_tt,
    ):
        response_val = fixture_swsampler.create_xtraceoptions_response_value(
            decision_not_auth_type_nonzero,
            parent_span_context_valid_remote,
            mock_xtraceoptions_signed_tt, 
        )
        assert response_val == "auth####foo-bar;trigger-trace####baz-qux;ignored####baz....qux"

    def test_create_xtraceoptions_response_value_tt_unauth_type_zero_root_span(
        self,
        fixture_swsampler,
        decision_not_auth_type_zero,
        parent_span_context_invalid,
        mock_xtraceoptions_signed_tt,
    ):
        response_val = fixture_swsampler.create_xtraceoptions_response_value(
            decision_not_auth_type_zero,
            parent_span_context_invalid,
            mock_xtraceoptions_signed_tt,
        )
        assert response_val == "auth####foo-bar;trigger-trace####baz-qux;ignored####baz....qux"

    def test_create_xtraceoptions_response_value_tt_unauth_type_zero_parent_span_remote(
        self,
        fixture_swsampler,
        decision_not_auth_type_zero,
        parent_span_context_valid_remote,
        mock_xtraceoptions_signed_tt,
    ):
        response_val = fixture_swsampler.create_xtraceoptions_response_value(
            decision_not_auth_type_zero,
            parent_span_context_valid_remote,
            mock_xtraceoptions_signed_tt,    
        )
        assert response_val == "auth####foo-bar;trigger-trace####ignored;ignored####baz....qux"

    def test_create_xtraceoptions_response_value_not_tt_unauth(
        self,
        fixture_swsampler,
        decision_not_auth_type_nonzero,
        parent_span_context_invalid,
        mock_xtraceoptions_signed_not_tt,
    ):
        response_val = fixture_swsampler.create_xtraceoptions_response_value(
            decision_not_auth_type_nonzero,
            parent_span_context_invalid,
            mock_xtraceoptions_signed_not_tt,     
        )
        assert response_val == "auth####foo-bar;trigger-trace####not-requested;ignored####baz....qux"

    def test_create_xtraceoptions_response_value_case_8(
        self,
        fixture_swsampler,
        decision_signed_tt_traced,
        parent_span_context_invalid,
        mock_xtraceoptions_signed_tt,
    ):
        response_val = fixture_swsampler.create_xtraceoptions_response_value(
            decision_signed_tt_traced,
            parent_span_context_invalid,
            mock_xtraceoptions_signed_tt,   
        )
        assert response_val == "auth####ok;trigger-trace####ok;ignored####baz....qux"

    def test_create_xtraceoptions_response_value_case_14(
        self,
        fixture_swsampler,
        decision_non_tt_traced,
        parent_span_context_invalid,
        mock_xtraceoptions_signed_not_tt,
    ):
        response_val = fixture_swsampler.create_xtraceoptions_response_value(
            decision_non_tt_traced,
            parent_span_context_invalid,
            mock_xtraceoptions_signed_not_tt,   
        )
        assert response_val == "trigger-trace####not-requested;ignored####baz....qux"

    def test_create_xtraceoptions_response_value_case_11(
        self,
        fixture_swsampler,
        decision_unsigned_tt_not_traced,
        parent_span_context_invalid,
        mock_xtraceoptions_unsigned_tt,
    ):
        response_val = fixture_swsampler.create_xtraceoptions_response_value(
            decision_unsigned_tt_not_traced,
            parent_span_context_invalid,
            mock_xtraceoptions_unsigned_tt, 
        )
        assert response_val == "trigger-trace####trigger-tracing-disabled;ignored####baz....qux"

    def test_calculate_trace_state_root_span(
        self,
        fixture_swsampler,
        decision_auth_valid_sig,
        parent_span_context_invalid
    ):
        actual_trace_state = fixture_swsampler.calculate_trace_state(
            decision_auth_valid_sig,
            parent_span_context_invalid
        )
        assert len(actual_trace_state.items()) == 0

    def test_calculate_trace_state_root_span_no_xtraceoptions_response(
        self,
        fixture_swsampler,
        decision_auth_valid_sig,
        parent_span_context_invalid,
        mock_xtraceoptions_no_response
    ):
        actual_trace_state = fixture_swsampler.calculate_trace_state(
            decision_auth_valid_sig,
            parent_span_context_invalid,
            mock_xtraceoptions_no_response
        )
        assert len(actual_trace_state.items()) == 0

    def test_calculate_trace_state_root_span_yes_xtraceoptions_response(
        self,
        mocker,
        fixture_swsampler,
        decision_auth_valid_sig,
        parent_span_context_invalid,
        mock_xtraceoptions_yes_response
    ):
        mocker.patch(
            "solarwinds_apm.sampler._SwSampler.create_xtraceoptions_response_value",
            return_value="bar"
        )
        expected_trace_state = TraceState([
            ["xtrace_options_response", "bar"]
        ])
        actual_trace_state = fixture_swsampler.calculate_trace_state(
            decision_auth_valid_sig,
            parent_span_context_invalid,
            mock_xtraceoptions_yes_response
        )
        assert len(actual_trace_state.items()) == 1
        assert expected_trace_state.get("xtrace_options_response") == actual_trace_state.get("xtrace_options_response")

    def test_calculate_trace_state_is_remote_create(
        self,
        mocker,
        fixture_swsampler,
        decision_auth_valid_sig,
        parent_span_context_valid_remote_no_tracestate
    ):
        actual_trace_state = fixture_swsampler.calculate_trace_state(
            decision_auth_valid_sig,
            parent_span_context_valid_remote_no_tracestate
        )
        assert len(actual_trace_state.items()) == 0

    def test_calculate_trace_state_is_remote_update(
        self,
        mocker,
        fixture_swsampler,
        decision_auth_valid_sig,
        parent_span_context_valid_remote,
        mock_xtraceoptions_signed_tt,
    ):
        mocker.patch(
            "solarwinds_apm.sampler._SwSampler.create_xtraceoptions_response_value",
            return_value="bar"
        )
        assert parent_span_context_valid_remote.trace_state == TraceState([
            ["sw", "123"]
        ])
        expected_trace_state = TraceState([
            ["sw", "123"],
            ["xtrace_options_response", "bar"]
        ])
        actual_trace_state = fixture_swsampler.calculate_trace_state(
            decision_auth_valid_sig,
            parent_span_context_valid_remote,
            mock_xtraceoptions_signed_tt,
        )
        assert expected_trace_state.get("sw") == actual_trace_state.get("sw")
        assert expected_trace_state.get("xtrace_options_response") == actual_trace_state.get("xtrace_options_response")

    def should_sample_test_helper(
        self,
        mocker,
        fixture_swsampler,
        parent_context,
        expected_xto,
    ):
        mock_get_current_span = mocker.patch("solarwinds_apm.sampler.get_current_span")
        mock_get_current_span.configure_mock(
            return_value=mocker.Mock(
                **{
                    "get_span_context.return_value": "my_span_context",
                }
            )
        )
        mock_xtraceoptions_cls = mocker.patch(
            "solarwinds_apm.sampler.XTraceOptions"
        )
        mock_xtraceoptions = mocker.Mock()
        mock_xtraceoptions_cls.configure_mock(
            return_value=mock_xtraceoptions
        )
        mocker.patch(
            "solarwinds_apm.sampler._SwSampler.calculate_liboboe_decision",
            return_value="my_decision"
        )
        mocker.patch(
            "solarwinds_apm.sampler._SwSampler.calculate_trace_state",
            return_value="my_trace_state"
        )
        mocker.patch(
            "solarwinds_apm.sampler._SwSampler.calculate_attributes",
            return_value="my_attributes"
        )
        mocker.patch(
            "solarwinds_apm.sampler._SwSampler.otel_decision_from_liboboe",
            return_value=Decision.RECORD_AND_SAMPLE
        )

        if not parent_context:
            expected_xto = mock_xtraceoptions

        sampling_result = fixture_swsampler.should_sample(
            parent_context=parent_context,
            trace_id=123,
            name="foo",
            attributes={"foo": "bar"}
        )

        _SwSampler.calculate_liboboe_decision.assert_called_once_with(
            "my_span_context",
            'foo',
            None,
            {'foo': 'bar'},
            expected_xto,
        )
        _SwSampler.calculate_trace_state.assert_called_once_with(
            "my_decision",
            "my_span_context",
            expected_xto,
        )
        _SwSampler.calculate_attributes.assert_called_once_with(
            "foo",
            {"foo": "bar"},
            "my_decision",
            "my_trace_state",
            "my_span_context",
            expected_xto,
        )
        _SwSampler.otel_decision_from_liboboe.assert_called_once_with(
            "my_decision"
        )
        assert sampling_result.attributes == "my_attributes"
        assert sampling_result.decision == Decision.RECORD_AND_SAMPLE
        assert sampling_result.trace_state == "my_trace_state"

    def test_should_sample_no_parent_context(
        self,
        mocker,
        fixture_swsampler,
    ):
        mock_parent_context = None
        self.should_sample_test_helper(
            mocker,
            fixture_swsampler,
            mock_parent_context,
            "not-used",
        )

    def test_should_sample_yes_parent_context(
        self,
        mocker,
        fixture_swsampler,
    ):
        mock_parent_context = mocker.Mock()
        mock_parent_context.configure_mock(
            **{
                "get": mocker.Mock(
                    return_value="foo_xto"
                )
            }
        )
        self.should_sample_test_helper(
            mocker,
            fixture_swsampler,
            mock_parent_context,
            "foo_xto",
        )

class TestParentBasedSwSampler():
    def test_init(self, mocker):
        sampler = ParentBasedSwSampler(mocker.Mock())
        assert type(sampler._root) == _SwSampler
        assert type(sampler._remote_parent_sampled) == _SwSampler
        assert type(sampler._remote_parent_not_sampled) == _SwSampler
        assert type(sampler._local_parent_sampled) == StaticSampler
        assert type(sampler._local_parent_not_sampled) == StaticSampler

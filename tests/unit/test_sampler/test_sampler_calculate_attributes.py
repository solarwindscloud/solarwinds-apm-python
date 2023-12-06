# © 2023 SolarWinds Worldwide, LLC. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at:http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

import pytest
from types import MappingProxyType

from opentelemetry.trace.span import (
    INVALID_SPAN_CONTEXT,
    TraceState
)

from solarwinds_apm.sampler import _SwSampler

# pylint: disable=unused-import
from .fixtures.parent_span_context import (
    fixture_parent_span_context_invalid,
    fixture_parent_span_context_valid_remote,
)
from .fixtures.sampler import fixture_swsampler
from .fixtures.span_id_from_sw import fixture_mock_span_id_from_sw
from .fixtures.sw_from_span_and_decision import fixture_mock_sw_from_span_and_decision

# Otel Fixtures =========================================

@pytest.fixture(name="tracestate_with_sw_and_others")
def fixture_tracestate_with_sw_and_others():
    return TraceState([
        ["foo", "bar"],
        ["sw", "123"],
        ["baz", "qux"]
    ])

@pytest.fixture(name="attributes_no_tracestate")
def fixture_attributes_no_tracestate():
    return MappingProxyType({
        "foo": "bar",
        "baz": "qux"
    })

@pytest.fixture(name="attributes_with_tracestate")
def fixture_attributes_with_tracestate():
    return MappingProxyType({
        "foo": "bar",
        "sw.w3c.tracestate": "some=other,sw=before",
        "baz": "qux"
    })

# Decision Fixtures =====================================

@pytest.fixture(name="decision_drop")
def fixture_decision_drop():
    return {
        "do_metrics": 0,
        "do_sample": 0,
    }

@pytest.fixture(name="decision_record_only_regular")
def fixture_decision_record_only_regular():
    return {
        "do_metrics": 1,
        "do_sample": 0,
    }

@pytest.fixture(name="decision_record_and_sample_regular")
def fixture_decision_record_and_sample_regular():
    return {
        "do_metrics": 1,
        "do_sample": 1,
        "rate": 1000000,
        "source": 6,
        "bucket_rate": 14.7,
        "bucket_cap": 267.0,
        "decision_type": 0,
        "auth": -1,
        "status_msg": "ok",
        "auth_msg": "",
        "status": 0,
    }

@pytest.fixture(name="decision_record_and_sample_unsigned_tt")
def fixture_decision_record_and_sample_unsigned_tt():
    return {
        "do_metrics": 1,
        "do_sample": 1,
        "rate": -1,
        "source": -1,
        "bucket_rate": 0.1,
        "bucket_cap": 6.0,
        "decision_type": 1,
        "auth": -1,
        "status_msg": "ok",
        "auth_msg": "",
        "status": 0,
    }

@pytest.fixture(name="decision_record_and_sample_signed_tt_auth_ok")
def fixture_decision_record_and_sample_signed_tt_auth_ok():
    return {
        "do_metrics": 1,
        "do_sample": 1,
        "rate": -1,
        "source": -1,
        "bucket_rate": 0.1,
        "bucket_cap": 6.0,
        "decision_type": 1,
        "auth": 0,
        "status_msg": "ok",
        "auth_msg": "ok",
        "status": 0,
    }

@pytest.fixture(name="decision_record_only_signed_tt_auth_failed")
def fixture_decision_record_only_signed_tt_auth_failed():
    return {
        "do_metrics": 1,
        "do_sample": 0,
        "rate": 1000000,
        "source": 6,
        "bucket_rate": 0.0,
        "bucket_cap": 0.0,
        "decision_type": -1,
        "auth": 2,
        "status_msg": "bad-signature",
        "auth_msg": "auth-failed",
        "status": -5,
    }

@pytest.fixture(name="decision_not_continued")
def fixture_decision_not_continued():
    return {
        "do_metrics": 1,
        "do_sample": 1,
        "rate": 1,
        "source": 1,
        "bucket_rate": 1,
        "bucket_cap": 1,
    }

@pytest.fixture(name="decision_continued")
def fixture_decision_continued():
    return {
        "do_metrics": 1,
        "do_sample": 1,
        "rate": -1,
        "source": -1,
        "bucket_rate": -1,
        "bucket_cap": -1,
    }

# XTraceOptions Fixtures ================================
## Empty
@pytest.fixture(name="mock_xtraceoptions_empty")
def fixture_xtraceoptions_empty(mocker):
    options = mocker.Mock()
    options.sw_keys = ""
    options.custom_kvs = {}
    return options

## Unsigned

@pytest.fixture(name="mock_xtraceoptions_sw_keys_and_custom_keys_no_tt_unsigned")
def fixture_xtraceoptions_sw_keys_and_custom_keys_no_tt_unsigned(mocker):
    options = mocker.Mock()
    options.sw_keys = "foo"
    options.custom_kvs = {"custom-foo": "awesome-bar"}
    return options

@pytest.fixture(name="mock_xtraceoptions_sw_keys_and_custom_keys_and_unsigned_tt")
def fixture_xtraceoptions_sw_keys_and_custom_keys_and_unsigned_tt(mocker):
    options = mocker.Mock()
    options.sw_keys = "foo"
    options.custom_kvs = {"custom-foo": "awesome-bar"}
    options.trigger_trace = 1
    return options

@pytest.fixture(name="mock_xtraceoptions_no_sw_keys_nor_custom_keys_nor_tt_unsigned")
def fixture_xtraceoptions_no_sw_keys_nor_custom_keys_nor_tt_unsigned(mocker):
    options = mocker.Mock()
    options.sw_keys = ""
    options.custom_kvs = {}
    return options

@pytest.fixture(name="mock_xtraceoptions_no_sw_keys_nor_custom_keys_with_unsigned_tt")
def fixture_xtraceoptions_no_sw_keys_nor_custom_keys_with_unsigned_tt(mocker):
    options = mocker.Mock()
    options.sw_keys = ""
    options.custom_kvs = {}
    options.trigger_trace = 1
    return options

## Signed

@pytest.fixture(name="mock_xtraceoptions_sw_keys_and_custom_keys_no_tt_signed")
def fixture_xtraceoptions_sw_keys_and_custom_keys_no_tt_signed(mocker):
    options = mocker.Mock()
    options.sw_keys = "foo"
    options.custom_kvs = {"custom-foo": "awesome-bar"}
    options.signature = "foo-sig"
    options.timestamp = 12345
    return options

@pytest.fixture(name="mock_xtraceoptions_sw_keys_and_custom_keys_and_signed_tt")
def fixture_xtraceoptions_sw_keys_and_custom_keys_and_signed_tt(mocker):
    options = mocker.Mock()
    options.sw_keys = "foo"
    options.custom_kvs = {"custom-foo": "awesome-bar"}
    options.signature = "foo-sig"
    options.timestamp = 12345
    options.trigger_trace = 1
    return options

@pytest.fixture(name="mock_xtraceoptions_no_sw_keys_nor_custom_keys_nor_tt_signed")
def fixture_xtraceoptions_no_sw_keys_nor_custom_keys_nor_tt_signed(mocker):
    options = mocker.Mock()
    options.sw_keys = ""
    options.custom_kvs = {}
    options.signature = "foo-sig"
    options.timestamp = 12345
    return options

@pytest.fixture(name="mock_xtraceoptions_no_sw_keys_nor_custom_keys_with_signed_tt")
def fixture_xtraceoptions_no_sw_keys_nor_custom_keys_with_signed_tt(mocker):
    options = mocker.Mock()
    options.sw_keys = ""
    options.custom_kvs = {}
    options.signature = "foo-sig"
    options.timestamp = 12345
    options.trigger_trace = 1
    return options



# The Tests =========================================================

class Test_SwSampler_calculate_attributes():
    """
    Separate _SwSampler.calculate_attributes tests for so many 
    possible x-trace-options, x-trace-options-signature, decision cases
    """
    def test_init(self, mocker):
        mock_apm_config = mocker.Mock()
        sampler = _SwSampler(mock_apm_config)
        assert sampler.apm_config == mock_apm_config

    # def test_decision_drop_with_no_sw_keys_nor_custom_keys_nor_tt_unsigned(
    #     self,
    #     mocker,
    #     fixture_swsampler,
    #     decision_drop,
    #     mock_xtraceoptions_no_sw_keys_nor_custom_keys_nor_tt_unsigned,
    # ):
    #     assert fixture_swsampler.calculate_attributes(
    #         span_name="foo",
    #         attributes=mocker.Mock(),
    #         decision=decision_drop,
    #         trace_state=mocker.Mock(),
    #         parent_span_context=mocker.Mock(),
    #         xtraceoptions=mock_xtraceoptions_no_sw_keys_nor_custom_keys_nor_tt_unsigned,
    #     ) is None

    # def test_decision_drop_with_sw_keys_and_custom_keys_no_tt_unsigned(
    #     self,
    #     mocker,
    #     fixture_swsampler,
    #     decision_drop,
    #     mock_xtraceoptions_sw_keys_and_custom_keys_no_tt_unsigned,
    # ):
    #     assert fixture_swsampler.calculate_attributes(
    #         span_name="foo",
    #         attributes=mocker.Mock(),
    #         decision=decision_drop,
    #         trace_state=mocker.Mock(),
    #         parent_span_context=mocker.Mock(),
    #         xtraceoptions=mock_xtraceoptions_sw_keys_and_custom_keys_no_tt_unsigned,
    #     ) is None

    # def test_decision_drop_with_no_sw_keys_nor_custom_keys_nor_tt_signed(
    #     self,
    #     mocker,
    #     fixture_swsampler,
    #     decision_drop,
    #     mock_xtraceoptions_no_sw_keys_nor_custom_keys_nor_tt_signed,
    # ):
    #     assert fixture_swsampler.calculate_attributes(
    #         span_name="foo",
    #         attributes=mocker.Mock(),
    #         decision=decision_drop,
    #         trace_state=mocker.Mock(),
    #         parent_span_context=mocker.Mock(),
    #         xtraceoptions=mock_xtraceoptions_no_sw_keys_nor_custom_keys_nor_tt_signed,
    #     ) is None

    # def test_decision_drop_with_sw_keys_and_custom_keys_no_tt_signed(
    #     self,
    #     mocker,
    #     fixture_swsampler,
    #     decision_drop,
    #     mock_xtraceoptions_sw_keys_and_custom_keys_no_tt_signed,
    # ):
    #     assert fixture_swsampler.calculate_attributes(
    #         span_name="foo",
    #         attributes=mocker.Mock(),
    #         decision=decision_drop,
    #         trace_state=mocker.Mock(),
    #         parent_span_context=mocker.Mock(),
    #         xtraceoptions=mock_xtraceoptions_sw_keys_and_custom_keys_no_tt_signed,
    #     ) is None

    # def test_decision_record_only_with_custom_and_sw_keys_no_tt_unsigned(
    #     self,
    #     mocker,
    #     fixture_swsampler,
    #     decision_record_only_regular,
    #     mock_xtraceoptions_sw_keys_and_custom_keys_no_tt_unsigned,
    # ):
    #     assert fixture_swsampler.calculate_attributes(
    #         span_name="foo",
    #         attributes=mocker.Mock(),
    #         decision=decision_record_only_regular,
    #         trace_state=mocker.Mock(),
    #         parent_span_context=mocker.Mock(),
    #         xtraceoptions=mock_xtraceoptions_sw_keys_and_custom_keys_no_tt_unsigned,
    #     ) is None

    # def test_decision_record_only_with_custom_and_sw_keys_no_tt_signed(
    #     self,
    #     mocker,
    #     fixture_swsampler,
    #     decision_record_only_regular,
    #     mock_xtraceoptions_sw_keys_and_custom_keys_no_tt_signed,
    # ):
    #     assert fixture_swsampler.calculate_attributes(
    #         span_name="foo",
    #         attributes=mocker.Mock(),
    #         decision=decision_record_only_regular,
    #         trace_state=mocker.Mock(),
    #         parent_span_context=mocker.Mock(),
    #         xtraceoptions=mock_xtraceoptions_sw_keys_and_custom_keys_no_tt_signed,
    #     ) is None

    def test_decision_record_and_sample_with_sw_keys_and_custom_keys_no_tt_unsigned(
        self,
        fixture_swsampler,
        decision_record_and_sample_unsigned_tt,
        parent_span_context_invalid,
        mock_xtraceoptions_sw_keys_and_custom_keys_no_tt_unsigned,
    ):
        assert fixture_swsampler.calculate_attributes(
            span_name="foo",
            attributes=None,
            decision=decision_record_and_sample_unsigned_tt,
            trace_state=None,
            parent_span_context=parent_span_context_invalid,
            xtraceoptions=mock_xtraceoptions_sw_keys_and_custom_keys_no_tt_unsigned,
        ) == MappingProxyType({
            "BucketCapacity": "6.0",
            "BucketRate": "0.1",
            "SampleRate": -1,
            "SampleSource": -1,
            "SWKeys": "foo",
            "custom-foo": "awesome-bar",
        })

    def test_decision_auth_ok_with_sw_keys_and_custom_keys_no_tt_signed(
        self,
        fixture_swsampler,
        decision_record_and_sample_signed_tt_auth_ok,
        parent_span_context_invalid,
        mock_xtraceoptions_sw_keys_and_custom_keys_no_tt_signed,
    ):
        assert fixture_swsampler.calculate_attributes(
            span_name="foo",
            attributes=None,
            decision=decision_record_and_sample_signed_tt_auth_ok,
            trace_state=None,
            parent_span_context=parent_span_context_invalid,
            xtraceoptions=mock_xtraceoptions_sw_keys_and_custom_keys_no_tt_signed,
        ) == MappingProxyType({
            "BucketCapacity": "6.0",
            "BucketRate": "0.1",
            "SampleRate": -1,
            "SampleSource": -1,
            "SWKeys": "foo",
            "custom-foo": "awesome-bar",
        })

    # def test_decision_auth_failed_with_sw_keys_and_custom_keys_no_tt_signed(
    #     self,
    #     fixture_swsampler,
    #     decision_record_only_signed_tt_auth_failed,
    #     parent_span_context_invalid,
    #     mock_xtraceoptions_sw_keys_and_custom_keys_no_tt_signed,
    # ):
    #     assert fixture_swsampler.calculate_attributes(
    #         span_name="foo",
    #         attributes=None,
    #         decision=decision_record_only_signed_tt_auth_failed,
    #         trace_state=None,
    #         parent_span_context=parent_span_context_invalid,
    #         xtraceoptions=mock_xtraceoptions_sw_keys_and_custom_keys_no_tt_signed,
    #     ) is None

    def test_decision_auth_ok_with_sw_keys_and_custom_keys_and_signed_tt(
        self,
        fixture_swsampler,
        decision_record_and_sample_signed_tt_auth_ok,
        parent_span_context_invalid,
        mock_xtraceoptions_sw_keys_and_custom_keys_and_signed_tt,
    ):
        assert fixture_swsampler.calculate_attributes(
            span_name="foo",
            attributes=None,
            decision=decision_record_and_sample_signed_tt_auth_ok,
            trace_state=None,
            parent_span_context=parent_span_context_invalid,
            xtraceoptions=mock_xtraceoptions_sw_keys_and_custom_keys_and_signed_tt,
        ) == MappingProxyType({
            "BucketCapacity": "6.0",
            "BucketRate": "0.1",
            "SampleRate": -1,
            "SampleSource": -1,
            "TriggeredTrace": True,
            "SWKeys": "foo",
            "custom-foo": "awesome-bar",
        })

    # def test_decision_auth_failed_with_sw_keys_and_custom_keys_and_signed_tt(
    #     self,
    #     fixture_swsampler,
    #     decision_record_only_signed_tt_auth_failed,
    #     parent_span_context_invalid,
    #     mock_xtraceoptions_sw_keys_and_custom_keys_and_signed_tt,
    # ):
    #     assert fixture_swsampler.calculate_attributes(
    #         span_name="foo",
    #         attributes=None,
    #         decision=decision_record_only_signed_tt_auth_failed,
    #         trace_state=None,
    #         parent_span_context=parent_span_context_invalid,
    #         xtraceoptions=mock_xtraceoptions_sw_keys_and_custom_keys_and_signed_tt,
    #     ) is None

    def test_contd_decision_sw_keys_and_custom_keys_and_unsigned_tt(
        self,
        fixture_swsampler,
        decision_continued,
        parent_span_context_invalid,
        mock_xtraceoptions_sw_keys_and_custom_keys_and_unsigned_tt
    ):
        assert fixture_swsampler.calculate_attributes(
            span_name="foo",
            attributes=None,
            decision=decision_continued,
            trace_state=None,
            parent_span_context=parent_span_context_invalid,
            xtraceoptions=mock_xtraceoptions_sw_keys_and_custom_keys_and_unsigned_tt,
        ) == MappingProxyType({
            "BucketCapacity": "-1",
            "BucketRate": "-1",
            "SampleRate": -1,
            "SampleSource": -1,
            "TriggeredTrace": True,
            "SWKeys": "foo",
            "custom-foo": "awesome-bar",
        })

    def test_contd_decision_sw_keys_and_custom_keys_and_signed_tt(
        self,
        fixture_swsampler,
        decision_continued,
        parent_span_context_invalid,
        mock_xtraceoptions_sw_keys_and_custom_keys_and_signed_tt
    ):
        assert fixture_swsampler.calculate_attributes(
            span_name="foo",
            attributes=None,
            decision=decision_continued,
            trace_state=None,
            parent_span_context=parent_span_context_invalid,
            xtraceoptions=mock_xtraceoptions_sw_keys_and_custom_keys_and_signed_tt,
        ) == MappingProxyType({
            "BucketCapacity": "-1",
            "BucketRate": "-1",
            "SampleRate": -1,
            "SampleSource": -1,
            "TriggeredTrace": True,
            "SWKeys": "foo",
            "custom-foo": "awesome-bar",
        })

    def test_contd_decision_with_no_sw_keys_nor_custom_keys_nor_tt_unsigned(
        self,
        fixture_swsampler,
        decision_continued,
        parent_span_context_invalid,
        mock_xtraceoptions_no_sw_keys_nor_custom_keys_nor_tt_unsigned
    ):
        assert fixture_swsampler.calculate_attributes(
            span_name="foo",
            attributes=None,
            decision=decision_continued,
            trace_state=None,
            parent_span_context=parent_span_context_invalid,
            xtraceoptions=mock_xtraceoptions_no_sw_keys_nor_custom_keys_nor_tt_unsigned,
        ) == MappingProxyType({
            "BucketCapacity": "-1",
            "BucketRate": "-1",
            "SampleRate": -1,
            "SampleSource": -1,
        })

    def test_contd_decision_with_no_sw_keys_nor_custom_keys_nor_tt_signed(
        self,
        fixture_swsampler,
        decision_continued,
        parent_span_context_invalid,
        mock_xtraceoptions_no_sw_keys_nor_custom_keys_nor_tt_unsigned
    ):
        assert fixture_swsampler.calculate_attributes(
            span_name="foo",
            attributes=None,
            decision=decision_continued,
            trace_state=None,
            parent_span_context=parent_span_context_invalid,
            xtraceoptions=mock_xtraceoptions_no_sw_keys_nor_custom_keys_nor_tt_unsigned,
        ) == MappingProxyType({
            "BucketCapacity": "-1",
            "BucketRate": "-1",
            "SampleRate": -1,
            "SampleSource": -1,
        })

    def test_contd_decision_with_no_sw_keys_nor_custom_keys_with_unsigned_tt(
        self,
        fixture_swsampler,
        decision_continued,
        parent_span_context_invalid,
        mock_xtraceoptions_no_sw_keys_nor_custom_keys_with_unsigned_tt
    ):
        assert fixture_swsampler.calculate_attributes(
            span_name="foo",
            attributes=None,
            decision=decision_continued,
            trace_state=None,
            parent_span_context=parent_span_context_invalid,
            xtraceoptions=mock_xtraceoptions_no_sw_keys_nor_custom_keys_with_unsigned_tt,
        ) == MappingProxyType({
            "BucketCapacity": "-1",
            "BucketRate": "-1",
            "SampleRate": -1,
            "SampleSource": -1,
            "TriggeredTrace": True,
        })

    def test_contd_decision_with_no_sw_keys_nor_custom_keys_with_signed_tt(
        self,
        fixture_swsampler,
        decision_continued,
        parent_span_context_invalid,
        mock_xtraceoptions_no_sw_keys_nor_custom_keys_with_signed_tt
    ):
        assert fixture_swsampler.calculate_attributes(
            span_name="foo",
            attributes=None,
            decision=decision_continued,
            trace_state=None,
            parent_span_context=parent_span_context_invalid,
            xtraceoptions=mock_xtraceoptions_no_sw_keys_nor_custom_keys_with_signed_tt,
        ) == MappingProxyType({
            "BucketCapacity": "-1",
            "BucketRate": "-1",
            "SampleRate": -1,
            "SampleSource": -1,
            "TriggeredTrace": True,
        })

    def test_not_contd_decision_with_sw_keys_and_custom_keys_and_unsigned_tt(
        self,
        fixture_swsampler,
        decision_not_continued,
        parent_span_context_invalid,
        mock_xtraceoptions_sw_keys_and_custom_keys_and_unsigned_tt
    ):
        assert fixture_swsampler.calculate_attributes(
            span_name="foo",
            attributes=None,
            decision=decision_not_continued,
            trace_state=None,
            parent_span_context=parent_span_context_invalid,
            xtraceoptions=mock_xtraceoptions_sw_keys_and_custom_keys_and_unsigned_tt,
        ) == MappingProxyType({
            "BucketCapacity": "1",
            "BucketRate": "1",
            "SampleRate": 1,
            "SampleSource": 1,
            "TriggeredTrace": True,
            "SWKeys": "foo",
            "custom-foo": "awesome-bar",
        })

    def test_not_contd_decision_with_sw_keys_and_custom_keys_and_signed_tt(
        self,
        fixture_swsampler,
        decision_not_continued,
        parent_span_context_invalid,
        mock_xtraceoptions_sw_keys_and_custom_keys_and_signed_tt
    ):
        assert fixture_swsampler.calculate_attributes(
            span_name="foo",
            attributes=None,
            decision=decision_not_continued,
            trace_state=None,
            parent_span_context=parent_span_context_invalid,
            xtraceoptions=mock_xtraceoptions_sw_keys_and_custom_keys_and_signed_tt,
        ) == MappingProxyType({
            "BucketCapacity": "1",
            "BucketRate": "1",
            "SampleRate": 1,
            "SampleSource": 1,
            "TriggeredTrace": True,
            "SWKeys": "foo",
            "custom-foo": "awesome-bar",
        })

    def test_not_contd_decision_with_no_sw_keys_nor_custom_keys_with_unsigned_tt(
        self,
        fixture_swsampler,
        decision_not_continued,
        parent_span_context_invalid,
        mock_xtraceoptions_no_sw_keys_nor_custom_keys_with_unsigned_tt
    ):
        assert fixture_swsampler.calculate_attributes(
            span_name="foo",
            attributes=None,
            decision=decision_not_continued,
            trace_state=None,
            parent_span_context=parent_span_context_invalid,
            xtraceoptions=mock_xtraceoptions_no_sw_keys_nor_custom_keys_with_unsigned_tt
        ) == MappingProxyType({
            "BucketCapacity": "1",
            "BucketRate": "1",
            "SampleRate": 1,
            "SampleSource": 1,
            "TriggeredTrace": True,
        })

    def test_not_contd_decision_with_no_sw_keys_nor_custom_keys_with_signed_tt(
        self,
        fixture_swsampler,
        decision_not_continued,
        parent_span_context_invalid,
        mock_xtraceoptions_no_sw_keys_nor_custom_keys_with_signed_tt
    ):
        assert fixture_swsampler.calculate_attributes(
            span_name="foo",
            attributes=None,
            decision=decision_not_continued,
            trace_state=None,
            parent_span_context=parent_span_context_invalid,
            xtraceoptions=mock_xtraceoptions_no_sw_keys_nor_custom_keys_with_signed_tt
        ) == MappingProxyType({
            "BucketCapacity": "1",
            "BucketRate": "1",
            "SampleRate": 1,
            "SampleSource": 1,
            "TriggeredTrace": True,
        })

    def test_not_contd_decision_with_no_sw_keys_nor_custom_keys_nor_tt_unsigned(
        self,
        fixture_swsampler,
        decision_not_continued,
        parent_span_context_invalid,
        mock_xtraceoptions_no_sw_keys_nor_custom_keys_nor_tt_unsigned
    ):
        assert fixture_swsampler.calculate_attributes(
            span_name="foo",
            attributes=None,
            decision=decision_not_continued,
            trace_state=None,
            parent_span_context=parent_span_context_invalid,
            xtraceoptions=mock_xtraceoptions_no_sw_keys_nor_custom_keys_nor_tt_unsigned
        ) == MappingProxyType({
            "BucketCapacity": "1",
            "BucketRate": "1",
            "SampleRate": 1,
            "SampleSource": 1,
        })

    def test_not_contd_decision_with_no_sw_keys_nor_custom_keys_nor_tt_signed(
        self,
        fixture_swsampler,
        decision_not_continued,
        parent_span_context_invalid,
        mock_xtraceoptions_no_sw_keys_nor_custom_keys_nor_tt_signed
    ):
        assert fixture_swsampler.calculate_attributes(
            span_name="foo",
            attributes=None,
            decision=decision_not_continued,
            trace_state=None,
            parent_span_context=parent_span_context_invalid,
            xtraceoptions=mock_xtraceoptions_no_sw_keys_nor_custom_keys_nor_tt_signed
        ) == MappingProxyType({
            "BucketCapacity": "1",
            "BucketRate": "1",
            "SampleRate": 1,
            "SampleSource": 1,
        })

    def test_valid_parent_create_new_attrs_with_sw_keys_and_custom_keys_and_unsigned_tt(
        self,
        fixture_swsampler,
        decision_continued,
        tracestate_with_sw_and_others,
        parent_span_context_valid_remote,
        mock_xtraceoptions_sw_keys_and_custom_keys_and_unsigned_tt
    ):
        assert fixture_swsampler.calculate_attributes(
            span_name="foo",
            attributes=None,
            decision=decision_continued,
            trace_state=tracestate_with_sw_and_others,
            parent_span_context=parent_span_context_valid_remote,
            xtraceoptions=mock_xtraceoptions_sw_keys_and_custom_keys_and_unsigned_tt,
        ) == MappingProxyType({
            "BucketCapacity": "-1",
            "BucketRate": "-1",
            "SampleRate": -1,
            "SampleSource": -1,
            "TriggeredTrace": True,
            "sw.tracestate_parent_id": "1111222233334444",
            "sw.w3c.tracestate": "foo=bar,sw=123,baz=qux",
            "SWKeys": "foo",
            "custom-foo": "awesome-bar",
        })

    def test_valid_parent_create_new_attrs_with_sw_keys_and_custom_keys_and_signed_tt(
        self,
        fixture_swsampler,
        decision_continued,
        tracestate_with_sw_and_others,
        parent_span_context_valid_remote,
        mock_xtraceoptions_sw_keys_and_custom_keys_and_signed_tt
    ):
        assert fixture_swsampler.calculate_attributes(
            span_name="foo",
            attributes=None,
            decision=decision_continued,
            trace_state=tracestate_with_sw_and_others,
            parent_span_context=parent_span_context_valid_remote,
            xtraceoptions=mock_xtraceoptions_sw_keys_and_custom_keys_and_signed_tt,
        ) == MappingProxyType({
            "BucketCapacity": "-1",
            "BucketRate": "-1",
            "SampleRate": -1,
            "SampleSource": -1,
            "TriggeredTrace": True,
            "sw.tracestate_parent_id": "1111222233334444",
            "sw.w3c.tracestate": "foo=bar,sw=123,baz=qux",
            "SWKeys": "foo",
            "custom-foo": "awesome-bar",
        })

    def test_valid_parent_update_attrs_no_tracestate_capture_with_sw_keys_and_custom_keys_and_unsigned_tt(
        self,
        fixture_swsampler,
        attributes_no_tracestate,
        decision_continued,
        tracestate_with_sw_and_others,
        parent_span_context_valid_remote,
        mock_xtraceoptions_sw_keys_and_custom_keys_and_unsigned_tt
    ):
        result = fixture_swsampler.calculate_attributes(
            span_name="foo",
            attributes=attributes_no_tracestate,
            decision=decision_continued,
            trace_state=tracestate_with_sw_and_others,
            parent_span_context=parent_span_context_valid_remote,
            xtraceoptions=mock_xtraceoptions_sw_keys_and_custom_keys_and_unsigned_tt,
        )
        expected = MappingProxyType({
            "foo": "bar",
            "baz": "qux",
            "BucketCapacity": "-1",
            "BucketRate": "-1",
            "SampleRate": -1,
            "SampleSource": -1,
            "TriggeredTrace": True,
            "sw.tracestate_parent_id": "1111222233334444",
            "sw.w3c.tracestate": "foo=bar,sw=123,baz=qux",
            "SWKeys": "foo",
            "custom-foo": "awesome-bar",
        })
        for e_key, e_val in expected.items():
            assert result.get(e_key) == e_val

    def test_valid_parent_update_attrs_no_tracestate_capture_with_sw_keys_and_custom_keys_and_signed_tt(
        self,
        fixture_swsampler,
        attributes_no_tracestate,
        decision_continued,
        tracestate_with_sw_and_others,
        parent_span_context_valid_remote,
        mock_xtraceoptions_sw_keys_and_custom_keys_and_signed_tt
    ):
        result = fixture_swsampler.calculate_attributes(
            span_name="foo",
            attributes=attributes_no_tracestate,
            decision=decision_continued,
            trace_state=tracestate_with_sw_and_others,
            parent_span_context=parent_span_context_valid_remote,
            xtraceoptions=mock_xtraceoptions_sw_keys_and_custom_keys_and_signed_tt,
        )
        expected = MappingProxyType({
            "foo": "bar",
            "baz": "qux",
            "BucketCapacity": "-1",
            "BucketRate": "-1",
            "SampleRate": -1,
            "SampleSource": -1,
            "TriggeredTrace": True,
            "sw.tracestate_parent_id": "1111222233334444",
            "sw.w3c.tracestate": "foo=bar,sw=123,baz=qux",
            "SWKeys": "foo",
            "custom-foo": "awesome-bar",
        })
        for e_key, e_val in expected.items():
            assert result.get(e_key) == e_val

    def test_valid_parent_update_attrs_tracestate_capture_with_sw_keys_and_custom_keys_and_unsigned_tt(
        self,
        fixture_swsampler,
        attributes_with_tracestate,
        decision_continued,
        tracestate_with_sw_and_others,
        parent_span_context_valid_remote,
        mock_xtraceoptions_sw_keys_and_custom_keys_and_unsigned_tt
    ):
        result = fixture_swsampler.calculate_attributes(
            span_name="foo",
            attributes=attributes_with_tracestate,
            decision=decision_continued,
            trace_state=tracestate_with_sw_and_others,
            parent_span_context=parent_span_context_valid_remote,
            xtraceoptions=mock_xtraceoptions_sw_keys_and_custom_keys_and_unsigned_tt,
        )
        expected = MappingProxyType({
            "foo": "bar",
            "baz": "qux",
            "BucketCapacity": "-1",
            "BucketRate": "-1",
            "SampleRate": -1,
            "SampleSource": -1,
            "TriggeredTrace": True,
            "sw.tracestate_parent_id": "1111222233334444",
            "sw.w3c.tracestate": "sw=1111222233334444-01,some=other",
            "SWKeys": "foo",
            "custom-foo": "awesome-bar",
        })
        for e_key, e_val in expected.items():
            assert result.get(e_key) == e_val

    def test_valid_parent_update_attrs_tracestate_capture_with_sw_keys_and_custom_keys_and_signed_tt(
        self,
        fixture_swsampler,
        attributes_with_tracestate,
        decision_continued,
        tracestate_with_sw_and_others,
        parent_span_context_valid_remote,
        mock_xtraceoptions_sw_keys_and_custom_keys_and_signed_tt
    ):
        result = fixture_swsampler.calculate_attributes(
            span_name="foo",
            attributes=attributes_with_tracestate,
            decision=decision_continued,
            trace_state=tracestate_with_sw_and_others,
            parent_span_context=parent_span_context_valid_remote,
            xtraceoptions=mock_xtraceoptions_sw_keys_and_custom_keys_and_signed_tt,
        )
        expected = MappingProxyType({
            "foo": "bar",
            "baz": "qux",
            "SWKeys": "foo",
            "custom-foo": "awesome-bar",
            "BucketCapacity": "-1",
            "BucketRate": "-1",
            "SampleRate": -1,
            "SampleSource": -1,
            "TriggeredTrace": True,
            "sw.tracestate_parent_id": "1111222233334444",
            "sw.w3c.tracestate": "sw=1111222233334444-01,some=other",
        })
        for e_key, e_val in expected.items():
            assert result.get(e_key) == e_val

    def test_no_parent_update_attrs_no_tracestate(
        self,
        fixture_swsampler,
        attributes_no_tracestate,
        decision_record_and_sample_regular,
        mock_xtraceoptions_empty,
    ):
        """Represents manual SDK start_as_current_span with attributes at root"""
        assert fixture_swsampler.calculate_attributes(
            span_name="foo",
            attributes=attributes_no_tracestate,
            decision=decision_record_and_sample_regular,
            trace_state=None,
            parent_span_context=INVALID_SPAN_CONTEXT,
            xtraceoptions=mock_xtraceoptions_empty,
        ) == MappingProxyType({
            "BucketCapacity": "267.0",
            "BucketRate": "14.7",
            "SampleRate": 1000000,
            "SampleSource": 6,
            "foo": "bar",
            "baz": "qux",
        })
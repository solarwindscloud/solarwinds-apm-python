# © 2023 SolarWinds Worldwide, LLC. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at:http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

import re
import json

from opentelemetry import trace as trace_api
from unittest import mock

from .test_base_sw_headers_attrs import TestBaseSwHeadersAndAttributes


class TestScenario8(TestBaseSwHeadersAndAttributes):
    """
    Test class for continuing tracing decision OR trigger tracing with input headers
    for traceparent, tracestate, and trigger tracing.
    """

    def test_sampled_both_trace_context_and_xtraceoptions_valid(self):
        """
        1. Decision to sample is continued using valid extracted tracestate at service
           entry span (mocked). Unsigned trigger trace header is ignored. This is
           not the root span because it continues an existing OTel context.
        2. traceparent and tracestate headers in the request to the test app are
           injected into the outgoing request (done by OTel TraceContextTextMapPropagator).
        3. The valid x-trace-options is still handled and an x-trace-options-response
           header is injected into the response
        4. The injected traceparent's trace_id is the trace_id of all spans.
        5. Sampling-related attributes are set for the service entry span.
        6. custom-* and sw-keys from x-trace-options are set for service entry span.
        7. The span_id of the outgoing request span matches the span_id portion in the
           tracestate header.
        """
        trace_id = "11112222333344445555666677778888"
        span_id = "1000100010001000"
        trace_flags = "01"
        traceparent = "00-{}-{}-{}".format(trace_id, span_id, trace_flags)
        tracestate_span = "e000baa4e000baa4"
        tracestate = "sw={}-{}".format(tracestate_span, trace_flags)
        xtraceoptions = "trigger-trace;custom-from=lin;foo=bar;sw-keys=custom-sw-from:tammy,baz:qux;ts={}".format(1234567890)

        # Use in-process test app client and mock to propagate context
        # and create in-memory trace
        resp = None
        # liboboe mocked to guarantee return of "do_sample" (2nd arg),
        # plus status_msg (the "ignored" string)
        mock_decision = mock.Mock(
            return_value=(1, 1, 3, 4, 5.0, 6.0, 1, 0, "ignored", "ok", 0)
        )
        with mock.patch(
            target="solarwinds_apm.extension.oboe.Context.getDecisions",
            new=mock_decision,
        ):
            # Request to instrumented app with headers
            resp = self.client.get(
                "/test_trace/",
                headers={
                    "traceparent": traceparent,
                    "tracestate": tracestate,
                    "x-trace-options": xtraceoptions,
                    "some-header": "some-value"
                }
            )
        resp_json = json.loads(resp.data)

        # Verify some-header was not altered by instrumentation
        try:
            assert resp_json["incoming-headers"]["some-header"] == "some-value"
        except KeyError as e:
            self.fail("KeyError was raised at incoming-headers check: {}".format(e))

        # Verify trace context injected into test app's outgoing postman-echo call
        # (added to Flask app's response data) includes:
        #    - traceparent with a trace_id, trace_flags from original request
        #    - tracestate from original request
        assert "traceparent" in resp_json
        assert trace_id in resp_json["traceparent"]
        _TRACEPARENT_HEADER_FORMAT = (
            "^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$"
        )
        _TRACEPARENT_HEADER_FORMAT_RE = re.compile(_TRACEPARENT_HEADER_FORMAT)
        traceparent_re_result = re.search(
            _TRACEPARENT_HEADER_FORMAT_RE,
            resp_json["traceparent"],
        )
        new_trace_id = traceparent_re_result.group(2)
        assert new_trace_id is not None
        assert new_trace_id == trace_id
        new_span_id = traceparent_re_result.group(3)
        assert new_span_id is not None
        new_trace_flags = traceparent_re_result.group(4)
        assert new_trace_flags == trace_flags

        assert "tracestate" in resp_json
        # In this test we know tracestate will have `sw`
        # with new_span_id and new_trace_flags.
        # `xtrace_options_response` is not propagated.
        assert resp_json["tracestate"] == "sw={}-{}".format(
            new_span_id,
            new_trace_flags,
        )

        # Verify the OTel context extracted from the original request are continued by
        # the trace context injected into test app's outgoing postman-echo call
        try:
            assert resp_json["incoming-headers"]["traceparent"] == traceparent
            assert new_trace_id in resp_json["incoming-headers"]["traceparent"]
            assert new_span_id not in resp_json["incoming-headers"]["traceparent"]
            assert new_trace_flags in resp_json["incoming-headers"]["traceparent"]

            assert resp_json["incoming-headers"]["tracestate"] == tracestate
            assert "sw=" in resp_json["incoming-headers"]["tracestate"]
            assert new_span_id not in resp_json["incoming-headers"]["tracestate"]
            assert new_trace_flags in resp_json["incoming-headers"]["tracestate"]
        except KeyError as e:
            self.fail("KeyError was raised at continue trace check: {}".format(e))

        # Verify x-trace response header has same trace_id
        # though it will have different span ID because of Flask
        # app's outgoing request
        assert "x-trace" in resp.headers
        assert new_trace_id in resp.headers["x-trace"]

        # Verify x-trace-options-response response header present
        # with values calculated from decision and input validation
        assert "x-trace-options-response" in resp.headers
        assert "trigger-trace=ignored" in resp.headers["x-trace-options-response"]
        assert "ignored=foo" in resp.headers["x-trace-options-response"]

        # Verify spans exported: service entry + outgoing request (child with local parent)
        spans = self.memory_exporter.get_finished_spans()
        assert len(spans) == 2
        span_server = spans[1]
        span_client = spans[0]
        assert span_server.name == "/test_trace/"
        assert span_server.kind == trace_api.SpanKind.SERVER
        assert span_client.name == "GET"
        assert span_client.kind == trace_api.SpanKind.CLIENT

        # Check spans' trace_id, which should match traceparent of original request
        # Note: context.trace_id needs a 32-byte hex conversion first.
        assert "{:032x}".format(span_server.context.trace_id) == trace_id
        assert "{:032x}".format(span_client.context.trace_id) == trace_id

        # Check service entry span tracestate has `sw` and `xtrace_options_response` key.
        # In this test it should be span_id, traceflags from extracted traceparent.
        # SWO APM uses TraceState to stash the trigger trace response so it's available 
        # at the time of custom injecting the x-trace-options-response header.
        expected_trace_state = trace_api.TraceState([
            ("sw", "{}-{}".format(tracestate_span, trace_flags)),
            ("xtrace_options_response", "trigger-trace####ignored;ignored####foo"),
        ])
        actual_trace_state = span_server.context.trace_state
        assert actual_trace_state.get("xtrace_options_response") == expected_trace_state.get("xtrace_options_response")
        assert actual_trace_state.get("sw") == expected_trace_state.get("sw")

        # Check service entry span attributes
        #   :present:
        #     service entry internal KVs, which are on all entry spans
        #     sw.tracestate_parent_id, because only set if not root and no attributes
        #     custom-*, because included in xtraceoptions in otel context
        #     SWKeys, because included in xtraceoptions in otel context
        assert all(attr_key in span_server.attributes for attr_key in self.SW_SETTINGS_KEYS)
        assert span_server.attributes["BucketCapacity"] == "6.0"
        assert span_server.attributes["BucketRate"] == "5.0"
        assert span_server.attributes["SampleRate"] == 3
        assert span_server.attributes["SampleSource"] == 4
        assert "sw.tracestate_parent_id" in span_server.attributes
        assert span_server.attributes["sw.tracestate_parent_id"] == tracestate_span
        assert "custom-from" in span_server.attributes
        assert span_server.attributes["custom-from"] == "lin"
        assert "SWKeys" in span_server.attributes
        assert span_server.attributes["SWKeys"] == "custom-sw-from:tammy,baz:qux"

        # Check service entry span tracestate has `sw` and `xtrace_options_response` key.
        # In this test it should also be span_id, traceflags from extracted traceparent
        # SWO APM uses TraceState to stash the trigger trace response so it's available 
        # at the time of custom injecting the x-trace-options-response header.
        expected_trace_state = trace_api.TraceState([
            ("sw", "{}-{}".format(tracestate_span, trace_flags)),
            ("xtrace_options_response", "trigger-trace####ignored;ignored####foo"),
        ])
        actual_trace_state = span_client.context.trace_state
        assert actual_trace_state.get("xtrace_options_response") == expected_trace_state.get("xtrace_options_response")
        assert actual_trace_state.get("sw") == expected_trace_state.get("sw")

        # Check outgoing request span attributes
        #   :absent:
        #     service entry internal KVs, which are only on entry spans
        #     sw.tracestate_parent_id, because cannot be set without attributes at decision
        #     custom-*, because only on entry spans
        #     SWKeys, because only on entry spans
        assert not any(attr_key in span_client.attributes for attr_key in self.SW_SETTINGS_KEYS)
        assert not "sw.tracestate_parent_id" in span_client.attributes
        assert not "custom-from" in span_client.attributes
        assert not "SWKeys" in span_client.attributes

        # Check span_id of the outgoing request span (client span) matches
        # the span_id portion in the outgoing tracestate header, which
        # is stored in the test app's response body (new_span_id).
        # Note: context.span_id needs a 16-byte hex conversion first.
        assert "{:016x}".format(span_client.context.span_id) == new_span_id

    # def test_not_sampled_both_trace_context_and_xtraceoptions_valid(self):
    #     """
    #     1. Decision to NOT sample is continued using valid extracted
    #        tracestate at service entry span (mocked). Unsigned trigger trace
    #        header is ignored. This is not the root span because it continues
    #        an existing OTel context.
    #     2. traceparent and tracestate headers in the request to the test app are
    #        injected into the outgoing request (done by OTel TraceContextTextMapPropagator).
    #     3. The valid x-trace-options is still handled and an x-trace-options-response
    #        header is injected into the response.
    #     4. No spans are exported.
    #     """
    #     trace_id = "11112222333344445555666677778888"
    #     span_id = "1000100010001000"
    #     trace_flags = "00"
    #     traceparent = "00-{}-{}-01".format(trace_id, span_id)
    #     tracestate_span = "e000baa4e000baa4"
    #     tracestate = "sw={}-{}".format(tracestate_span, trace_flags)
    #     xtraceoptions = "trigger-trace;custom-from=lin;foo=bar;sw-keys=custom-sw-from:tammy,baz:qux;ts={}".format(1234567890)

    #     # Use in-process test app client and mock to propagate context
    #     # and create in-memory trace
    #     resp = None
    #     # liboboe mocked to guarantee return of "do_sample" (2nd arg),
    #     # plus status_msg (the "ignored" string)
    #     mock_decision = mock.Mock(
    #         return_value=(1, 0, 3, 4, 5.0, 6.0, 1, 0, "ignored", "ok", 0)
    #     )
    #     with mock.patch(
    #         target="solarwinds_apm.extension.oboe.Context.getDecisions",
    #         new=mock_decision,
    #     ):
    #         # Request to instrumented app with headers
    #         resp = self.client.get(
    #             "/test_trace/",
    #             headers={
    #                 "traceparent": traceparent,
    #                 "tracestate": tracestate,
    #                 "x-trace-options": xtraceoptions,
    #                 "some-header": "some-value"
    #             }
    #         )
    #     resp_json = json.loads(resp.data)

    #     # Verify some-header was not altered by instrumentation
    #     try:
    #         assert resp_json["incoming-headers"]["some-header"] == "some-value"
    #     except KeyError as e:
    #         self.fail("KeyError was raised at incoming-headers check: {}".format(e))

    #     # Verify trace context injected into test app's outgoing postman-echo call
    #     # (added to Flask app's response data) includes:
    #     #    - traceparent with a trace_id, trace_flags from original request
    #     #    - tracestate from original request
    #     assert "traceparent" in resp_json
    #     assert trace_id in resp_json["traceparent"]
    #     _TRACEPARENT_HEADER_FORMAT = (
    #         "^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$"
    #     )
    #     _TRACEPARENT_HEADER_FORMAT_RE = re.compile(_TRACEPARENT_HEADER_FORMAT)
    #     traceparent_re_result = re.search(
    #         _TRACEPARENT_HEADER_FORMAT_RE,
    #         resp_json["traceparent"],
    #     )
    #     new_trace_id = traceparent_re_result.group(2)
    #     assert new_trace_id is not None
    #     assert new_trace_id == trace_id
    #     new_span_id = traceparent_re_result.group(3)
    #     assert new_span_id is not None
    #     new_trace_flags = traceparent_re_result.group(4)
    #     assert new_trace_flags == trace_flags

    #     assert "tracestate" in resp_json
    #     # In this test we know tracestate will have `sw`
    #     # with new_span_id and new_trace_flags.
    #     # `xtrace_options_response` is not propagated.
    #     assert resp_json["tracestate"] == "sw={}-{}".format(
    #         new_span_id,
    #         new_trace_flags,
    #     )

    #     # Verify the OTel context extracted from the original request are continued by
    #     # the trace context injected into test app's outgoing postman-echo call
    #     try:
    #         assert resp_json["incoming-headers"]["traceparent"] == traceparent
    #         assert new_trace_id in resp_json["incoming-headers"]["traceparent"]
    #         assert new_span_id not in resp_json["incoming-headers"]["traceparent"]
    #         assert new_trace_flags in resp_json["incoming-headers"]["traceparent"]

    #         assert resp_json["incoming-headers"]["tracestate"] == tracestate
    #         assert "sw=" in resp_json["incoming-headers"]["tracestate"]
    #         assert new_span_id not in resp_json["incoming-headers"]["tracestate"]
    #         assert new_trace_flags in resp_json["incoming-headers"]["tracestate"]
    #     except KeyError as e:
    #         self.fail("KeyError was raised at continue trace check: {}".format(e))

    #     # Verify x-trace response header has same trace_id
    #     # though it will have different span ID because of Flask
    #     # app's outgoing request
    #     assert "x-trace" in resp.headers
    #     assert new_trace_id in resp.headers["x-trace"]

    #     # Verify x-trace-options-response response header present
    #     # with values calculated from decision and input validation
    #     assert "x-trace-options-response" in resp.headers
    #     assert "trigger-trace=ignored" in resp.headers["x-trace-options-response"]
    #     assert "ignored=foo" in resp.headers["x-trace-options-response"]

    #     # Verify no spans exported
    #     spans = self.memory_exporter.get_finished_spans()
    #     assert len(spans) == 0

    def test_sampled_both_trace_context_and_xtraceoptions_valid_without_tt(self):
        """
        1. Decision to sample is continued using valid extracted tracestate at service
           entry span (mocked). Unsigned trigger trace header is ignored. This is
           not the root span because it continues an existing OTel context.
        2. traceparent and tracestate headers in the request to the test app are
           injected into the outgoing request (done by OTel TraceContextTextMapPropagator).
        3. The valid x-trace-options is still handled and an x-trace-options-response
           header is injected into the response
        4. The injected traceparent's trace_id is the trace_id of all spans.
        5. Sampling-related attributes are set for the service entry span.
        6. custom-* and sw-keys from x-trace-options are still set for service entry span.
        7. The span_id of the outgoing request span matches the span_id portion in the
           tracestate header.
        """
        trace_id = "11112222333344445555666677778888"
        span_id = "1000100010001000"
        trace_flags = "01"
        traceparent = "00-{}-{}-{}".format(trace_id, span_id, trace_flags)
        tracestate_span = "e000baa4e000baa4"
        tracestate = "sw={}-{}".format(tracestate_span, trace_flags)
        xtraceoptions = "custom-from=lin;foo=bar;sw-keys=custom-sw-from:tammy,baz:qux;ts={}".format(1234567890)

        # Use in-process test app client and mock to propagate context
        # and create in-memory trace
        resp = None
        # liboboe mocked to guarantee return of "do_sample" (2nd arg),
        # plus status_msg (the "ignored" string)
        mock_decision = mock.Mock(
            return_value=(1, 1, 3, 4, 5.0, 6.0, 1, 0, "ignored", "ok", 0)
        )
        with mock.patch(
            target="solarwinds_apm.extension.oboe.Context.getDecisions",
            new=mock_decision,
        ):
            # Request to instrumented app with headers
            resp = self.client.get(
                "/test_trace/",
                headers={
                    "traceparent": traceparent,
                    "tracestate": tracestate,
                    "x-trace-options": xtraceoptions,
                    "some-header": "some-value"
                }
            )
        resp_json = json.loads(resp.data)

        # Verify some-header was not altered by instrumentation
        try:
            assert resp_json["incoming-headers"]["some-header"] == "some-value"
        except KeyError as e:
            self.fail("KeyError was raised at incoming-headers check: {}".format(e))

        # Verify trace context injected into test app's outgoing postman-echo call
        # (added to Flask app's response data) includes:
        #    - traceparent with a trace_id, trace_flags from original request
        #    - tracestate from original request
        assert "traceparent" in resp_json
        assert trace_id in resp_json["traceparent"]
        _TRACEPARENT_HEADER_FORMAT = (
            "^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$"
        )
        _TRACEPARENT_HEADER_FORMAT_RE = re.compile(_TRACEPARENT_HEADER_FORMAT)
        traceparent_re_result = re.search(
            _TRACEPARENT_HEADER_FORMAT_RE,
            resp_json["traceparent"],
        )
        new_trace_id = traceparent_re_result.group(2)
        assert new_trace_id is not None
        assert new_trace_id == trace_id
        new_span_id = traceparent_re_result.group(3)
        assert new_span_id is not None
        new_trace_flags = traceparent_re_result.group(4)
        assert new_trace_flags == trace_flags

        assert "tracestate" in resp_json
        # In this test we know there is `sw` in tracestate
        # where value will be new_span_id and new_trace_flags.
        # There should be no `xtrace_options_response` key because there is
        # no trigger-trace in the extracted x-trace-options header.
        assert resp_json["tracestate"] == "sw={}-{}".format(
            new_span_id,
            new_trace_flags,
        )

        # Verify the OTel context extracted from the original request are continued by
        # the trace context injected into test app's outgoing postman-echo call
        try:
            assert resp_json["incoming-headers"]["traceparent"] == traceparent
            assert new_trace_id in resp_json["incoming-headers"]["traceparent"]
            assert new_span_id not in resp_json["incoming-headers"]["traceparent"]
            assert new_trace_flags in resp_json["incoming-headers"]["traceparent"]

            assert resp_json["incoming-headers"]["tracestate"] == tracestate
            assert "sw=" in resp_json["incoming-headers"]["tracestate"]
            assert new_span_id not in resp_json["incoming-headers"]["tracestate"]
            assert new_trace_flags in resp_json["incoming-headers"]["tracestate"]
        except KeyError as e:
            self.fail("KeyError was raised at continue trace check: {}".format(e))

        # Verify x-trace response header has same trace_id
        # though it will have different span ID because of Flask
        # app's outgoing request
        assert "x-trace" in resp.headers
        assert new_trace_id in resp.headers["x-trace"]

        # Verify x-trace-options-response response header present
        # with values calculated from decision and input validation
        assert "x-trace-options-response" in resp.headers
        assert "trigger-trace=not-requested" in resp.headers["x-trace-options-response"]
        assert "ignored=foo" in resp.headers["x-trace-options-response"]

        # Verify spans exported: service entry + outgoing request (child with local parent)
        spans = self.memory_exporter.get_finished_spans()
        assert len(spans) == 2
        span_server = spans[1]
        span_client = spans[0]
        assert span_server.name == "/test_trace/"
        assert span_server.kind == trace_api.SpanKind.SERVER
        assert span_client.name == "GET"
        assert span_client.kind == trace_api.SpanKind.CLIENT

        # Check spans' trace_id, which should match traceparent of original request
        # Note: context.trace_id needs a 32-byte hex conversion first.
        assert "{:032x}".format(span_server.context.trace_id) == trace_id
        assert "{:032x}".format(span_client.context.trace_id) == trace_id

        # Check service entry span tracestate has `sw` and `xtrace_options_response` keys
        # In this test it should be span_id, traceflags from extracted traceparent.
        # SWO APM uses TraceState to stash the trigger trace response so it's available 
        # at the time of custom injecting the x-trace-options-response header.
        expected_trace_state = trace_api.TraceState([
            ("sw", "{}-{}".format(tracestate_span, trace_flags)),
            ("xtrace_options_response", "trigger-trace####not-requested;ignored####foo"),
        ])
        actual_trace_state = span_server.context.trace_state
        assert actual_trace_state.get("sw") == expected_trace_state.get("sw")
        assert actual_trace_state.get("xtrace_options_response") == expected_trace_state.get("xtrace_options_response")

        # Check service entry span attributes
        #   :present:
        #     service entry internal KVs, which are on all entry spans
        #     sw.tracestate_parent_id, because only set if not root and no attributes
        #     custom-*, because included in xtraceoptions in otel context
        #     SWKeys, because included in xtraceoptions in otel context
        assert all(attr_key in span_server.attributes for attr_key in self.SW_SETTINGS_KEYS)
        assert span_server.attributes["BucketCapacity"] == "6.0"
        assert span_server.attributes["BucketRate"] == "5.0"
        assert span_server.attributes["SampleRate"] == 3
        assert span_server.attributes["SampleSource"] == 4
        assert "sw.tracestate_parent_id" in span_server.attributes
        assert span_server.attributes["sw.tracestate_parent_id"] == tracestate_span
        assert "custom-from" in span_server.attributes
        assert span_server.attributes["custom-from"] == "lin"
        assert "SWKeys" in span_server.attributes
        assert span_server.attributes["SWKeys"] == "custom-sw-from:tammy,baz:qux"

        # Check outgoing request tracestate has `sw` and `xtrace_options_response` keys
        # In this test it should also be span_id, traceflags from extracted traceparent
        # SWO APM uses TraceState to stash the trigger trace response so it's available 
        # at the time of custom injecting the x-trace-options-response header.
        expected_trace_state = trace_api.TraceState([
            ("sw", "{}-{}".format(tracestate_span, trace_flags)),
            ("xtrace_options_response", "trigger-trace####not-requested;ignored####foo"),
        ])
        actual_trace_state = span_client.context.trace_state
        assert actual_trace_state.get("sw") == expected_trace_state.get("sw")
        assert actual_trace_state.get("xtrace_options_response") == expected_trace_state.get("xtrace_options_response")

        # Check outgoing request span attributes
        #   :absent:
        #     service entry internal KVs, which are only on entry spans
        #     sw.tracestate_parent_id, because cannot be set without attributes at decision
        #     custom-*, because only on entry spans
        #     SWKeys, because only on entry spans
        assert not any(attr_key in span_client.attributes for attr_key in self.SW_SETTINGS_KEYS)
        assert not "sw.tracestate_parent_id" in span_client.attributes
        assert not "custom-from" in span_client.attributes
        assert not "SWKeys" in span_client.attributes

        # Check span_id of the outgoing request span (client span) matches
        # the span_id portion in the outgoing tracestate header, which
        # is stored in the test app's response body (new_span_id).
        # Note: context.span_id needs a 16-byte hex conversion first.
        assert "{:016x}".format(span_client.context.span_id) == new_span_id

    # def test_not_sampled_both_trace_context_and_xtraceoptions_valid_without_tt(self):
    #     """
    #     1. Decision to NOT sample is continued using valid extracted tracestate at service
    #        entry span (mocked). Unsigned trigger trace header is ignored. This is
    #        not the root span because it continues an existing OTel context
    #     2. traceparent and tracestate headers in the request to the test app are
    #     injected into the outgoing request (done by OTel TraceContextTextMapPropagator).
    #     3. The valid x-trace-options is still handled and an x-trace-options-response
    #        header is injected into the response
    #     4. No spans are exported.
    #     """
    #     trace_id = "11112222333344445555666677778888"
    #     span_id = "1000100010001000"
    #     trace_flags = "00"
    #     traceparent = "00-{}-{}-01".format(trace_id, span_id)
    #     tracestate_span = "e000baa4e000baa4"
    #     tracestate = "sw={}-{}".format(tracestate_span, trace_flags)
    #     xtraceoptions = "custom-from=lin;foo=bar;sw-keys=custom-sw-from:tammy,baz:qux;ts={}".format(1234567890)

    #     # Use in-process test app client and mock to propagate context
    #     # and create in-memory trace
    #     resp = None
    #     # liboboe mocked to guarantee return of "do_sample" (2nd arg),
    #     # plus status_msg (the "ignored" string)
    #     mock_decision = mock.Mock(
    #         return_value=(1, 0, 3, 4, 5.0, 6.0, 1, 0, "ignored", "ok", 0)
    #     )
    #     with mock.patch(
    #         target="solarwinds_apm.extension.oboe.Context.getDecisions",
    #         new=mock_decision,
    #     ):
    #         # Request to instrumented app with headers
    #         resp = self.client.get(
    #             "/test_trace/",
    #             headers={
    #                 "traceparent": traceparent,
    #                 "tracestate": tracestate,
    #                 "x-trace-options": xtraceoptions,
    #                 "some-header": "some-value"
    #             }
    #         )
    #     resp_json = json.loads(resp.data)

    #     # Verify some-header was not altered by instrumentation
    #     try:
    #         assert resp_json["incoming-headers"]["some-header"] == "some-value"
    #     except KeyError as e:
    #         self.fail("KeyError was raised at incoming-headers check: {}".format(e))

    #     # Verify trace context injected into test app's outgoing postman-echo call
    #     # (added to Flask app's response data) includes:
    #     #    - traceparent with a trace_id, trace_flags from original request
    #     #    - tracestate from original request
    #     assert "traceparent" in resp_json
    #     assert trace_id in resp_json["traceparent"]
    #     _TRACEPARENT_HEADER_FORMAT = (
    #         "^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$"
    #     )
    #     _TRACEPARENT_HEADER_FORMAT_RE = re.compile(_TRACEPARENT_HEADER_FORMAT)
    #     traceparent_re_result = re.search(
    #         _TRACEPARENT_HEADER_FORMAT_RE,
    #         resp_json["traceparent"],
    #     )
    #     new_trace_id = traceparent_re_result.group(2)
    #     assert new_trace_id is not None
    #     assert new_trace_id == trace_id
    #     new_span_id = traceparent_re_result.group(3)
    #     assert new_span_id is not None
    #     new_trace_flags = traceparent_re_result.group(4)
    #     assert new_trace_flags == trace_flags

    #     assert "tracestate" in resp_json
    #     # In this test we know there is `sw` in tracestate
    #     # where value will be new_span_id and new_trace_flags.
    #     # There should be no `xtrace_options_response` key because there is
    #     # no trigger-trace in the extracted x-trace-options header.
    #     assert resp_json["tracestate"] == "sw={}-{}".format(
    #         new_span_id,
    #         new_trace_flags,
    #     )

    #     # Verify the OTel context extracted from the original request are continued by
    #     # the trace context injected into test app's outgoing postman-echo call
    #     try:
    #         assert resp_json["incoming-headers"]["traceparent"] == traceparent
    #         assert new_trace_id in resp_json["incoming-headers"]["traceparent"]
    #         assert new_span_id not in resp_json["incoming-headers"]["traceparent"]
    #         assert new_trace_flags in resp_json["incoming-headers"]["traceparent"]

    #         assert resp_json["incoming-headers"]["tracestate"] == tracestate
    #         assert "sw=" in resp_json["incoming-headers"]["tracestate"]
    #         assert new_span_id not in resp_json["incoming-headers"]["tracestate"]
    #         assert new_trace_flags in resp_json["incoming-headers"]["tracestate"]
    #     except KeyError as e:
    #         self.fail("KeyError was raised at continue trace check: {}".format(e))

    #     # Verify x-trace response header has same trace_id
    #     # though it will have different span ID because of Flask
    #     # app's outgoing request
    #     assert "x-trace" in resp.headers
    #     assert new_trace_id in resp.headers["x-trace"]

    #     # Verify x-trace-options-response response header present
    #     # with values calculated from decision and input validation
    #     assert "x-trace-options-response" in resp.headers
    #     assert "trigger-trace=not-requested" in resp.headers["x-trace-options-response"]
    #     assert "ignored=foo" in resp.headers["x-trace-options-response"]

    #     # Verify no spans exported
    #     spans = self.memory_exporter.get_finished_spans()
    #     assert len(spans) == 0

    def test_sampled_invalid_trace_context_and_valid_unsigned_with_tt(self):
        """
        1. Decision to sample with unsigned trigger trace flag is made at root/service
           entry span (mocked). There IS an OTel context extracted from request headers,
           but it is not valid. So this is the root and start of the trace.
        2. Some new, valid traceparent and tracestate are injected into service's outgoing request
           (done by OTel TraceContextTextMapPropagator).
        3. The valid x-trace-options is still handled and an x-trace-options-response
           header is injected into the response.
        4. Sampling-related, SWKeys, custom-*, and TriggeredTrace attributes are set
           for the root/service entry span, but not what's ignored.
        5. The span_id of the outgoing request span matches the span_id portion in the
           tracestate header.
        """
        # Use in-process test app client and mock to propagate context
        # and create in-memory trace
        resp = None
        # liboboe mocked to guarantee return of "do_sample" (2nd arg),
        # plus status_msg (the first "ok" string)
        mock_decision = mock.Mock(
            return_value=(1, 1, -1, -1, 5.0, 6.0, 1, -1, "ok", "ok", 0)
        )
        with mock.patch(
            target="solarwinds_apm.extension.oboe.Context.getDecisions",
            new=mock_decision,
        ):
            # Request to instrumented app with headers
            resp = self.client.get(
                "/test_trace/",
                headers={
                    "traceparent": "not-a-valid-traceparent",
                    "tracestate": "also-not-a-valid-tracestate",
                    "x-trace-options": "trigger-trace;sw-keys=check-id:check-1013,website-id:booking-demo;this-will-be-ignored;custom-awesome-key=foo",
                    "some-header": "some-value"
                }
            )
        resp_json = json.loads(resp.data)

        # Verify some-header was not altered by instrumentation
        try:
            assert resp_json["incoming-headers"]["some-header"] == "some-value"
        except KeyError as e:
            self.fail("KeyError was raised at incoming-headers check: {}".format(e))

        # Verify trace context injected into test app's outgoing postman-echo call
        # (added to Flask app's response data) includes:
        #    - traceparent with a trace_id, span_id, and trace_flags for do_sample
        #    - tracestate with same span_id and trace_flags for do_sample
        assert "traceparent" in resp_json
        _TRACEPARENT_HEADER_FORMAT = (
            "^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$"
        )
        _TRACEPARENT_HEADER_FORMAT_RE = re.compile(_TRACEPARENT_HEADER_FORMAT)
        traceparent_re_result = re.search(
            _TRACEPARENT_HEADER_FORMAT_RE,
            resp_json["traceparent"],
        )
        new_trace_id = traceparent_re_result.group(2)
        assert new_trace_id is not None
        new_span_id = traceparent_re_result.group(3)
        assert new_span_id is not None
        new_trace_flags = traceparent_re_result.group(4)
        assert new_trace_flags == "01"

        assert "tracestate" in resp_json
        # In this test we know tracestate will have `sw`
        # with new_span_id and new_trace_flags.
        # `xtrace_options_response` is not propagated.
        assert resp_json["tracestate"] == "sw={}-{}".format(
            new_span_id,
            new_trace_flags,
        )

        # Verify x-trace response header has same trace_id
        # though it will have different span ID because of Flask
        # app's outgoing request
        assert "x-trace" in resp.headers
        assert new_trace_id in resp.headers["x-trace"]

        # Verify x-trace-options-response response header present
        # with values calculated from decision and input validation
        assert "x-trace-options-response" in resp.headers
        assert "trigger-trace=ok" in resp.headers["x-trace-options-response"]
        assert "ignored=this-will-be-ignored" in resp.headers["x-trace-options-response"]

        # Verify spans exported: service entry (root) + outgoing request (child with local parent)
        spans = self.memory_exporter.get_finished_spans()
        assert len(spans) == 2
        span_server = spans[1]
        span_client = spans[0]
        assert span_server.name == "/test_trace/"
        assert span_server.kind == trace_api.SpanKind.SERVER
        assert span_client.name == "GET"
        assert span_client.kind == trace_api.SpanKind.CLIENT

        # Check root span tracestate has `xtrace_options_response` key but no `sw` key
        # because no valid parent context.
        # SWO APM uses TraceState to stash the trigger trace response so it's available 
        # at the time of custom injecting the x-trace-options-response header.
        expected_trace_state = trace_api.TraceState([
            ("xtrace_options_response", "trigger-trace####ok;ignored####this-will-be-ignored"),
        ])
        actual_trace_state = span_server.context.trace_state
        assert actual_trace_state.get("sw") == expected_trace_state.get("sw")  # None
        assert actual_trace_state.get("xtrace_options_response") == expected_trace_state.get("xtrace_options_response")

        # Check root span attributes
        #   :present:
        #     service entry internal KVs, which are on all entry spans
        #     SWKeys, because included in xtraceoptions in otel context
        #     custom-*, because included in xtraceoptions in otel context
        #     TriggeredTrace, because trigger-trace in otel context
        #   :absent:
        #     sw.tracestate_parent_id, because cannot be set at root nor without attributes at decision
        #     the ignored value in the x-trace-options-header
        assert all(attr_key in span_server.attributes for attr_key in self.SW_SETTINGS_KEYS)
        assert span_server.attributes["BucketCapacity"] == "6.0"
        assert span_server.attributes["BucketRate"] == "5.0"
        assert span_server.attributes["SampleRate"] == -1
        assert span_server.attributes["SampleSource"] == -1
        assert not "sw.tracestate_parent_id" in span_server.attributes
        assert "SWKeys" in span_server.attributes
        assert span_server.attributes["SWKeys"] == "check-id:check-1013,website-id:booking-demo"
        assert "custom-awesome-key" in span_server.attributes
        assert span_server.attributes["custom-awesome-key"] == "foo"
        assert "TriggeredTrace" in span_server.attributes
        assert span_server.attributes["TriggeredTrace"] == True
        assert "this-will-be-ignored" not in span_server.attributes

        # Check root span tracestate has `xtrace_options_response` key but no `sw` key
        # because no valid parent context.
        # SWO APM uses TraceState to stash the trigger trace response so it's available 
        # at the time of custom injecting the x-trace-options-response header.
        expected_trace_state = trace_api.TraceState([
            ("xtrace_options_response", "trigger-trace####ok;ignored####this-will-be-ignored"),
        ])
        actual_trace_state = span_client.context.trace_state
        assert actual_trace_state.get("sw") == expected_trace_state.get("sw")  # None
        assert actual_trace_state.get("xtrace_options_response") == expected_trace_state.get("xtrace_options_response")

        # Check outgoing request span attributes
        #   :absent:
        #     service entry internal KVs, which are only on entry spans
        #     sw.tracestate_parent_id, because cannot be set without attributes at decision
        #     SWKeys, because only written for service entry spans
        #     custom-*, because only written for service entry spans
        #     TriggeredTrace, because only written for service entry spans
        #     the ignored value in the x-trace-options-header
        assert not any(attr_key in span_client.attributes for attr_key in self.SW_SETTINGS_KEYS)
        assert not "sw.tracestate_parent_id" in span_client.attributes
        assert not "SWKeys" in span_client.attributes
        assert not "custom-awesome-key" in span_client.attributes
        assert not "TriggeredTrace" in span_client.attributes
        assert "this-will-be-ignored" not in span_client.attributes

        # Check span_id of the outgoing request span (client span) matches
        # the span_id portion in the outgoing tracestate header, which
        # is stored in the test app's response body (new_span_id).
        # Note: context.span_id needs a 16-byte hex conversion first.
        assert "{:016x}".format(span_client.context.span_id) == new_span_id

    # def test_not_sampled_invalid_trace_context_and_valid_unsigned_with_tt(self):
    #     """
    #     Scenario #6, not sampled with unsigned tt:
    #     1. Decision to NOT sample with unsigned trigger trace flag is made at root/service
    #        entry span (mocked). There IS an OTel context extracted from request headers,
    #        but it is not valid. So this is the root and start of the trace.
    #     2. Some new, valid traceparent and tracestate are injected into service's outgoing request (done by OTel TraceContextTextMapPropagator).
    #     3. The valid x-trace-options is still handled and an x-trace-options-response
    #        header is injected into the response.
    #     4. No spans are exported.
    #     """
    #     # Use in-process test app client and mock to propagate context
    #     # and create in-memory trace
    #     resp = None
    #     # liboboe mocked to guarantee return of "do_sample" (2nd arg),
    #     # plus status_msg (the "rate-exceeded" string)
    #     mock_decision = mock.Mock(
    #         return_value=(1, 0, -1, -1, 5.0, 6.0, 1, -1, "rate-exceeded", "ok", -4)
    #     )
    #     with mock.patch(
    #         target="solarwinds_apm.extension.oboe.Context.getDecisions",
    #         new=mock_decision,
    #     ):
    #         # Request to instrumented app with headers
    #         resp = self.client.get(
    #             "/test_trace/",
    #             headers={
    #                 "traceparent": "not-a-valid-traceparent",
    #                 "tracestate": "also-not-a-valid-tracestate",
    #                 "x-trace-options": "trigger-trace;sw-keys=check-id:check-1013,website-id:booking-demo;this-will-be-ignored;custom-awesome-key=foo",
    #                 "some-header": "some-value"
    #             }
    #         )
    #     resp_json = json.loads(resp.data)

    #     # Verify some-header was not altered by instrumentation
    #     try:
    #         assert resp_json["incoming-headers"]["some-header"] == "some-value"
    #     except KeyError as e:
    #         self.fail("KeyError was raised at incoming-headers check: {}".format(e))

    #     # Verify trace context injected into test app's outgoing postman-echo call
    #     # (added to Flask app's response data) includes:
    #     #    - traceparent with a trace_id, span_id, and trace_flags for do_sample
    #     #    - tracestate with same span_id and trace_flags for do_sample
    #     assert "traceparent" in resp_json
    #     _TRACEPARENT_HEADER_FORMAT = (
    #         "^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$"
    #     )
    #     _TRACEPARENT_HEADER_FORMAT_RE = re.compile(_TRACEPARENT_HEADER_FORMAT)
    #     traceparent_re_result = re.search(
    #         _TRACEPARENT_HEADER_FORMAT_RE,
    #         resp_json["traceparent"],
    #     )
    #     new_trace_id = traceparent_re_result.group(2)
    #     assert new_trace_id is not None
    #     new_span_id = traceparent_re_result.group(3)
    #     assert new_span_id is not None
    #     new_trace_flags = traceparent_re_result.group(4)
    #     assert new_trace_flags == "00"

    #     assert "tracestate" in resp_json
    #     # In this test we know tracestate will have `sw`
    #     # with new_span_id and new_trace_flags.
    #     # `xtrace_options_response` is not propagated.
    #     assert resp_json["tracestate"] == "sw={}-{}".format(new_span_id, new_trace_flags)

    #     # Verify x-trace response header has same trace_id
    #     # though it will have different span ID because of Flask
    #     # app's outgoing request
    #     assert "x-trace" in resp.headers
    #     assert new_trace_id in resp.headers["x-trace"]

    #     # Verify x-trace-options-response response header present
    #     # with values calculated from decision and input validation
    #     assert "x-trace-options-response" in resp.headers
    #     assert "trigger-trace=rate-exceeded" in resp.headers["x-trace-options-response"]
    #     assert "ignored=this-will-be-ignored" in resp.headers["x-trace-options-response"]

    #     # Verify no spans exported
    #     spans = self.memory_exporter.get_finished_spans()
    #     assert len(spans) == 0

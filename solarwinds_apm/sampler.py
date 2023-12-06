# © 2023 SolarWinds Worldwide, LLC. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at:http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

"""This module provides a SolarWinds-specific sampler.

The custom sampler will fetch sampling configurations for the SolarWinds backend.
"""

import enum
import logging
from types import MappingProxyType
from typing import TYPE_CHECKING, Optional, Sequence

from opentelemetry.context.context import Context as OtelContext
from opentelemetry.sdk.trace.sampling import (
    Decision,
    ParentBased,
    Sampler,
    SamplingResult,
)
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import Link, SpanKind, get_current_span
from opentelemetry.trace.span import SpanContext, TraceState
from opentelemetry.util.types import Attributes

from solarwinds_apm.apm_config import OboeTracingMode
from solarwinds_apm.apm_constants import (
    INTL_SWO_COMMA_W3C_SANITIZED,
    INTL_SWO_EQUALS_W3C_SANITIZED,
    INTL_SWO_TRACESTATE_KEY,
    INTL_SWO_X_OPTIONS_KEY,
    INTL_SWO_X_OPTIONS_RESPONSE_KEY,
)
from solarwinds_apm.traceoptions import XTraceOptions
from solarwinds_apm.w3c_transformer import W3CTransformer

if TYPE_CHECKING:
    from solarwinds_apm.apm_config import SolarWindsApmConfig

logger = logging.getLogger(__name__)


class _SwSampler(Sampler):
    """SolarWinds custom opentelemetry sampler which obeys configuration options provided by the NH/AO Backend."""

    _INTERNAL_BUCKET_CAPACITY = "BucketCapacity"
    _INTERNAL_BUCKET_RATE = "BucketRate"
    _INTERNAL_SAMPLE_RATE = "SampleRate"
    _INTERNAL_SAMPLE_SOURCE = "SampleSource"
    _INTERNAL_SW_KEYS = "SWKeys"
    _INTERNAL_TRIGGERED_TRACE = "TriggeredTrace"
    _LIBOBOE_CONTINUED = -1
    _SW_TRACESTATE_CAPTURE_KEY = "sw.w3c.tracestate"
    _SW_TRACESTATE_ROOT_KEY = "sw.tracestate_parent_id"
    _UNSET = -1
    _XTRACEOPTIONS_RESP_AUTH = "auth"
    _XTRACEOPTIONS_RESP_IGNORED = "ignored"
    _XTRACEOPTIONS_RESP_TRIGGER_IGNORED = "ignored"
    _XTRACEOPTIONS_RESP_TRIGGER_NOT_REQUESTED = "not-requested"
    _XTRACEOPTIONS_RESP_TRIGGER_TRACE = "trigger-trace"

    def __init__(self, apm_config: "SolarWindsApmConfig"):
        self.apm_config = apm_config
        self.context = apm_config.extension.Context

        if self.apm_config.get("tracing_mode") is not None:
            self.tracing_mode = self.apm_config.get("tracing_mode")
        else:
            self.tracing_mode = self._UNSET

        self.oboe_settings_api = apm_config.oboe_api()

    def get_description(self) -> str:
        return "SolarWinds custom opentelemetry sampler"

    def construct_url(
        self,
        attributes: Attributes = None,
    ) -> str:
        """Construct url"""
        # TODO (NH-34752) Check http scheme, http target, net host name `attributes`
        #   availability after OTel instrumentation library updates released
        #   https://github.com/open-telemetry/opentelemetry-python-contrib/issues/936
        if not attributes:
            return ""

        url = ""
        scheme = attributes.get(SpanAttributes.HTTP_SCHEME)
        host = attributes.get(SpanAttributes.NET_HOST_NAME)
        port = attributes.get(SpanAttributes.NET_HOST_PORT)
        target = attributes.get(SpanAttributes.HTTP_TARGET)
        if scheme and host and target and port:
            url = f"{scheme}://{host}:{port}{target}"
            logger.debug("Constructed url for filtering: %s", url)
        elif scheme and host and target:
            url = f"{scheme}://{host}{target}"
            logger.debug("Constructed url for filtering: %s", url)
        return url

    def calculate_tracing_mode(
        self,
        name: str,
        kind: SpanKind = None,
        attributes: Attributes = None,
    ) -> int:
        """Calculates tracing mode per-request or global tracing mode, if set.
        Can still be overridden by remote settings."""
        # If future span matches txn filter, use filter's tracing mode
        if self.apm_config.get("transaction_filters"):
            # If span for http request, there should be a url
            url = self.construct_url(attributes)
            if url:
                identifier = url
            else:
                identifier = f"{kind.name}:{name}"

            for txn_filter in self.apm_config.get("transaction_filters"):
                if txn_filter.get("regex").search(identifier):
                    logger.debug("Got a match for identifier %s", identifier)
                    logger.debug(
                        "Setting tracing_mode as %s",
                        txn_filter.get("tracing_mode"),
                    )
                    return txn_filter.get("tracing_mode")

        # Else use global 'tracing_mode'
        logger.debug("Using global tracing_mode as %s", self.tracing_mode)
        return self.tracing_mode

    # pylint: disable=too-many-locals
    def calculate_liboboe_decision(
        self,
        parent_span_context: SpanContext,
        name: str,
        kind: SpanKind = None,
        attributes: Attributes = None,
        xtraceoptions: Optional[XTraceOptions] = None,
    ) -> dict:
        """Calculates oboe trace decision based on parent span context and APM config."""
        tracestring = None
        if parent_span_context.is_valid and parent_span_context.is_remote:
            tracestring = W3CTransformer.traceparent_from_context(
                parent_span_context
            )
        sw_member_value = parent_span_context.trace_state.get(
            INTL_SWO_TRACESTATE_KEY
        )

        tracing_mode = self.calculate_tracing_mode(
            name,
            kind,
            attributes,
        )

        trigger_trace_mode = OboeTracingMode.get_oboe_trigger_trace_mode(
            self.apm_config.get("trigger_trace")
        )
        # 'sample_rate' is legacy and not supported in NH Python, so give as unset
        sample_rate = self._UNSET

        options = None
        trigger_trace_request = 0
        signature = None
        timestamp = None
        if xtraceoptions:
            options = xtraceoptions.options_header
            trigger_trace_request = xtraceoptions.trigger_trace
            signature = xtraceoptions.signature
            timestamp = xtraceoptions.timestamp

        logger.debug(
            "Creating new oboe decision with "
            "tracestring: %s, "
            "sw_member_value: %s, "
            "tracing_mode: %s, "
            "sample_rate: %s, "
            "trigger_trace_request: %s, "
            "trigger_trace_mode: %s, "
            "options: %s, "
            "signature: %s, "
            "timestamp: %s",
            tracestring,
            sw_member_value,
            tracing_mode,
            sample_rate,
            trigger_trace_request,
            trigger_trace_mode,
            options,
            signature,
            timestamp,
        )

        if self.apm_config.is_lambda:
            logger.debug("Sampling in lambda mode.")
            (
                do_metrics,
                do_sample,
                rate,
                source,
                bucket_rate,
                bucket_cap,
                decision_type,
                auth,
                status_msg,
                auth_msg,
                status,
            ) = self.oboe_settings_api.getTracingDecision(
                tracestring,
                sw_member_value,
                tracing_mode,
                sample_rate,
                trigger_trace_request,
                trigger_trace_mode,
                options,
                signature,
                timestamp,
            )

        else:
            (
                do_metrics,
                do_sample,
                rate,
                source,
                bucket_rate,
                bucket_cap,
                decision_type,
                auth,
                status_msg,
                auth_msg,
                status,
            ) = self.context.getDecisions(
                tracestring,
                sw_member_value,
                tracing_mode,
                sample_rate,
                trigger_trace_request,
                trigger_trace_mode,
                options,
                signature,
                timestamp,
            )

        decision = {
            "do_metrics": do_metrics,
            "do_sample": do_sample,
            "rate": rate,
            "source": source,
            "bucket_rate": bucket_rate,
            "bucket_cap": bucket_cap,
            "decision_type": decision_type,
            "auth": auth,
            "status_msg": status_msg,
            "auth_msg": auth_msg,
            "status": status,
        }
        logger.debug("Got liboboe decision outputs: %s", decision)
        return decision

    def is_decision_continued(self, liboboe_decision: dict) -> bool:
        """Returns True if liboboe decision is a continued one (due to all
        internals being 'continued'), else False"""
        return all(
            val == self._LIBOBOE_CONTINUED
            for val in (
                liboboe_decision["rate"],
                liboboe_decision["source"],
                liboboe_decision["bucket_rate"],
                liboboe_decision["bucket_cap"],
            )
        )

    def otel_decision_from_liboboe(self, liboboe_decision: dict) -> enum.Enum:
        """Formats OTel decision from liboboe decision"""
        decision = Decision.RECORD_AND_SAMPLE
        logger.debug("OTel decision created: %s", decision)
        return decision

    def create_xtraceoptions_response_value(
        self,
        decision: dict,
        parent_span_context: SpanContext,
        xtraceoptions: XTraceOptions,
    ) -> str:
        """Use decision and xtraceoptions to create sanitized xtraceoptions
        response kv with W3C tracestate-allowed delimiters:
        EQUALS_W3C_SANITIZED instead of EQUALS
        COMMA_W3C_SANITIZED instead of COMMA
        """
        response = []

        if xtraceoptions.signature and decision["auth_msg"]:
            response.append(
                INTL_SWO_EQUALS_W3C_SANITIZED.join(
                    [self._XTRACEOPTIONS_RESP_AUTH, decision["auth_msg"]]
                )
            )

        # Include other trace options if valid signature or no signature
        if not decision["auth"] or decision["auth"] < 1:
            trigger_msg = ""
            if xtraceoptions.trigger_trace:
                # If a traceparent header was provided then oboe does not generate the message
                tracestring = None
                if (
                    parent_span_context.is_valid
                    and parent_span_context.is_remote
                ):
                    tracestring = W3CTransformer.traceparent_from_context(
                        parent_span_context
                    )

                if tracestring and decision["decision_type"] == 0:
                    trigger_msg = self._XTRACEOPTIONS_RESP_TRIGGER_IGNORED
                else:
                    trigger_msg = decision["status_msg"]
            else:
                trigger_msg = self._XTRACEOPTIONS_RESP_TRIGGER_NOT_REQUESTED
            response.append(
                INTL_SWO_EQUALS_W3C_SANITIZED.join(
                    [self._XTRACEOPTIONS_RESP_TRIGGER_TRACE, trigger_msg]
                )
            )

            if xtraceoptions.ignored:
                response.append(
                    INTL_SWO_EQUALS_W3C_SANITIZED.join(
                        [
                            self._XTRACEOPTIONS_RESP_IGNORED,
                            (
                                INTL_SWO_COMMA_W3C_SANITIZED.join(
                                    xtraceoptions.ignored
                                )
                            ),
                        ]
                    )
                )

        return ";".join(response)

    def calculate_trace_state(
        self,
        decision: dict,
        parent_span_context: SpanContext,
        xtraceoptions: Optional[XTraceOptions] = None,
    ) -> TraceState:
        """Calculates trace_state based on x-trace-options if provided -- for non-existent or remote parent spans only."""
        # No valid parent i.e. root span, or parent is remote
        if (
            not parent_span_context
            or not parent_span_context.is_valid
            or not parent_span_context.trace_state
        ):
            trace_state = TraceState()
        else:
            trace_state = parent_span_context.trace_state
        # Update with x-trace-options-response if applicable
        # Not a propagated header, so always add at should_sample
        if xtraceoptions and xtraceoptions.include_response:
            trace_state = trace_state.add(
                INTL_SWO_X_OPTIONS_RESPONSE_KEY,
                self.create_xtraceoptions_response_value(
                    decision, parent_span_context, xtraceoptions
                ),
            )
        logger.debug("Calculated trace_state: %s", trace_state)
        return trace_state

    def add_tracestate_capture_to_attributes_dict(
        self,
        attributes_dict: dict,
        decision: dict,
        trace_state: TraceState,
        parent_span_context: SpanContext,
    ) -> dict:
        """Calculate and add SW tracestate capture to attributes_dict,
        which is a dict not an Attributes/MappingProxy object"""
        tracestate_capture = attributes_dict.get(
            self._SW_TRACESTATE_CAPTURE_KEY, None
        )
        if not tracestate_capture:
            trace_state_no_response = W3CTransformer.remove_response_from_sw(
                trace_state
            )
        else:
            # Must retain all potential tracestate pairs for attributes
            attr_trace_state = TraceState.from_header([tracestate_capture])
            new_attr_trace_state = attr_trace_state.update(
                INTL_SWO_TRACESTATE_KEY,
                W3CTransformer.sw_from_span_and_decision(
                    parent_span_context.span_id,
                    W3CTransformer.trace_flags_from_int(decision["do_sample"]),
                ),
            )
            trace_state_no_response = W3CTransformer.remove_response_from_sw(
                new_attr_trace_state
            )
        attributes_dict[
            self._SW_TRACESTATE_CAPTURE_KEY
        ] = trace_state_no_response.to_header()
        return attributes_dict

    def calculate_attributes(
        self,
        span_name: str,
        attributes: Attributes,
        decision: dict,
        trace_state: TraceState,
        parent_span_context: SpanContext,
        xtraceoptions: XTraceOptions,
    ) -> Attributes or None:
        """Calculates Attributes or None based on trace decision, trace state,
        parent span context, xtraceoptions, and existing attributes."""
        logger.debug("Received attributes: %s", attributes)
        # Don't set attributes if not tracing
        otel_decision = self.otel_decision_from_liboboe(decision)
        if not Decision.is_sampled(otel_decision):
            logger.debug(
                "Trace decision not is_sampled - not setting attributes"
            )
            return None

        new_attributes = {}

        if attributes:
            # Copy existing MappingProxyType KV into new_attributes for modification.
            # These attributes may have customer-set KVs from manual SDK calls
            for attr_k, attr_v in attributes.items():
                new_attributes[attr_k] = attr_v

        # Always (root or is_remote) set _INTERNAL_SW_KEYS if extracted
        internal_sw_keys = xtraceoptions.sw_keys
        if internal_sw_keys:
            new_attributes[self._INTERNAL_SW_KEYS] = internal_sw_keys

        # Always (root or is_remote) set custom KVs if extracted from x-trace-options
        custom_kvs = xtraceoptions.custom_kvs
        if custom_kvs:
            for custom_key, custom_value in custom_kvs.items():
                new_attributes[custom_key] = custom_value

        # Always (root or is_remote) set service entry internal KVs
        new_attributes[
            self._INTERNAL_BUCKET_CAPACITY
        ] = f"{decision['bucket_cap']}"
        new_attributes[
            self._INTERNAL_BUCKET_RATE
        ] = f"{decision['bucket_rate']}"

        # sw.tracestate_parent_id is set if:
        #  1. the future span is the entry span of a service
        #  2. there exists a (remote) parent span
        #  3. that parent's trace state contains `sw` for SWO vendor
        sw_value = parent_span_context.trace_state.get(
            INTL_SWO_TRACESTATE_KEY, None
        )
        if sw_value and parent_span_context.is_remote:
            new_attributes[
                self._SW_TRACESTATE_ROOT_KEY
            ] = W3CTransformer.span_id_from_sw(sw_value)

        new_attributes[self._INTERNAL_SAMPLE_RATE] = decision["rate"]
        new_attributes[self._INTERNAL_SAMPLE_SOURCE] = decision["source"]
        logger.debug(
            "Set attributes with service entry internal KVs: %s",
            new_attributes,
        )

        # If unsigned or signed TT (root or is_remote), set TriggeredTrace
        if xtraceoptions.trigger_trace == 1:
            new_attributes[self._INTERNAL_TRIGGERED_TRACE] = True

        # Trace's root span has no valid traceparent nor tracestate
        # so we can't calculate remaining attributes
        if not parent_span_context.is_valid or not trace_state:
            logger.debug(
                "No valid traceparent or no tracestate - returning attributes: %s",
                new_attributes,
            )

            if new_attributes:
                # attributes must be immutable for SamplingResult
                return MappingProxyType(new_attributes)
            return None

        new_attributes = self.add_tracestate_capture_to_attributes_dict(
            new_attributes,
            decision,
            trace_state,
            parent_span_context,
        )

        logger.debug("Setting attributes: %s", new_attributes)

        # attributes must be immutable for SamplingResult
        return MappingProxyType(new_attributes)

    # Note: this inherits deprecated `typing` use by OTel,
    #       I think for compatibility with Python3.7 else TypeError
    def should_sample(
        self,
        parent_context: Optional[OtelContext],
        trace_id: int,
        name: str,
        kind: SpanKind = None,
        attributes: Attributes = None,
        links: Sequence[  # pylint: disable=deprecated-typing-alias
            "Link"
        ] = None,
        trace_state: "TraceState" = None,
    ) -> "SamplingResult":
        """
        Calculates SamplingResult based on calculation of new/continued trace
        decision, new/updated trace state, and new/updated attributes.
        """
        parent_span_context = get_current_span(
            parent_context
        ).get_span_context()

        if not parent_context or not parent_context.get(
            INTL_SWO_X_OPTIONS_KEY
        ):
            xtraceoptions = XTraceOptions()
        else:
            xtraceoptions = parent_context.get(INTL_SWO_X_OPTIONS_KEY)

        liboboe_decision = self.calculate_liboboe_decision(
            parent_span_context, name, kind, attributes, xtraceoptions
        )

        # Always calculate trace_state for propagation
        new_trace_state = self.calculate_trace_state(
            liboboe_decision, parent_span_context, xtraceoptions
        )
        new_attributes = self.calculate_attributes(
            name,
            attributes,
            liboboe_decision,
            new_trace_state,
            parent_span_context,
            xtraceoptions,
        )
        otel_decision = self.otel_decision_from_liboboe(liboboe_decision)

        return SamplingResult(
            otel_decision,
            new_attributes if Decision.is_sampled(otel_decision) else None,
            new_trace_state,
        )


class ParentBasedSwSampler(ParentBased):
    """
    Sampler that respects its parent span's sampling decision, but otherwise
    samples according to the configurations from the NH/AO backend.

    Requires "SolarWindsApmConfig".
    """

    def __init__(self, apm_config: "SolarWindsApmConfig"):
        """
        Uses _SwSampler/liboboe if no parent span.
        Uses _SwSampler/liboboe if parent span is_remote.
        Uses OTEL defaults if parent span is_local.
        """
        super().__init__(
            root=_SwSampler(apm_config),
            remote_parent_sampled=_SwSampler(apm_config),
            remote_parent_not_sampled=_SwSampler(apm_config),
        )

    # should_sample defined by ParentBased

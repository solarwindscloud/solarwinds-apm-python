import logging
import re
import typing

from opentelemetry.context.context import Context

logger = logging.getLogger(__file__)

class XTraceOptions():
    """Formats X-Trace-Options for trigger tracing"""

    _TRACEOPTIONS_CUSTOM = ("^custom-[^\s]*$")
    _TRACEOPTIONS_CUSTOM_RE = re.compile(_TRACEOPTIONS_CUSTOM)

    def __init__(self,
        options_header: str,
        context: typing.Optional[Context] = None
    ):
        """
        Args:
          options: A string of x-trace-options
          context: OTel context that may contain x-trace-options
        
        Examples of options:
          "trigger-trace"
          "trigger-trace;sw-keys=check-id:check-1013,website-id:booking-demo"
          "trigger-trace;custom-key1=value1"
        """
        self.custom_kvs = {}
        self.sw_keys = {}
        self.trigger_trace = False
        self.ts = 0
        self.ignored = []

        if not options_header:
            self.from_context(context)
            return

        # each of options delimited by semicolon
        traceoptions = re.split(r";+", options_header)
        for option in traceoptions:
            # KVs (e.g. sw-keys or custom-key1) are assigned by equals
            option_kv = option.split("=", 2)
            if not option_kv[0]:
                continue

            option_key = option_kv[0].strip()
            if option_key == "trigger-trace":
                if len(option_kv) > 1:
                    logger.warning("trigger-trace must be standalone flag. Ignoring.")
                    self.ignored.append("trigger-trace")
                else:
                    self.trigger_trace = True
        
            elif option_key == "sw-keys":
                # each of sw-keys KVs delimited by comma
                sw_kvs = re.split(r",+", option_kv[1])
                for assignment in sw_kvs:
                    # each of sw-keys values assigned by colon
                    sw_kv = assignment.split(":", 2)
                    if not sw_kv[0]:
                        logger.warning(
                            "Could not parse sw-key assignment {0}. Ignoring.".format(
                                assignment
                            ))
                        self.ignore.append(assignment)
                    else:
                        self.sw_keys.update({sw_kv[0]: sw_kv[1]})

            elif re.match(self._TRACEOPTIONS_CUSTOM_RE, option_key):
                self.custom_kvs[option_key] = option_kv[1].strip()

            elif option_key == "ts":
                try:
                    self.ts = int(option_kv[1])
                except ValueError as e:
                    logger.warning("ts must be base 10 int. Ignoring.")
                    self.ignore.append("ts")
            
            else:
                logger.warning(
                    "{0} is not a recognized trace option. Ignoring".format(
                        option_key
                    ))
                self.ignored.append(option_key)

            if self.ignored:
                logger.warning(
                    "Some x-trace-options were ignored: {0}".format(
                        ", ".join(self.ignored)
                    ))

    def __iter__(self) -> typing.Iterator:
        """Iterable representation of XTraceOptions"""
        yield from self.__dict__.items()

    def __str__(self) -> str:
        """String representation of XTraceOptions"""
        options_str = ""

        if self.trigger_trace:
            options_str += "trigger-trace"

        if len(self.sw_keys) > 0:
            if len(options_str) > 0:
                options_str += ";"
            options_str += "sw-keys="
            for i, (k, v) in enumerate(self.sw_keys.items()):
                options_str += "{0}:{1}".format(k, v)
                if i < len(self.sw_keys) - 1:
                    options_str += ","

        if len(self.custom_kvs) > 0:
            if len(options_str) > 0:
                options_str += ";"
            for i, (k, v) in enumerate(self.custom_kvs.items()):
                options_str += "{0}={1}".format(k, v)
                if i < len(self.custom_kvs) - 1:
                    options_str += ";"
        
        if self.ts > 0:
            if len(options_str) > 0:
                options_str += ";"
            options_str += "ts={0}".format(self.ts)

        return options_str

    def from_context(
        self,
        context: typing.Optional[Context]
    ) -> None:
        """
        Args:
          context: OTel context that may contain x-trace-options
        """
        logger.debug("Setting XTraceOptions from_context with {0}".format(context))
        if not context:
            return

        if "trigger_trace" in context and context["trigger_trace"]:
            self.trigger_trace = True

        if "sw_keys" in context and context["sw_keys"]:
            self.sw_keys = context["sw_keys"]

        if "custom_kvs" in context and context["custom_kvs"]:
            self.custom_kvs = context["custom_kvs"]

        if "ts" in context and context["ts"] > 0:
            self.ts = context["ts"]

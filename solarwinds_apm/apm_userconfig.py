# © 2024 SolarWinds Worldwide, LLC. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at:http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

import json
import logging
import os
import re
from functools import reduce
from typing import Any

from dotenv import dotenv_values

from solarwinds_apm import apm_logging
from solarwinds_apm.apm_constants import (
    INTL_SWO_SUPPORT_EMAIL,
    INTL_SWO_USER_CONFIG_PATH,
)

logger = logging.getLogger(__name__)


class OboeTracingMode:
    """Provides an interface to translate the string representation of tracing_mode to the C-extension equivalent."""

    OBOE_SETTINGS_UNSET = -1
    OBOE_TRACE_DISABLED = 0
    OBOE_TRACE_ENABLED = 1
    OBOE_TRIGGER_DISABLED = 0
    OBOE_TRIGGER_ENABLED = 1

    @classmethod
    def get_oboe_trace_mode(cls, tracing_mode: str) -> int:
        if tracing_mode == "enabled":
            return cls.OBOE_TRACE_ENABLED
        if tracing_mode == "disabled":
            return cls.OBOE_TRACE_DISABLED
        return cls.OBOE_SETTINGS_UNSET

    @classmethod
    def get_oboe_trigger_trace_mode(cls, trigger_trace_mode: str) -> int:
        if trigger_trace_mode == "enabled":
            return cls.OBOE_TRIGGER_ENABLED
        if trigger_trace_mode == "disabled":
            return cls.OBOE_TRIGGER_DISABLED
        return cls.OBOE_SETTINGS_UNSET


class SolarWindsApmUserConfig:
    """SolarWinds APM User Configuration Class
    The precedence: Environment Variables > config file > default values.
    Note that oboe doesn't read configurations by itself. The Python agent needs to
    read environment variables and/or config files and pass them into oboe. This is
    done only once during the initialization and the properties cannot be refreshed.
    """

    # TODO move to base config class if needed
    _CONFIG_FILE_DEFAULT = "./solarwinds-apm-config.json"
    _DELIMITER = "."
    _KEY_MASK = "{}...{}:{}"
    _KEY_MASK_BAD_FORMAT = "{}...<invalid_format>"
    _KEY_MASK_BAD_FORMAT_SHORT = "{}<invalid_format>"
    _SW_PREFIX = "sw_apm_"

    def __init__(
        self,
        **kwargs: int,
    ) -> None:

        logger.warning("!!! Got kwargs as %s", kwargs)

        self.__config = {
            "tracing_mode": kwargs.get(
                "tracing_mode", OboeTracingMode.get_oboe_trace_mode("unset")
            ),
            "trigger_trace": kwargs.get(
                "trigger_trace",
                OboeTracingMode.get_oboe_trigger_trace_mode("enabled"),
            ),
            "collector": kwargs.get(
                "collector", ""
            ),  # the collector address in host:port format.
            "reporter": kwargs.get(
                "reporter", ""
            ),  # the reporter mode, either 'udp' or 'ssl'.
            "log_type": kwargs.get(
                "log_type", apm_logging.ApmLoggingType.default_type()
            ),
            "debug_level": kwargs.get(
                "debug_level", apm_logging.ApmLoggingLevel.default_level()
            ),
            "log_filepath": kwargs.get("log_filepath", ""),
            "service_key": kwargs.get("service_key", ""),
            "hostname_alias": kwargs.get("hostname_alias", ""),
            "trustedpath": kwargs.get("trustedpath", ""),
            "events_flush_interval": int(
                kwargs.get("events_flush_interval", -1)
            ),
            "max_request_size_bytes": int(
                kwargs.get("max_request_size_bytes", -1)
            ),
            "ec2_metadata_timeout": int(
                kwargs.get("ec2_metadata_timeout", 1000)
            ),
            "max_flush_wait_time": int(kwargs.get("max_flush_wait_time", -1)),
            "max_transactions": int(kwargs.get("max_transactions", -1)),
            "trace_metrics": int(kwargs.get("trace_metrics", -1)),
            "token_bucket_capacity": int(
                kwargs.get("token_bucket_capacity", -1)
            ),
            "token_bucket_rate": int(kwargs.get("token_bucket_rate", -1)),
            "bufsize": int(kwargs.get("bufsize", -1)),
            "histogram_precision": int(kwargs.get("histogram_precision", -1)),
            "reporter_file_single": int(kwargs.get("reporter_file_single", 0)),
            "proxy": kwargs.get("proxy", ""),
            # TODO transactionSettings loads
            "transaction_filters": [],
            "transaction_name": kwargs.get("transaction_name", None),
        }
        self.update_with_cnf_file()
        self.update_with_env_var()

    def __str__(self) -> str:
        """String representation of ApmUserConfig is config with masked service key"""
        apm_config = {
            "__config": self._config_mask_service_key(),
        }
        return f"{apm_config}"

    def __setitem__(self, key: str, value: str) -> None:
        """Refresh the configurations in liboboe global struct while user changes settings."""
        if key == "tracing_mode":
            self._set_config_value(key, value)
        else:
            logger.warning(
                "Unsupported SolarWinds APM config key: %s",
                key,
            )

    def __getitem__(self, key: str) -> Any:
        return self.__config[key]

    def __delitem__(self, key: str) -> None:
        del self.__config[key]

    def get(self, key: str, default: Any = None):
        """Get the value of key. Nested keys separated by a dot are also accepted.
        Suggestion: Use mask_service_key() to safely get service_key value"""
        key = key.split(self._DELIMITER)
        value = reduce(
            lambda d, k: d.get(k, None) if isinstance(d, dict) else None,
            key,
            self.__config,
        )
        return value if value is not None else default

    def get_cnf_dict(self) -> Any:
        """Load Python dict from confg file (json), if any"""
        cnf_filepath = os.environ.get("SW_APM_CONFIG_FILE")
        cnf_dict = None

        if not cnf_filepath:
            cnf_filepath = self._CONFIG_FILE_DEFAULT
            if not os.path.isfile(cnf_filepath):
                logger.debug("No config file at %s; skipping", cnf_filepath)
                return cnf_dict

        try:
            with open(cnf_filepath, encoding="utf-8") as cnf_file:
                try:
                    file_content = cnf_file.read()
                    cnf_dict = json.loads(file_content)
                except ValueError as ex:
                    logger.error(
                        "Invalid config file, must be valid json. Ignoring: %s",
                        ex,
                    )
        except FileNotFoundError as ex:
            logger.error("Invalid config file path. Ignoring: %s", ex)
        return cnf_dict

    # TODO implement in base config class
    def _config_mask_service_key(self) -> dict:
        """Return new config with service key masked"""
        config_masked = {}
        for cnf_k, cnf_v in self.__config.items():
            if cnf_k == "service_key":
                cnf_v = self.mask_service_key()
            config_masked[cnf_k] = cnf_v
        return config_masked

    # TODO implement in base config class
    def mask_service_key(self) -> str:
        """Return masked service key except first 4 and last 4 chars"""
        service_key = self.__config.get("service_key")
        if not service_key:
            return ""
        if service_key.strip() == "":
            return service_key

        key_parts = service_key.split(":")
        if len(key_parts) < 2:
            bad_format_key = key_parts[0]
            if len(bad_format_key) < 5:
                return self._KEY_MASK_BAD_FORMAT_SHORT.format(bad_format_key)
            return self._KEY_MASK_BAD_FORMAT.format(
                bad_format_key[0:4],
            )

        api_token = key_parts[0]
        if len(api_token) < 9:
            return service_key
        return self._KEY_MASK.format(
            api_token[0:4],
            api_token[-4:],
            key_parts[1],
        )

    def update_with_cnf_file(self) -> None:
        """Update the settings with the config file (json), if any."""

        def _snake_to_camel_case(key):
            key_parts = key.split("_")
            camel_head = key_parts[0]
            camel_body = "".join(part.title() for part in key_parts[1:])
            return f"{camel_head}{camel_body}"

        cnf_dict = self.get_cnf_dict()
        if not cnf_dict:
            return

        # agent_enabled is special
        cnf_agent_enabled = self.convert_to_bool(
            cnf_dict.get(_snake_to_camel_case("agent_enabled"))
        )
        if cnf_agent_enabled is not None:
            self.agent_enabled = cnf_agent_enabled

        available_cnf = set(self.__config.keys())
        for key in available_cnf:
            # Use internal snake_case config keys to check JSON config file camelCase keys
            val = cnf_dict.get(_snake_to_camel_case(key))
            if val is not None:
                self._set_config_value(key, val)

        self.update_transaction_filters(cnf_dict)

    def update_transaction_filters(self, cnf_dict: dict) -> None:
        """Update configured transaction_filters using config dict"""
        txn_settings = cnf_dict.get("transactionSettings")
        if not txn_settings:
            logger.debug("No transaction filters provided by config.")
            return
        if not isinstance(txn_settings, list):
            logger.warning(
                "Transaction filters must be a list of filters. Ignoring."
            )
            return
        for filter in txn_settings:
            if set(filter) != set(["regex", "tracing"]) or filter[
                "tracing"
            ] not in ["enabled", "disabled"]:
                logger.warning(
                    "Invalid transaction filter rule. Ignoring: %s", filter
                )
                continue

            txn_filter = {}
            txn_filter["tracing_mode"] = OboeTracingMode.get_oboe_trace_mode(
                filter["tracing"]
            )

            if not isinstance(filter["regex"], str):
                logger.warning(
                    "Transaction filter regex must be string or regex. Ignoring: %s",
                    filter,
                )
                continue

            if not len(filter["regex"]) > 0:
                logger.warning(
                    "Transaction filter regex must not be empty. Ignoring: %s",
                    filter,
                )
                continue

            txn_filter_re = None
            try:
                txn_filter_re = re.compile(filter["regex"])
            except re.error:
                logger.warning(
                    "Transaction filter regex invalid. Ignoring: %s",
                    filter,
                )
                continue

            # only the first filter for given `regex` will be used
            if txn_filter_re not in [
                cfilter["regex"]
                for cfilter in self.__config["transaction_filters"]
            ]:
                txn_filter["regex"] = txn_filter_re
                self.__config["transaction_filters"].append(txn_filter)

        logger.debug(
            "Set up transaction filters: %s",
            self.__config["transaction_filters"],
        )

    def update_with_env_var(self) -> None:
        """Update the settings with environment variables."""
        # agent_enabled is special
        env_agent_enabled = self.convert_to_bool(
            os.environ.get("SW_APM_AGENT_ENABLED")
        )
        if env_agent_enabled is not None:
            self.agent_enabled = env_agent_enabled

        available_envvs = set(self.__config.keys())
        for key in available_envvs:
            if key == "transaction":
                # we do not allow complex config options to be set via environment variables
                continue
            env = (self._SW_PREFIX + key).upper()
            val = os.environ.get(env)
            if val is not None:
                self._set_config_value(key, val)

    @classmethod
    def convert_to_bool(cls, val):
        """Converts given value to boolean value if bool or str representation, else None"""
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            if val.lower() == "true":
                return True
            if val.lower() == "false":
                return False
        logger.debug("Received config %s instead of true/false", val)
        return None

    # pylint: disable=too-many-branches,too-many-statements
    def _set_config_value(self, keys_str: str, val: Any) -> Any:
        """Sets the value of the config option indexed by 'keys' to 'val', where 'keys' is a nested key (separated by
        self.delimiter, i.e., the position of the element to be changed in the nested dictionary)
        """
        # _config is a nested dict, thus find most deeply nested sub dict according to the provided keys
        # by defaulting to None in d.get(), we do not allow the creation of any new (key, value) pair, even
        # when we are handling a defaultdict (i.e., with this we do not allow e.g. the creation of new instrumentations
        # through the config)
        keys = keys_str.split(self._DELIMITER)
        sub_dict = reduce(
            lambda d, key: d.get(key, None) if isinstance(d, dict) else None,
            keys[:-1],
            self.__config,
        )
        key = keys[-1]
        try:
            if keys == ["ec2_metadata_timeout"]:
                timeout = int(val)
                if timeout not in range(0, 3001):
                    raise ValueError
                self.__config[key] = timeout
            elif keys == ["token_bucket_capacity"]:
                bucket_cap = float(val)
                if not 0 <= bucket_cap <= 8.0:
                    raise ValueError
                self.__config[key] = bucket_cap
            elif keys == ["token_bucket_rate"]:
                bucket_rate = float(val)
                if not 0 <= bucket_rate <= 4.0:
                    raise ValueError
                self.__config[key] = bucket_rate
            elif keys == ["proxy"]:
                if not isinstance(val, str) or not val.startswith("http://"):
                    raise ValueError
                self.__config[key] = val
            elif keys == ["tracing_mode"]:
                if not isinstance(val, str):
                    raise ValueError
                val = val.lower()
                if val in {"always", "never"}:
                    val = "enabled" if val == "always" else "disabled"
                if val not in ["enabled", "disabled"]:
                    raise ValueError
                oboe_trace_mode = OboeTracingMode.get_oboe_trace_mode(val)
                self.__config[key] = oboe_trace_mode
            elif keys == ["trigger_trace"]:
                if not isinstance(val, str):
                    raise ValueError
                val = val.lower()
                if val in {"always", "never"}:
                    val = "enabled" if val == "always" else "disabled"
                if val not in ["enabled", "disabled"]:
                    raise ValueError
                oboe_trigger_trace = (
                    OboeTracingMode.get_oboe_trigger_trace_mode(val)
                )
                self.__config[key] = oboe_trigger_trace
            elif keys == ["reporter"]:
                if not isinstance(val, str) or val.lower() not in (
                    "udp",
                    "ssl",
                    "null",
                    "file",
                ):
                    raise ValueError
                self.__config[key] = val.lower()
            elif keys == ["debug_level"]:
                val = int(val)
                if not apm_logging.ApmLoggingLevel.is_valid_level(val):
                    raise ValueError
                self.__config[key] = val
            elif keys == ["transaction_name"]:
                self.__config[key] = val
            elif isinstance(sub_dict, dict) and keys[-1] in sub_dict:
                if isinstance(sub_dict[keys[-1]], bool):
                    val = self.convert_to_bool(val)
                else:
                    val = type(sub_dict[keys[-1]])(val)
                sub_dict[keys[-1]] = val
            else:
                logger.warning(
                    "Ignore invalid configuration key: %s",
                    ".".join(keys),
                )
        except (ValueError, TypeError):
            logger.warning(
                "Ignore config option with invalid (non-convertible or out-of-range) type: %s",
                ".".join(keys if keys[0] != "transaction" else keys[1:]),
            )

    def write_to_env_file(
        self,
        env_filepath: str = INTL_SWO_USER_CONFIG_PATH,
    ) -> None:
        """Writes config to .env file at filepath. Overwrites file completely
        if it exists."""
        if os.path.exists(env_filepath):
            if os.path.isfile(env_filepath):
                os.remove(env_filepath)
            else:
                os.rmdir(env_filepath)

        with open(env_filepath, "x", encoding="utf-8") as env_file:
            for config_key, config_value in self.__config.items():
                # TODO transactionSettings dumps
                env_file.write(f"{config_key}={config_value}\n")


def extract_user_config(
    env_filepath: str = INTL_SWO_USER_CONFIG_PATH,
) -> "SolarWindsApmUserConfig":
    """Extract UserConfig from .env file at filepath. Removes file at
    path after extraction."""
    if not os.path.exists(env_filepath) or not os.path.isfile(env_filepath):
        logger.error(
            "ERROR: Could not extracting internal config. Please contact %s",
            INTL_SWO_SUPPORT_EMAIL,
        )

    env_config = dotenv_values(env_filepath)
    os.remove(env_filepath)
    return SolarWindsApmUserConfig(**env_config)

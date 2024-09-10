from collections.abc import Callable
from importlib.resources import files
import logging
from pathlib import Path
from typing import TypeVar

import yaml

import osc_kreuz.str_keys_conventions as skc


log = logging.getLogger()

# lists for constructing default config paths
default_config_file_path = Path("osc-kreuz")
default_config_file_name_options = [
    "osc-kreuz_conf.yml",
    "osc-kreuz-conf.yml",
    "osc-kreuz_config.yml",
    "osc-kreuz-config.yml",
    "config.yml",
    "conf.yml",
]
default_config_file_locations = [
    Path.home() / ".config",
    Path("/etc"),
    Path("/usr/local/etc"),
]

deprecated_config_strings = {
    skc.globalconfig: ["globalconfig"],
    "ip": ["oscr_ip"],
    skc.inputport_ui: ["inputport_ui"],
    skc.inputport_data: ["inputport_data"],
    skc.inputport_settings: ["inputport_settings"],
}


def read_config(config_path) -> dict:
    # get Config Path:
    if config_path is None:
        # check different paths for a config file, with the highest one taking precedence
        for possible_config_path in (
            base / default_config_file_path / filename
            for base in default_config_file_locations
            for filename in default_config_file_name_options
        ):
            if possible_config_path.exists():
                config_path = possible_config_path
                log.info(f"Loading config file {config_path}")
                break

    if config_path is None:
        log.warning(f"Could not find config, loading default config")
        # load the default config embedded into this package using files
        config_path = files("osc_kreuz").joinpath("config_default.yml")
        config = yaml.load(config_path.read_bytes(), Loader=yaml.Loader)
    else:
        # read config file
        with open(config_path) as f:
            config = yaml.load(f, Loader=yaml.Loader)

    return config


T = TypeVar("T")


def read_config_option(
    config,
    option_name: str,
    option_type: Callable[..., T] | None = None,
    default: T = None,
) -> T:
    if option_name in config:
        pass
    elif option_name in deprecated_config_strings:
        for deprecated_option_name in deprecated_config_strings[option_name]:
            if deprecated_option_name in config:
                log.warning(
                    f"option {deprecated_option_name} is deprecated, please use {option_name} instead"
                )
                option_name = deprecated_option_name
                break
    else:
        return default

    val = config[option_name]

    if option_type is None:
        return val

    try:
        return option_type(val)
    except Exception:
        log.error(f"Could not read config option {option_name}, invalid type")
    return config[option_name]

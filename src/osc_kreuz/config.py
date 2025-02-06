from collections.abc import Callable
from importlib.resources import files
import logging
from pathlib import Path
from typing import TypeVar
import os
import yaml

import osc_kreuz.str_keys_conventions as skc


log = logging.getLogger()

default_config_file_folder = Path("osc-kreuz")


xdg_config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
state_directory = (
    Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    / default_config_file_folder
)

# lists for constructing default config paths
default_config_file_name_options = [
    "osc-kreuz_conf.yml",
    "osc-kreuz-conf.yml",
    "osc-kreuz_config.yml",
    "osc-kreuz-config.yml",
    "config.yml",
    "conf.yml",
]
default_config_file_locations = [
    xdg_config_home,
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


class ConfigError(Exception):
    pass


def read_config(config_path: str | Path | None) -> dict:
    """reads the config file from path config_path. if no path is supplied go through the default config paths, if no file is found use the embedded default config

    Args:
        config_path (str | Path | None): path of the config file

    Raises:
        ConfigError: raised when loading the file failed

    Returns:
        dict: the config as a dict
    """

    # get Config Path:
    if config_path is None:
        # check different paths for a config file, with the highest one taking precedence
        for possible_config_path in (
            base / default_config_file_folder / filename
            for base in default_config_file_locations
            for filename in default_config_file_name_options
        ):
            if possible_config_path.exists():
                config_path = possible_config_path
                log.info(f"Loading config file {config_path}")
                break

    if config_path is None:
        log.warning("Could not find config, loading default config")
        # load the default config embedded into this package using files
        default_config = files("osc_kreuz").joinpath("config_default.yml")
        try:
            config = yaml.load(default_config.read_bytes(), Loader=yaml.Loader)
        except yaml.YAMLError as e:
            log.error(f"Failed to load the default config file, Uh-Oh!: YAMLError {e}")
            raise ConfigError
    else:
        # read config file
        with open(config_path) as f:
            try:
                config = yaml.load(f, Loader=yaml.Loader)
            except yaml.YAMLError as e:
                log.error(f"Failed to load config file: YAMLError {e}")
                raise ConfigError

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


state_suffix = "_state"


def add_renderer_to_state_file(renderer: str, hostname: str, port: int):
    if not state_directory.exists():
        state_directory.mkdir()

    renderer_str = f"{hostname};{port}\n"
    with open(state_directory / f"{renderer}{state_suffix}.csv", "a+") as f:
        f.seek(0)
        for line in f:
            if line == renderer_str:
                break
        else:
            f.write(renderer_str)


def read_renderer_state_file(renderer: str) -> list[dict]:
    receivers = []
    filename = state_directory / f"{renderer}{state_suffix}.csv"
    if not filename.exists():
        return receivers
    try:
        with open(filename, "r") as f:
            for line in f:
                hostname, port = line.strip("\n").split(";")
                receivers.append({"hostname": hostname, "port": int(port)})
    except Exception as e:
        log.warning(f"exception while reading {renderer} state file: {e}")

    return receivers


def get_renderers_with_state_file() -> list[str]:
    renderers = []

    for filename in state_directory.glob(f"*{state_suffix}.csv"):
        renderers.append(filename.stem[: -len(state_suffix)])
    return renderers

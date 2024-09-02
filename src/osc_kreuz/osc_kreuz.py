#!/usr/bin/env python3

from types import NoneType
from typing import Callable
from osc_kreuz.config import read_config, read_config_option
import osc_kreuz.str_keys_conventions as skc
from threading import Event
from osc_kreuz.soundobject import SoundObject
from osc_kreuz.renderer import Renderer
import osc_kreuz.renderer as rendererclass
import osc_kreuz.osccomcenter as osccomcenter

from pathlib import Path
from importlib.resources import files

import click
import signal
import yaml
import logging
import sys

logFormat = "%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]: %(message)s"
timeFormat = "%Y-%m-%d %H:%M:%S"
logging.basicConfig(format=logFormat, datefmt=timeFormat, level=logging.INFO)
log = logging.getLogger("main")

stop_event = Event()

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


def read_config(config_path) -> dict:
    # get Config Path:
    if config_path is None:
        # TODO move to function
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
        log.warn(f"Could not find config, loading default config")
        config_path = files("osc_kreuz").joinpath("config_default.yml")
        config = yaml.load(config_path.read_bytes(), Loader=yaml.Loader)
    else:
        # read config file
        with open(config_path) as f:
            config = yaml.load(f, Loader=yaml.Loader)

    return config


def read_config_option(
    config, option_name: str, option_type: Callable | NoneType = None, default=None
):
    if option_name in config:
        val = config[option_name]

        if option_type is None:
            return val

        try:
            return option_type(val)
        except Exception:
            log.error(f"Could not read config option {option_name}")
        return config[option_name]
    else:
        return default


def signal_handler(*args):
    stop_event.set()


def debug_prints(globalconfig, extendedOscInput, verbose):
    log.debug("max number of sources is set to %s", str(globalconfig["number_sources"]))
    log.debug("number of rendering units is %s", str(globalconfig["n_renderengines"]))

    try:
        render_units = globalconfig["render_units"]
    except KeyError:
        render_units = []

    for key in ["ambi", "wfs", "reverb"]:
        if key in render_units:
            log.debug(f"{key} index: {render_units.index(key)}")

    log.debug("UI listenport: %s", globalconfig[skc.inputport_ui])
    log.debug("DATA listenport (for automation): %s", globalconfig[skc.inputport_data])
    log.debug(
        "port for settings, ping and client subscription is: %s",
        globalconfig[skc.inputport_settings],
    )
    if extendedOscInput:
        log.debug("extended osc-string listening activated")
    else:
        log.debug("only basic osc-strings will be accepted")

    log.debug("max gain is %s", globalconfig[skc.max_gain])

    if Renderer.debugCopy:
        log.debug("Osc-Messages will be copied to somewhere")
    else:
        log.debug("No Debug client configured")

    log.debug("Verbosity Level is %s", verbose)
    if verbose == 1:
        log.debug("outgoing osc will be printed in console")
    elif verbose > 1:
        log.debug("incoming and outgoing osc will be printed in console")


@click.command(help="OSC Message Processor and Router")
@click.option(
    "-c",
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True, path_type=Path),
    help="path to configfile",
)
@click.option(
    "--oscdebug",
    help='ip and port for debug messages, e.g. "130.149.23.46:55112"',
    type=click.STRING,
)
@click.option("-v", "--verbose", count=True, help="increase verbosity level.")
@click.version_option()
def main(config_path, oscdebug, verbose):

    if verbose > 0:
        log.setLevel(logging.DEBUG)

    config = read_config(config_path)

    # setup debug osc client
    if oscdebug:
        oscDebugParams = oscdebug.split(":")
        debugIp = oscDebugParams[0]
        debugPort = int(oscDebugParams[1])
        Renderer.createDebugClient(debugIp, debugPort)
        Renderer.debugCopy = True

    # read config values
    globalconfig = config[skc.globalconfig]
    renderengines = read_config_option(
        globalconfig, "render_units", None, ["ambi, wfs"]
    )
    numberofsources = read_config_option(globalconfig, "number_sources", int, 64)
    room_scaling_factor = read_config_option(
        globalconfig, "room_scaling_factor", float, 1.0
    )
    n_direct_sends = read_config_option(globalconfig, "number_direct_sends", int, 32)
    ip = read_config_option(globalconfig, "ip", str, "127.0.0.1")
    port_ui = read_config_option(globalconfig, "port_ui", int, 4455)
    port_data = read_config_option(globalconfig, "port_data", int, 4007)
    port_settings = read_config_option(globalconfig, "port_settings", int, 4999)

    n_renderunits = len(renderengines)
    globalconfig["n_renderengines"] = n_renderunits

    # set global config in objects
    SoundObject.readGlobalConfig(globalconfig)
    SoundObject.number_renderer = n_renderunits
    Renderer.globalConfig = globalconfig

    # setup number of sources

    Renderer.numberOfSources = numberofsources

    # Data initialisation
    soundobjects: list[SoundObject] = [
        SoundObject(objectID=i + 1, coordinate_scaling_factor=room_scaling_factor)
        for i in range(numberofsources)
    ]

    # soundobjects are added as a class variable to the render class, so every renderer has access to them
    Renderer.sources = soundobjects

    receivers: list[Renderer] = []

    # creating audiorouters
    log.info("setting up receivers")
    if "receivers" in config:
        for receiver_config in config["receivers"]:
            if not "type" in receiver_config:
                log.warning("receiver has no type specified, skipping")
                continue
            try:
                receivers.append(rendererclass.createRendererClient(receiver_config))
            except rendererclass.RendererException as e:
                log.error(e)
                sys.exit(-1)

    # Setup OSC Com center
    osc = osccomcenter.OSCComCenter(
        soundobjects=soundobjects,
        receivers=receivers,
        renderengines=renderengines,
        n_sources=numberofsources,
        n_direct_sends=n_direct_sends,
        ip=ip,
        port_ui=port_ui,
        port_data=port_data,
        port_settings=port_settings,
    )
    osc.setupOscBindings()
    osc.setVerbosity(verbose)

    # TODO handle this somewhere else
    extendedOscInput = True
    if verbose > 0:
        debug_prints(globalconfig, extendedOscInput, verbose)

    log.info("OSC router ready to use")
    log.info("have fun...")

    signal.signal(signal.SIGTERM, signal_handler)
    # signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGUSR1, signal_handler)
    stop_event.wait()


if __name__ == "__main__":
    main()

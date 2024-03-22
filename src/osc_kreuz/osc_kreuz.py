#!/usr/bin/env python3

import osc_kreuz.str_keys_conventions as skc

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

    osccomcenter.setVerbosity(verbose)
    if verbose > 0:
        log.setLevel(logging.DEBUG)

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

    # setup debug osc client
    if oscdebug:
        oscDebugParams = oscdebug.split(":")
        debugIp = oscDebugParams[0]
        debugPort = int(oscDebugParams[1])
        Renderer.createDebugClient(debugIp, debugPort)
        Renderer.debugCopy = True

    # set extended OSC String Input Format (whatever that may be)
    extendedOscInput = True
    osccomcenter.extendedOscInput = extendedOscInput

    # prepare globalconfig
    globalconfig = config["globalconfig"]

    try:
        n_renderunits = len(globalconfig["render_units"])
    except KeyError:
        n_renderunits = 0
    globalconfig["n_renderengines"] = n_renderunits

    # set global config in objects
    SoundObject.readGlobalConfig(globalconfig)
    SoundObject.number_renderer = n_renderunits
    Renderer.globalConfig = globalconfig
    osccomcenter.globalconfig = globalconfig

    # setup number of sources
    numberofsources = int(globalconfig["number_sources"])  # 64

    Renderer.numberOfSources = numberofsources

    # Data initialisation
    soundobjects: list[SoundObject] = []
    for i in range(numberofsources):
        soundobjects.append(SoundObject(objectID=i + 1))

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
    osccomcenter.soundobjects = soundobjects
    osccomcenter.receivers = receivers

    osccomcenter.setupOscBindings()

    #
    if verbose > 0:
        debug_prints(globalconfig, extendedOscInput, verbose)

    log.info("OSC router ready to use")
    log.info("have fun...")

    signal.pause()


if __name__ == "__main__":
    main()

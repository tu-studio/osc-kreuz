#!/usr/bin/env python3

import logging
from pathlib import Path
import signal
import sys
from threading import Event

import click
import yaml

from osc_kreuz.config import read_config, read_config_option
import osc_kreuz.osccomcenter as osccomcenter
from osc_kreuz.renderer import Renderer
import osc_kreuz.renderer as rendererclass
from osc_kreuz.soundobject import SoundObject
import osc_kreuz.str_keys_conventions as skc

logFormat = "%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]: %(message)s"
timeFormat = "%Y-%m-%d %H:%M:%S"
logging.basicConfig(format=logFormat, datefmt=timeFormat, level=logging.INFO)
log = logging.getLogger("main")

stop_event = Event()


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
@click.option(
    "-i",
    "--ip",
    help="ip the osc_kreuz listens on, overrides the value read from the config",
    type=click.STRING,
)
@click.option(
    "-u",
    "--port_ui",
    help="port the osc_kreuz listens on for data input by a user, overrides the value read from the config",
    type=click.INT,
)
@click.option(
    "-d",
    "--port_data",
    help="port the osc_kreuz listens on for automated data, overrides the value read from the config",
    type=click.INT,
)
@click.option(
    "-s",
    "--port_settings",
    help="port the osc_kreuz listens on for settings, overrides the value read from the config",
    type=click.INT,
)
@click.option("-v", "--verbose", count=True, help="increase verbosity level.")
@click.version_option()
def main(config_path, oscdebug, verbose, ip, port_ui, port_data, port_settings):
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
    globalconfig = read_config_option(config, skc.globalconfig, default={})

    renderengines = read_config_option(
        globalconfig, "render_units", None, ["ambi, wfs"]
    )
    numberofsources = read_config_option(globalconfig, "number_sources", int, 64)
    room_scaling_factor = read_config_option(
        globalconfig, "room_scaling_factor", float, 1.0
    )
    n_direct_sends = read_config_option(globalconfig, "number_direct_sends", int, 32)
    if ip is None:
        ip = read_config_option(globalconfig, "ip", str, "127.0.0.1")
    if port_ui is None:
        port_ui = read_config_option(globalconfig, "port_ui", int, 4455)
    if port_data is None:
        port_data = read_config_option(globalconfig, "port_data", int, 4007)

    if port_settings is None:
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

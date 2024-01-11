#!/usr/bin/env python3

import seamless_oscrouter.str_keys_conventions as skc
import seamless_oscrouter.conversionsTools as ct

from seamless_oscrouter.soundobjectclass import SoundObject
from seamless_oscrouter.rendererclass import Renderer
import seamless_oscrouter.rendererclass as rendererclass
import seamless_oscrouter.osccomcenter as osccomcenter

from functools import partial
from pathlib import Path

from oscpy.server import OSCThreadServer
import click
import signal
import argparse
import yaml
import logging

logFormat = "%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]: %(message)s"
timeFormat = "%Y-%m-%d %H:%M:%S"
logging.basicConfig(format=logFormat, datefmt=timeFormat, level=logging.INFO)
log = logging.getLogger("main")


default_config_file_path = "seamless-core/oscrouter/oscRouterConfig.yml"


def debug_prints(globalconfig, extendedOscInput, verbose):
    log.debug("max number of sources is set to", str(globalconfig["number_sources"]))
    log.debug(
        "number of rendering units is", str(globalconfig["numberofrenderengines"])
    )
    if "index_ambi" in globalconfig.keys():
        log.debug("ambisonics index:", globalconfig["index_ambi"])
    if "index_wfs" in globalconfig.keys():
        log.debug("wfs index:", globalconfig["index_wfs"])
    if "index_reverb" in globalconfig.keys():
        log.debug("reverb index:", globalconfig["index_reverb"])

    log.debug("UI listenport:", globalconfig[skc.inputport_ui])
    log.debug("DATA listenport (for automation):", globalconfig[skc.inputport_data])
    log.debug(
        "port for settings, ping and client subscription is:",
        globalconfig[skc.inputport_settings],
    )
    if extendedOscInput:
        log.debug("extended osc-string listening activated")
    else:
        log.debug("only basic osc-strings will be accepted")

    log.debug("max gain is", globalconfig[skc.max_gain])

    if Renderer.debugCopy:
        log.debug("Osc-Messages will be copied to somewhere")
    else:
        log.debug("No Debug client configured")

    log.debug("Verbosity Level is", verbose)
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
def main(config_path, oscdebug, verbose):
    osccomcenter.setVerbosity(verbose)
    if verbose > 0:
        log.setLevel(logging.DEBUG)

    # get Config Path:
    if config_path is None:
        # check different paths for a config file, with the highest one taking precedence
        for possible_config_path in [
            Path.home() / ".config" / default_config_file_path,
            Path("/etc") / default_config_file_path,
            Path("/usr/local/etc") / default_config_file_path,
        ]:
            if possible_config_path.exists():
                config_path = possible_config_path
                break

        if config_path is None:
            log.warning("Could not find config file, falling back to default config!")
            config_path = Path(__file__).parent.parent / "oscRouterConfig.yml"

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
    globalconfig["numberofrenderengines"] = config["globalconfig"]["number_renderunits"]

    # set global config in objects
    SoundObject.readGlobalConfig(globalconfig)
    SoundObject.number_renderer = int(globalconfig["numberofrenderengines"])
    Renderer.globalConfig = globalconfig
    osccomcenter.globalconfig = globalconfig

    # setup number of sources
    numberofsources = int(globalconfig["number_sources"])  # 64

    Renderer.numberOfSources = numberofsources

    # region Data initialisation
    soundobjects: [SoundObject] = []
    for i in range(numberofsources):
        soundobjects.append(SoundObject(objectID=i + 1))
    Renderer.sources = soundobjects

    audiorouter: Renderer = None
    audiorouterWFS: Renderer = None
    renderengineClients: [Renderer] = []
    dataClients: [Renderer] = []
    uiClients: [Renderer] = []
    allClients: [Renderer] = []

    # creating audiorouters
    log.info("setting audiorouter connection")
    if "audiorouters" in config:
        for dic in config["audiorouters"]:
            if not audiorouter:
                audiorouter = rendererclass.createRendererClient(
                    skc.renderClass.Audiorouter, kwargs=dic
                )
            else:
                audiorouter.addDestination(dic["ipaddress"], dic["listenport"])
    else:
        log.warning("NO AUDIOROUTER CONFIGURED")

    # creating WFS audiorouters
    if "audioroutersWFS" in config:
        for dic in config["audioroutersWFS"]:
            if not audiorouterWFS:
                audiorouterWFS = rendererclass.createRendererClient(
                    skc.renderClass.AudiorouterWFS, kwargs=dic
                )
            else:
                audiorouterWFS.addDestination(dic["ipaddress"], dic["listenport"])
    else:
        log.warning("NO WFS-AUDIOROUTER CONFIGURED")

    # creating render engines
    log.info("setting renderer connectio")
    if "renderengines" in config:
        for render_type, render_engine in config["renderengines"].items():
            renderengineClients.append(
                rendererclass.createRendererClient(
                    skc.renderClass(render_type), render_engine
                )
            )
    else:
        log.info("no renderer clients in configfile")

    # creating data clients
    log.info("setting data_client connections")
    if "dataclients" in config:
        for client_type, dataclient in config["dataclients"].items():
            dataClients.append(
                rendererclass.createRendererClient(
                    skc.renderClass(client_type), kwargs=dataclient
                )
            )
    else:
        log.warning("no data clients in configfile")

    # creating UI clients
    log.info("setting UI-client connections")
    if "viewclients" in config:
        for client_type, viewclient in config["viewclients"].items():
            uiClients.append(
                rendererclass.createRendererClient(
                    skc.renderClass(client_type), kwargs=viewclient
                )
            )
    else:
        log.info("no UI-clients in configfile")

    # add all clients to the allclients list
    for ren in [*renderengineClients, *dataClients, *uiClients]:
        allClients.append(ren)

    # Setup OSC Com center
    osccomcenter.soundobjects = soundobjects
    osccomcenter.audiorouter = audiorouter
    osccomcenter.audiorouterWFS = audiorouterWFS
    osccomcenter.renderengineClients = renderengineClients
    osccomcenter.dataClients = dataClients
    osccomcenter.uiClients = uiClients
    osccomcenter.allClients = allClients

    osccomcenter.setupOscBindings()

    #
    if verbose > 0:
        debug_prints(globalconfig, extendedOscInput, verbose)

    log.info("OSC router ready to use")
    log.info("have fun...")

    signal.pause()


if __name__ == "__main__":
    main()

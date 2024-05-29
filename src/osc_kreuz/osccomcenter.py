from osc_kreuz.renderer import Renderer, ViewClient
import osc_kreuz.str_keys_conventions as skc
from oscpy.server import OSCThreadServer
from functools import partial
from osc_kreuz.soundobject import SoundObject
import ipaddress
import logging

log = logging.getLogger("OSCcomcenter")


soundobjects: list[SoundObject] = []

clientSubscriptions = {}
receivers: list[Renderer] = []
globalconfig = dict()
extendedOscInput = True
verbosity = 0
bPrintOSC = False


def setVerbosity(v: int):
    global verbosity, bPrintOSC
    verbosity = v
    bPrintOSC = v >= 2
    Renderer.setVerbosity(v)
    log.debug("verbosity set to", v)


osc_ui_server = OSCThreadServer()
osc_data_server = OSCThreadServer()
osc_setting_server = OSCThreadServer()


oscr_ip = False


def setupOscSettingsBindings():
    osc_setting_server.listen(
        address="0.0.0.0", port=globalconfig["inputport_settings"], default=True
    )

    osc_setting_server.bind(
        "/oscrouter/debug/osccopy".encode(), oscreceived_debugOscCopy
    )
    osc_setting_server.bind("/oscrouter/debug/verbose".encode(), oscreceived_verbose)
    osc_setting_server.bind(
        "/oscrouter/subscribe".encode(), oscreceived_subscriptionRequest
    )
    osc_setting_server.bind(
        "/oscrouter/unsubscribe".encode(), osc_handler_unsubscribe
    )
    osc_setting_server.bind("/oscrouter/ping".encode(), oscreceived_ping)
    osc_setting_server.bind("/oscrouter/pong".encode(), oscreceived_pong)
    osc_setting_server.bind("/oscrouter/dump".encode(), oscreceived_dump)

    global oscr_ip
    if "oscr_ip" in globalconfig.keys() and checkIp(globalconfig["oscr_ip"]):
        oscr_ip = globalconfig["oscr_ip"].encode()


def oscreceived_ping(*args):

    if checkPort(args[0]):
        vals = [oscr_ip] if oscr_ip else []
        osc_setting_server.answer(b"/oscrouter/pong", port=args[0], values=vals)


def oscreceived_pong(*args):

    try:
        clientName = args[0]
        clientSubscriptions[clientName].receivedIsAlive()
    except:
        if verbosity > 0:
            _name = ""
            if len(args) > 0:
                _name = args[0]
            log.info("no renderer for pong message {}".format(_name))


def oscreceived_subscriptionRequest(*args) -> None:
    """OSC Callback for subscription Requests.

    These requests follow the format:
    /oscrouter/subscribe myname 31441 xyz 0 5
    /oscrouter/subscribe [client_name] [client_port] [coordinate_format] [source index as value? (0 or 1)] [update rate]
    args[0] nameFor Client
    args[1] port client listens to
    args[2] format client expects
    args[3] send source index as value instead of inside the osc prefix
    args[4] source position update rate
    """

    viewClientInitValues = {}
    vCName = args[0]
    subArgs = len(args)
    if subArgs >= 2:
        if checkPort(args[1]):
            viewClientInitValues["port"] = args[1]

            _ip = osc_setting_server.get_sender()[1]

            viewClientInitValues["hostname"] = _ip

            # if subArgs>2:
            #     initKeys = ['dataformat', 'indexAsValue', 'updateintervall']
            #     for i in range(2, subArgs):
            #         viewClientInitValues[initKeys[i-2]] = args[i]
            try:
                viewClientInitValues["dataformat"] = args[2].decode()
            except:
                pass
            try:
                viewClientInitValues["indexAsValue"] = args[3]
            except:
                pass
            try:
                viewClientInitValues["updateintervall"] = args[4]
            except:
                pass
        newViewClient = ViewClient(vCName, **viewClientInitValues)

        clientSubscriptions[vCName] = newViewClient
        # TODO check if this is threadsafe (it probably isn't)
        receivers.append(newViewClient)
        newViewClient.checkAlive(deleteClient)

    else:
        if verbosity > 0:
            log.info("not enough arguments für view client")

def osc_handler_unsubscribe(*args) -> None:
    """OSC Callback for unsubscribe Requests.

    These requests follow the format:
    /oscrouter/unsubscribe myname 
    /oscrouter/unsubscribe [client_name]
    args[0] nameFor Client
    """

    subArgs = len(args)
    if len(args) >= 1:
        client_name = args[0]
        try:
            view_client = clientSubscriptions[client_name]
            deleteClient(view_client, client_name)

        except KeyError:
            log.warn(f"can't delete client {client_name}, it does not exist")
    else:
        log.warn("not enough arguments für view client")


def oscreceived_dump(*args):
    pass
    # TODO: dump all source data to renderer


def deleteClient(viewC, alias):
    # TODO check if this is threadsafe (it probably isn't)

    if verbosity > 0:
        log.info("deleting client", viewC, alias)
    try:
        receivers.remove(viewC)
        del clientSubscriptions[alias]
        log.info(f"removed client {alias}")
    except (ValueError, KeyError):
        log.warn(f"tried to delete receiver {alias}, but it does not exist")




def checkPort(port) -> bool:
    if type(port) == int and 1023 < port < 65535:
        return True
    else:
        if verbosity > 0:
            log.info("port", port, "not legit")
        return False


def checkIp(ip) -> bool:
    ipalright = True
    try:
        _ip = "127.0.0.1" if ip == "localhost" else ip
        _ = ipaddress.ip_address(_ip)
    except:
        ipalright = False
        if verbosity > 0:
            log.info("ip address", ip, "not legit")

    return ipalright


def checkIpAndPort(ip, port) -> bool:
    return checkIp(ip) and checkPort(port)


def oscreceived_debugOscCopy(*args):
    ip = ""
    port = 0
    if len(args) == 2:
        ip = args[0].decode()
        port = args[1]
    elif len(args) == 1:
        ipport = args[0].decode().split(":")
        if len(ipport) == 2:
            ip = ipport[0]
            port = ipport[1]
    else:
        Renderer.debugCopy = False
        log.info("debug client: invalid message format")
        return
    try:
        ip = "127.0.0.1" if ip == "localhost" else ip
        osccopy_ip = ipaddress.ip_address(ip)
        osccopy_port = int(port)
    except:
        log.info("debug client: invalid ip or port")
        return
    log.info(f"debug client connected: {ip}:{port}")

    if 1023 < osccopy_port < 65535:
        Renderer.createDebugClient(str(osccopy_ip), osccopy_port)
        Renderer.debugCopy = True
        return

    Renderer.debugCopy = False


def oscreceived_verbose(*args):
    vvvv = -1
    try:
        vvvv = int(args[0])
    except:
        setVerbosity(0)
        # verbosity = 0
        # Renderer.setVerbosity(0)
        log.error("wrong verbosity argument")
        return

    if 0 <= vvvv <= 2:
        setVerbosity(vvvv)
        # global verbosity
        # verbosity = vvvv
        # Renderer.setVerbosity(vvvv)
    else:
        setVerbosity(0)


def build_osc_paths(
    osc_path_type: skc.OscPathType, value: str, idx: int | None = None
) -> list[str]:
    """Builds a list of all needed osc paths for a given osc path Type and the value.
    If idx is supplied, the extended path is used. Aliases for the value are handled

    Args:
        osc_path_type (skc.OscPathType): Osc Path Type
        value (str): value to be written into the OSC strings.
        idx (int | None, optional): Index of the source if the extended format should be used. Defaults to None.

    Raises:
        KeyError: Raised when the Osc Path Type does not exist

    Returns:
        list[str]: list of OSC path strings
    """
    if osc_path_type not in skc.osc_paths:
        raise KeyError(f"Invalid OSC Path Type: {osc_path_type}")
    try:
        aliases = skc.osc_aliases[value]
    except KeyError:
        aliases = [value]

    if idx is None:
        paths = skc.osc_paths[osc_path_type]["base"]
    else:
        paths = skc.osc_paths[osc_path_type]["extended"]

    return [path.format(val=alias, idx=idx) for alias in aliases for path in paths]


def setupOscBindings():
    """Sets up all Osc Bindings"""
    setupOscSettingsBindings()

    osc_ui_server.listen(
        address="0.0.0.0", port=globalconfig[skc.inputport_ui], default=True
    )
    osc_data_server.listen(
        address="0.0.0.0", port=globalconfig[skc.inputport_data], default=True
    )

    n_sources = globalconfig["number_sources"]

    # Setup OSC Callbacks for positional data
    for key in skc.posformat.keys():

        for addr in build_osc_paths(skc.OscPathType.Position, key):
            bindToDataAndUiPort(addr, partial(oscreceived_setPosition, key))

        if extendedOscInput:
            for i in range(n_sources):
                idx = i + 1
                for addr in build_osc_paths(skc.OscPathType.Position, key, idx=idx):
                    bindToDataAndUiPort(
                        addr, partial(oscreceived_setPositionForSource, key, i)
                    )

    # Setup OSC for Wonder Attribute Paths
    for key in skc.SourceAttributes:
        for addr in build_osc_paths(skc.OscPathType.Properties, key.value):
            log.info(f"WFS Attr path: {addr}")
            bindToDataAndUiPort(addr, partial(oscReceived_setValueForAttribute, key))

        for i in range(n_sources):
            idx = i + 1
            for addr in build_osc_paths(skc.OscPathType.Properties, key.value, idx):
                bindToDataAndUiPort(
                    addr, partial(oscreceived_setValueForSourceForAttribute, i, key)
                )

    # sendgain input
    for spatGAdd in ["/source/send/spatial", "/send/gain", "/source/send"]:
        bindToDataAndUiPort(spatGAdd, partial(oscreceived_setRenderGain))

    # get list of all render units
    try:
        render_units = globalconfig["render_units"]
    except KeyError:
        render_units = []

    # Setup OSC Callbacks for all render units
    for rendIdx, render_unit in enumerate(render_units):
        # get aliases for this render unit, if none exist just use the base name

        # add callback to base paths for all all aliases
        for addr in build_osc_paths(skc.OscPathType.Gain, render_unit):
            bindToDataAndUiPort(
                addr, partial(oscreceived_setRenderGainToRenderer, rendIdx)
            )

        # add callback to extended paths
        if extendedOscInput:
            for i in range(n_sources):
                idx = i + 1
                for addr in build_osc_paths(skc.OscPathType.Gain, render_unit, idx):
                    bindToDataAndUiPort(
                        addr,
                        partial(
                            oscreceived_setRenderGainForSourceForRenderer, i, rendIdx
                        ),
                    )

    directSendAddr = "/source/send/direct"
    bindToDataAndUiPort(directSendAddr, partial(oscreceived_setDirectSend))

    # XXX can this be removed?
    # if extendedOscInput:
    #     for i in range(n_sources):
    #         idx = i + 1
    #         for addr in [
    #             ("/source/" + str(idx) + "/rendergain"),
    #             ("/source/" + str(idx) + "/send/spatial"),
    #             ("/source/" + str(idx) + "/spatial"),
    #             ("/source/" + str(idx) + "/sendspatial"),
    #         ]:

    #             bindToDataAndUiPort(
    #                 addr, partial(oscreceived_setRenderGainForSource, i)
    #             )

    #             # TODO fix whatever this is
    #             # This adds additional osc paths for the render engines by index
    #             # for j in range(len(renderengineClients)):
    #             #     addr2 = addr + "/" + str(j)
    #             #     bindToDataAndUiPort(
    #             #         addr2,
    #             #         partial(oscreceived_setRenderGainForSourceForRenderer, i, j),
    #             #     )

    #         for addr in [
    #             ("/source/" + str(idx) + "/direct"),
    #             ("/source/" + str(idx) + "/directsend"),
    #             ("/source/" + str(idx) + "/senddirect"),
    #             ("/source/" + str(idx) + "/send/direct"),
    #         ]:
    #             bindToDataAndUiPort(
    #                 addr, partial(oscreceived_setDirectSendForSource, idx)
    #             )

    #             for j in range(globalconfig["number_direct_sends"]):
    #                 addr2 = addr + "/" + str(j)
    #                 bindToDataAndUiPort(
    #                     addr2,
    #                     partial(oscreceived_setDirectSendForSourceForChannel, idx, j),
    #                 )

    if verbosity > 2:
        for add in osc_ui_server.addresses:
            log.info(add)


def bindToDataAndUiPort(addr: str, func):
    # dontUseDataPortFlag = bool(globalconfig['data_port_timeout'] == 0)
    log.debug(f"Adding OSC callback for {addr}")
    addrEnc = addr.encode()

    # if verbosity >= 2:
    osc_ui_server.bind(
        addrEnc, partial(printOSC, addr=addr, port=globalconfig[skc.inputport_ui])
    )
    osc_data_server.bind(
        addrEnc, partial(printOSC, addr=addr, port=globalconfig[skc.inputport_data])
    )

    osc_ui_server.bind(addrEnc, partial(func, fromUi=True))
    osc_data_server.bind(addrEnc, partial(func, fromUi=False))


def sourceLegit(id: int) -> bool:
    indexInRange = id in range(globalconfig["number_sources"])
    if verbosity > 0:
        if not indexInRange:
            if not type(id) == int:
                log.warn("source index is no integer")
            else:
                log.warn("source index out of range")
    return indexInRange


def renderIndexLegit(id: int) -> bool:
    indexInRange = id in range(globalconfig["n_renderengines"])
    if verbosity > 0:
        if not indexInRange:
            if not type(id) == int:
                log.warn("renderengine index is no integer")
            else:
                log.warn("renderengine index out of range")
    return indexInRange


def directSendLegit(id: int) -> bool:
    indexInRange = id in range(globalconfig["number_direct_sends"])
    if verbosity > 0:
        if not indexInRange:
            if not type(id) == int:
                log.warn("direct send index is no integer")
            else:
                log.warn("direct send index out of range")
    return indexInRange


def oscreceived_setPosition(coordKey, *args, fromUi=True):
    sIdx = args[0] - 1
    if sourceLegit(sIdx):
        sIdx = int(sIdx)
        oscreceived_setPositionForSource(coordKey, sIdx, *args[1:], fromUi=fromUi)


def oscreceived_setPositionForSource(coordKey, sIdx: int, *args, fromUi=True):

    if soundobjects[sIdx].setPosition(coordKey, *args, fromUi=fromUi):
        notifyRenderClientsForUpdate("sourcePositionChanged", sIdx, fromUi=fromUi)
        # notifyRendererForSourcePosition(sIdx, fromUi)


# TODO why are there this many functions for doing almost the same thing?
def oscreceived_setRenderGain(*args, fromUi: bool = True):
    sIdx = args[0] - 1
    if sourceLegit(sIdx):
        sIdx = int(sIdx)
        oscreceived_setRenderGainForSource(sIdx, *args[1:], fromUi)


def oscreceived_setRenderGainToRenderer(rIdx: int, *args, fromUi: bool = True):
    sIdx = args[0] - 1
    if renderIndexLegit(rIdx) and sourceLegit(sIdx):
        rIdx = int(rIdx)
        sIdx = int(sIdx)
        oscreceived_setRenderGainForSourceForRenderer(
            sIdx, rIdx, *args[1:], fromUi=fromUi
        )


def oscreceived_setRenderGainForSource(sIdx: int, *args, fromUi: bool = True):
    rIdx = args[0]
    if renderIndexLegit(rIdx):
        rIdx = int(rIdx)
        oscreceived_setRenderGainForSourceForRenderer(
            sIdx, rIdx, *args[1:], fromUi=fromUi
        )


def oscreceived_setRenderGainForSourceForRenderer(
    sIdx: int, rIdx: int, *args, fromUi: bool = True
):

    if soundobjects[sIdx].setRendererGain(rIdx, args[0], fromUi):
        notifyRenderClientsForUpdate(
            "sourceRenderGainChanged", sIdx, rIdx, fromUi=fromUi
        )


def oscreceived_setDirectSend(*args, fromUi: bool = True):
    sIdx = args[0] - 1
    if sourceLegit(sIdx):
        sIdx = int(sIdx)
        oscreceived_setDirectSendForSource(sIdx, *args[1:], fromUi)


def oscreceived_setDirectSendForSource(sIdx: int, *args, fromUi: bool = True):
    cIdx = args[0]
    if directSendLegit(cIdx):  # 0 <= cIdx < globalconfig['number_direct_sends']:
        cIdx = int(cIdx)
        oscreceived_setDirectSendForSourceForChannel(sIdx, cIdx, *args[1:], fromUi)


def oscreceived_setDirectSendForSourceForChannel(
    sIdx: int, cIdx: int, *args, fromUi: bool = True
):
    if soundobjects[sIdx].setDirectSend(cIdx, args[0], fromUi):
        notifyRenderClientsForUpdate(
            "sourceDirectSendChanged", sIdx, cIdx, fromUi=fromUi
        )


# TODO: implement this thing
def notifyRendererForDirectsendGain(sIdx: int, cIfx: int, fromUi: bool = True):
    pass


def oscreceived_setAttribute(*args, fromUi: bool = True):
    sIdx = args[0] - 1
    if sourceLegit(sIdx):
        sIdx = int(sIdx)
        oscreceived_setAttributeForSource(sIdx, *args[1:], fromUi)


def oscreceived_setAttributeForSource(sIdx: int, *args, fromUi: bool = True):
    attribute = args[0]
    if attribute in skc.knownAttributes:
        oscreceived_setValueForSourceForAttribute(sIdx, attribute, *args[1:], fromUi)


def oscReceived_setValueForAttribute(
    attribute: skc.SourceAttributes, *args, fromUi: bool = True
):
    sIdx = args[0] - 1
    if sourceLegit(sIdx):
        sIdx = int(sIdx)
        oscreceived_setValueForSourceForAttribute(sIdx, attribute, *args[1:], fromUi)


def oscreceived_setValueForSourceForAttribute(
    sIdx: int, attribute: skc.SourceAttributes, *args, fromUi: bool = True
):
    if soundobjects[sIdx].setAttribute(attribute, args[0], fromUi):
        notifyRenderClientsForUpdate(
            "sourceAttributeChanged", sIdx, attribute, fromUi=fromUi
        )


def notifyRenderClientsForUpdate(updateFunction: str, *args, fromUi: bool = True):
    for receiver in receivers:
        updatFunc = getattr(receiver, updateFunction)
        updatFunc(*args)

    # XXX why was this distinction made? dataClients were not included in receivers
    # if fromUi:
    #     for rend in dataClients:
    #         updatFunc = getattr(rend, updateFunction)
    #         updatFunc(*args)


######
def oscreceived_sourceAttribute(attribute: skc.SourceAttributes, *args):

    sidx = int(args[0]) - 1
    if sidx >= 0 and sidx < 64:
        oscreceived_sourceAttribute_wString(sidx, attribute, args[1:])


def oscreceived_sourceAttribute_wString(
    sidx: int, attribute: skc.SourceAttributes, *args
):
    sobject = soundobjects[sidx]
    if sobject.setAttribute(attribute, args[0]):
        for ren in receivers:
            ren.sourceAttributeChanged(sidx, attribute)


def printOSC(*args, addr: str = "", port: int = 0):
    if bPrintOSC:
        log.info("incoming OSC on Port", port, addr, args)

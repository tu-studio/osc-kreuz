from numpy import iterable
from osc_kreuz.soundobjectclass import SoundObject
import osc_kreuz.str_keys_conventions as skc
from oscpy.client import OSCClient

from threading import Timer
from functools import partial
from typing import Any, Callable

from collections.abc import Iterable
import logging

log = logging.getLogger("renderer")
verbosity = 0


class RendererException(Exception):
    pass


class Update:
    def __init__(self, callback, args, path):
        pass

    def execute(self):
        pass

    def __eq__(self, __value: object) -> bool:
        # check that callback, path and args are the same, and that the type is right
        return False


class Renderer(object):

    numberOfSources = 64
    sources: list[SoundObject] = []
    globalConfig = {}
    debugCopy: bool = False
    oscDebugClient: OSCClient

    printOutput = verbosity >= 1

    @classmethod
    def createDebugClient(cls, ip, port):
        cls.oscDebugClient = OSCClient(ip, port)

    @classmethod
    def setVerbosity(cls, v: int):
        global verbosity
        verbosity = v
        cls.printOutput = verbosity >= 1

    def __init__(
        self,
        dataformat=skc.xyz,
        updateintervall=10,
        hostname="127.0.0.1",
        hosts: list[dict] | None = None,
        port=4002,
        sourceattributes=(),
        indexAsValue=0,  # XXX unused
    ):
        self.setVerbosity(verbosity)

        self.posFormat = dataformat
        self.validSinglePosKeys = {}
        self.sourceAttributes = sourceattributes

        # check if hosts are defined as an array
        self.hosts: list[tuple[str, int]] = []
        if hosts is None:
            self.hosts.append((hostname, int(port)))
        else:
            for host in hosts:
                try:
                    host_tuple = (host["hostname"], host["port"])
                    self.hosts.append(host_tuple)
                except KeyError:
                    raise RendererException("Invalid Host")

        self.updateIntervall = int(updateintervall) / 1000

        self.source_needs_update: list[bool] = [False] * self.numberOfSources
        self.source_getting_update: list[bool] = [False] * self.numberOfSources

        # update stack contains sets of tuples of functions and osc_paths
        # sets are used, so each source is updated only once during the update process
        self.updateStack: list[set[tuple[Callable, bytes]]] = [
            set() for _ in range(self.numberOfSources)
        ]

        self.debugPrefix = "/genericRenderer"
        self.oscPre = ("/source/" + self.posFormat).encode()

        self.receivers: list[OSCClient] = []
        for ip, port in self.hosts:
            self.receivers.append(OSCClient(ip, port, encoding="utf8"))

        self.isDataClient = False

        self.printRenderInformation()

    def printRenderInformation(self, print_pos_format=True):
        log.info(f"Initialized renderer {self.myType()}")
        hosts_str = ", ".join([f"{hostname}:{port}" for hostname, port in self.hosts])
        log.info(f"\thosts: {hosts_str}")
        if print_pos_format:
            log.info(f"\tlistening to format {self.posFormat}")

    def myType(self) -> str:
        return "basic Rendererclass: abstract class, doesnt listen"

    def addDestination(self, ip: str, port: int):
        self.receivers.append(OSCClient(ip, port, encoding="utf8"))

        log.debug(self.myType(), "added destination", ip, str(port))

    def composeSourceUpdateMessage(
        self, values, sIdx: int = 0, *args
    ) -> list[tuple[bytes, Iterable]]:
        return [(args[0], values)]

    def sourceChanged(self, source_idx):
        if not self.source_getting_update[source_idx]:
            self.updateSource(source_idx)
        else:
            self.source_needs_update[source_idx] = True

    def updateSource(self, source_idx):
        """Builds and sends source update messages

        Args:
            source_idx (int): index of source to be updated
        """
        while self.updateStack[source_idx]:
            getValueFunc, oscPre = self.updateStack[source_idx].pop()
            values = getValueFunc()

            msgs = self.composeSourceUpdateMessage(values, source_idx, *oscPre)
            self.sendUpdates(msgs)

        self.scheduleSourceUpdateCheck(source_idx)

    def sendUpdates(self, msgs):
        """This function sends all messages to the osc clients

        Args:
            msgs (list(list)): list of messages
        """
        for msg in msgs:
            for receiversClient in self.receivers:
                try:
                    oscArgs = msg[1]
                    receiversClient.send_message(msg[0], oscArgs)

                except Exception as e:
                    log.warn(f"Exception while sending: {e}")
                    pass

                if self.debugCopy:
                    debugOsc = (
                        self.debugPrefix
                        + "/"
                        + receiversClient.address
                        + ":"
                        + str(receiversClient.port)
                        + msg[0].decode()
                    ).encode()
                    try:
                        self.oscDebugClient.send_message(debugOsc, msg[1])
                    except:
                        pass

            if self.printOutput:
                self.printOscOutput(msg[0], msg[1])

    def scheduleSourceUpdateCheck(self, source_idx):
        self.source_needs_update[source_idx] = False
        self.source_getting_update[source_idx] = True
        Timer(
            self.updateIntervall, partial(self.check_sourceNeedsUpdate, source_idx)
        ).start()

    def check_sourceNeedsUpdate(self, source_idx):
        self.source_getting_update[source_idx] = False
        if self.source_needs_update[source_idx]:
            self.updateSource(source_idx)

    # implement this functions in subclasses for registering for specific updates
    def sourceAttributeChanged(self, source_idx, attribute):
        pass

    def sourceRenderGainChanged(self, source_idx, render_idx):
        pass

    def sourceDirectSendChanged(self, source_idx, send_idx):
        pass

    def sourcePositionChanged(self, source_idx):
        pass

    def oscDebugSend(self, oscStr, data: list):
        decStr = oscStr.decode()
        newOscAddr = self.debugPrefix + decStr
        self.oscDebugClient.send_message(newOscAddr.encode(), data)

    def printOscOutput(self, oscStr, data: list):
        decStr = oscStr.decode()
        log.debug("OSC out", self.debugPrefix, decStr, data)


class SpatialRenderer(Renderer):
    def myType(self) -> str:
        return "Generic Spatial Renderer"

    def sourcePositionChanged(self, source_idx):
        self.updateStack[source_idx].add(
            (
                partial(self.sources[source_idx].getPosition, self.posFormat),
                (self.oscPre,),
            )
        )
        self.sourceChanged(source_idx)

    def composeSourceUpdateMessage(
        self, values, sIdx: int = 0, *args
    ) -> list[tuple[bytes, Iterable]]:
        return [(args[0], *values)]


class Wonder(SpatialRenderer):
    def __init__(self, **kwargs):
        if not "dataformat" in kwargs.keys():
            kwargs["dataformat"] = skc.xy
        if not "sourceattributes" in kwargs.keys():
            kwargs["sourceattributes"] = (
                skc.SourceAttributes.doppler,
                skc.SourceAttributes.planewave,
            )
        super(Wonder, self).__init__(**kwargs)

        self.attributeOsc = {
            skc.SourceAttributes.doppler: b"/WONDER/source/dopplerEffect",
            skc.SourceAttributes.planewave: b"/WONDER/source/type",
            skc.SourceAttributes.angle: b"/WONDER/source/angle",
        }
        self.oscPre = b"/WONDER/source/position"
        self.oscAnglePref = b"/WONDER/source/angle"

        self.interpolTime = self.updateIntervall
        self.linkPositionAndAngle = True

        self.debugPrefix = "/dWonder"

    def myType(self) -> str:
        return "Wonder"

    def sourceAttributeChanged(self, source_idx, attribute):
        self.updateStack[source_idx].add(
            (
                partial(self.sources[source_idx].getAttribute, attribute),
                (self.attributeOsc[attribute],),
            )
        )
        self.sourceChanged(source_idx)

    def composeSourceUpdateMessage(
        self, values, sIdx: int = 0, *args
    ) -> list[tuple[bytes, Iterable]]:
        osc_pre = args[0]
        wonderOscMap = {
            b"/WONDER/source/position": self.wonderPositionValues,
            b"/WONDER/source/angle": self.wonderAngleValues,
            b"/WONDER/source/dopplerEffect": self.wonderDopplerValues,
            b"/WONDER/source/type": self.wonderPlanewave,
        }

        send_values = wonderOscMap[osc_pre](sIdx, values)

        return [(osc_pre, send_values)]

    def wonderPositionValues(self, sIdx: int, values) -> list:
        if self.linkPositionAndAngle and self.sources[sIdx].getAttribute(
            skc.SourceAttributes.planewave
        ):
            self.addUpdateAngleToStack(sIdx)
        return [sIdx, *values, self.interpolTime]

    def wonderAngleValues(self, sIdx, values) -> list:
        # TODO: Umrechnen
        return [sIdx, values, self.interpolTime]

    def wonderDopplerValues(self, sIdx, value) -> list:
        return [sIdx, value]

    def wonderPlanewave(self, sIdx, value) -> list:
        if value:
            self.addUpdateAngleToStack(sIdx)
        return [sIdx, int(not value)]

    def addUpdateAngleToStack(self, sIdx: int):
        self.updateStack[sIdx].add(
            (partial(self.sources[sIdx].getPosition, skc.azim), (self.oscAnglePref,))
        )


class Audiorouter(Renderer):
    #
    def __init__(self, **kwargs):
        super(Audiorouter, self).__init__(**kwargs)

        self.debugPrefix = "/dAudiorouter"
        self.oscpre_renderGain = b"/source/send/spatial"
        self.oscpre_reverbGain = b"/source/reverb/gain"
        self.oscpre_directSend = b"/source/send/direct"

    def printRenderInformation(self, print_pos_format=False):
        super().printRenderInformation(print_pos_format=False)

    def myType(self) -> str:
        return "Audiorouter"

    def composeSourceUpdateMessage(
        self, values, sIdx: int = 0, *args
    ) -> list[tuple[bytes, Iterable]]:
        osc_pre = args[0]

        if osc_pre == self.oscpre_reverbGain:
            return [(osc_pre, [sIdx, values])]
        else:
            cIdx = args[1]
            return [(osc_pre, [sIdx, cIdx, values])]

    # TODO: better solution putting a tuple of three values in there?
    def sourceDirectSendChanged(self, source_idx, send_idx):
        self.updateStack[source_idx].add(
            (
                partial(self.sources[source_idx].getDirectSend, send_idx),
                (self.oscpre_directSend, send_idx),
            )
        )
        self.sourceChanged(source_idx)

    def sourceRenderGainChanged(self, source_idx, render_idx):
        if not render_idx == 1:
            if render_idx == 2:
                self.updateStack[source_idx].add(
                    (
                        partial(self.sources[source_idx].getRenderGain, render_idx),
                        (self.oscpre_reverbGain, render_idx),
                    )
                )
            else:
                self.updateStack[source_idx].add(
                    (
                        partial(self.sources[source_idx].getRenderGain, render_idx),
                        (self.oscpre_renderGain, render_idx),
                    )
                )
            self.sourceChanged(source_idx)


class AudiorouterWFS(Audiorouter):
    def __init__(self, **kwargs):
        super(AudiorouterWFS, self).__init__(**kwargs)
        self.debugPrefix = "/dAudiorouterWFS"

    def sourceRenderGainChanged(self, source_idx, render_idx):
        if render_idx == 1:
            self.updateStack[source_idx].add(
                (
                    partial(self.sources[source_idx].getRenderGain, render_idx),
                    (self.oscpre_renderGain, render_idx),
                )
            )
            self.sourceChanged(source_idx)

    def myType(self) -> str:
        return "Audiorouter-WFS"


class AudioMatrix(Renderer):
    def __init__(self, paths: Iterable[dict["str", Any]], **kwargs):
        super().__init__(**kwargs)
        self.debugPrefix = "/dAudioMatrix"
        self.gain_paths: dict[int, list[bytes]] = {}
        self.pos_paths: list[tuple[bytes, str]] = []

        # this dict is used to translate between render unit index and render unit name
        self.render_unit_indices = {}

        # prepare gain path with all render unit indices
        for index, render_unit in enumerate(self.globalConfig["render_units"]):
            self.render_unit_indices[index] = render_unit
            self.render_unit_indices[render_unit] = index
            self.gain_paths[index] = []

        for path in paths:
            osc_path: str = path["path"]
            path_type = path["type"]

            if path_type == "gain":
                renderer = path["renderer"]
                renderer_index = self.render_unit_indices[renderer]
                self.gain_paths[renderer_index].append(osc_path.encode())
            elif path_type in ["position", "pos"]:
                try:
                    coord_fmt = skc.CoordFormats(path["format"]).value
                except:
                    coord_fmt = skc.CoordFormats("xyz").value
                self.pos_paths.append((osc_path.encode(), coord_fmt))

        log.debug("Audio Matrix initialized")

    def myType(self) -> str:
        return "AudioMatrix"

    def composeSourceUpdateMessage(
        self, values, sIdx: int = 0, *args
    ) -> list[tuple[bytes, Iterable]]:
        osc_pre = args[0]
        if not iterable(values):
            values = [values]
        return [(osc_pre, [sIdx, *values])]

    def sourceRenderGainChanged(self, source_idx, render_idx):
        log.info(f"source gain changed: {source_idx}, {render_idx}")
        if render_idx in self.gain_paths:
            for path in self.gain_paths[render_idx]:
                self.updateStack[source_idx].add(
                    (
                        partial(self.sources[source_idx].getRenderGain, render_idx),
                        (path,),
                    )
                )
                self.sourceChanged(source_idx)

    def sourcePositionChanged(self, source_idx):
        log.info(f"source position update {source_idx}")
        for path, coord_fmt in self.pos_paths:
            self.updateStack[source_idx].add(
                (
                    (
                        partial(self.sources[source_idx].getPosition, coord_fmt),
                        (path,),
                    )
                )
            )
            self.sourceChanged(source_idx)


class Panoramix(SpatialRenderer):
    def __init__(self, **kwargs):
        if not "dataformat" in kwargs.keys():
            kwargs["dataformat"] = skc.xyz
        super(Panoramix, self).__init__(**kwargs)

        self.posAddrs = []
        for i in range(self.numberOfSources):
            self.posAddrs.append(("/track/" + str(i + 1) + "/xyz").encode())

        self.debugPrefix = "/dPanoramix"

    def myType(self) -> str:
        return "Panoramix CAREFUL NOT REALLY IMPLEMENTED"

    def composeSourceUpdateMessage(
        self, values, sIdx: int = 0, *args
    ) -> list[tuple[bytes, Iterable]]:
        # msgs = []
        sobject = self.sources[sIdx]
        position = sobject.getPosition(self.posFormat)
        # sourceID = source_idx + 1
        addr = self.posAddrs[sIdx]

        return [(addr, position)]


class IemMultiencoder(SpatialRenderer):
    def __init__(self, **kwargs):
        if not "dataformat" in kwargs.keys():
            kwargs["dataformat"] = skc.ae
        # kwargs[skc.posformat] = skc.aed
        super(IemMultiencoder, self).__init__(**kwargs)

        self.posAddrs: list = []
        for i in range(self.numberOfSources):
            for kk in skc.posformat[self.posFormat][1]:
                # TODO: Check if the right strings
                addrstr = "/MultiEncoder/" + str(i) + skc.fullnames[kk]
                self.posAddrs.append(addrstr)

        self.debugPrefix = "/dIEM"

    def myType(self) -> str:
        return "IEM Multiencoder, NOT IMPLEMENTED"

    def composeSourceUpdateMessage(
        self, values, sIdx: int = 0, *args
    ) -> list[tuple[bytes, Iterable]]:
        return []


class SuperColliderEngine(SpatialRenderer):
    def __init__(self, **kwargs):
        if not "dataformat" in kwargs.keys():
            kwargs["dataformat"] = skc.aed
        super(SuperColliderEngine, self).__init__(**kwargs)

        self.oscPre = b"/source/pos/aed"
        self.singleValKeys = {
            skc.azim: b"/source/pos/azim",
            skc.dist: b"/source/pos/dist",
            skc.elev: b"/source/pos/elev",
        }
        self.validPosKeys = {skc.azim, skc.dist, skc.elev}

        self.debugPrefix = "/dSuperCollider"

    def composeSourceUpdateMessage(
        self, values, sIdx: int = 0, *args
    ) -> list[tuple[bytes, Iterable]]:
        osc_pre = args[0]
        return [(osc_pre, [sIdx, *values])]
        # sobject = self.sources[source_idx]
        # singleUpdate = sobject.getSingleValueUpdate(self.validPosKeys)
        # if singleUpdate:
        #     return [(self.singleValKeys[singleUpdate[0]]), [singleUpdate[1]]]
        #
        # else:
        #     position = sobject.getPosition(self.posFormat)
        #     return [(self.addrstr, [source_idx + 1, *position])]

    def myType(self) -> str:
        return "Supercolliderengine"


class ViewClient(SpatialRenderer):
    def myType(self) -> str:
        return "viewClient: {}".format(self.alias)

    def __init__(self, aliasname, **kwargs):
        self.alias = aliasname

        super(ViewClient, self).__init__(**kwargs)

        self.pingCounter = 0

        self.debugPrefix = "/d{}".format(aliasname.decode())
        # self.biAlias = b''
        # self.setAlias(aliasname)

        self.indexAsValue = False
        if "indexAsValue" in kwargs.keys():
            self.indexAsValue = kwargs["indexAsValue"]

        self.idxSourceOscPrePos = [b""] * self.numberOfSources
        self.idxSourceOscPreAttri = [{}] * self.numberOfSources
        self.idxSourceOscPreRender = [[]] * self.numberOfSources

        self.createOscPrefixes()

        # self.idxSourceOscPreAttri

        self.pingTimer: Timer | None = None

    def createOscPrefixes(self):
        for i in range(self.numberOfSources):
            self.idxSourceOscPrePos[i] = "/source/{}/{}".format(
                i + 1, self.posFormat
            ).encode()
            _aDic = {}
            for attr in skc.knownAttributes:
                _aDic[attr] = "/source/{}/{}".format(i + 1, attr).encode()

            self.idxSourceOscPreAttri[i] = _aDic

            try:
                render_units = self.globalConfig["render_units"]
            except KeyError:
                render_units = []

            renderList = [b""] * self.globalConfig["n_renderengines"]
            if (
                "ambi" in render_units
                and "wfs" in render_units
                and "reverb" in render_units
            ):
                renderList[render_units.index("ambi")] = "/source/{}/ambi".format(
                    i + 1
                ).encode()
                renderList[render_units.index("wfs")] = "/source/{}/wfs".format(
                    i + 1
                ).encode()
                renderList[render_units.index("reverb")] = "/source/{}/reverb".format(
                    i + 1
                ).encode()
            else:
                for j in range(self.globalConfig["number_renderunits"]):
                    self.idxSourceOscPreRender[i][j] = "/source/{}/send/{}".format(
                        i + 1, j
                    ).encode()
            self.idxSourceOscPreRender[i] = renderList

    def checkAlive(self, deleteClient):
        self.pingTimer = Timer(2.0, partial(self.checkAlive, deleteClient))

        if self.pingCounter < 6:
            # self.receivers[0].send_message(b'/oscrouter/ping', [self.globalConfig['inputport_settings']])
            try:
                self.receivers[0].send_message(
                    b"/oscrouter/ping", [self.globalConfig["inputport_settings"]]
                )  # , self.alias
            except:
                log.warn("error while pinging client ", self.alias, ", removing")
                self.pingTimer.cancel()
                deleteClient(self, self.alias)

            self.pingCounter += 1
            self.pingTimer.start()
        else:
            deleteClient(self, self.alias)

    def receivedIsAlive(self):
        self.pingCounter = 0

    def sourcePositionChanged(self, source_idx):
        if self.indexAsValue:
            self.updateStack[source_idx].add(
                (
                    partial(self.sources[source_idx].getPosition, self.posFormat),
                    (self.idxSourceOscPrePos[source_idx],),
                )
            )
        else:
            self.updateStack[source_idx].add(
                (
                    partial(self.sources[source_idx].getPosition, self.posFormat),
                    (self.oscPre,),
                )
            )
        self.sourceChanged(source_idx)

    def sourceRenderGainChanged(self, source_idx, render_idx):
        self.updateStack[source_idx].add(
            (
                partial(self.sources[source_idx].getRenderGain, render_idx),
                (self.idxSourceOscPreRender[source_idx][render_idx],),
            )
        )
        self.sourceChanged(source_idx)

    def composeSourceUpdateMessage(
        self, values, sIdx: int = 0, *args
    ) -> list[tuple[bytes, Iterable]]:
        if isinstance(values, Iterable):
            return [(args[0], values)]
        else:
            return [(args[0], [values])]


class Oscar(SpatialRenderer):
    def __init__(self, **kwargs):
        if not "dataformat" in kwargs.keys():
            kwargs["dataformat"] = skc.aed
        super(Oscar, self).__init__(**kwargs)

        self.sourceAttributes = (
            skc.SourceAttributes.doppler,
            skc.SourceAttributes.planewave,
        )

        # self.posAddrs = []

        self.oscPosPre = []
        self.oscAttrPre = []
        self.oscRenderPre = []
        self.oscDirectPre = []

        # self.oscAttributeOscPre = {
        #     skc.SourceAttributes.doppler: [],
        #     skc.SourceAttributes.planewave: []
        # }

        for i in range(self.numberOfSources):
            sourceAddrs = {}
            for kk in skc.fullformat[self.posFormat]:
                addrStr = "/source/" + str(i + 1) + "/" + kk
                sourceAddrs[kk] = addrStr.encode()
            self.oscPosPre.append(sourceAddrs)

            attrDic = {}
            for key in self.sourceAttributes:
                oscStr = "/source" + str(i + 1) + "/" + key.value
                attrDic[key] = oscStr.encode()
            self.oscAttrPre.append(attrDic)

            renderGainOscs = []
            for rId in range(self.globalConfig["n_renderengines"]):
                riOsc = "/source/" + str(i + 1) + "/render/" + str(rId)
                renderGainOscs.append(riOsc.encode())
            self.oscRenderPre.append(renderGainOscs)

            channelSend = []
            for cId in range(self.globalConfig["number_direct_sends"]):
                csOsc = "/source/" + str(i + 1) + "/direct/" + str(cId)
                channelSend.append(csOsc.encode())
            self.oscDirectPre.append(channelSend)

            # self.posAddrs.append(sourceAddrs)

        self.validPosKeys = {skc.dist}

        self.isDataClient = True

        self.debugPrefix = "/dOscar"

    def myType(self) -> str:
        return "Oscar"

    def sourcePositionChanged(self, source_idx):
        for key in skc.fullformat[self.posFormat]:
            self.updateStack[source_idx].add(
                (
                    partial(self.sources[source_idx].getPosition, key),
                    (self.oscPosPre[source_idx][key],),
                )
            )
            self.sourceChanged(source_idx)

    def sourceAttributeChanged(self, source_idx, attribute):
        self.updateStack[source_idx].add(
            (
                partial(self.sources[source_idx].getAttribute[attribute]),
                (self.oscAttrPre[source_idx][attribute],),
            )
        )
        self.sourceChanged(source_idx)

    def sourceDirectSendChanged(self, source_idx, send_idx):
        self.updateStack[source_idx].add(
            (
                partial(self.sources[source_idx].getDirectSend, send_idx),
                (self.oscDirectPre[source_idx][send_idx],),
            )
        )
        self.sourceChanged(source_idx)

    def sourceRenderGainChanged(self, source_idx, render_idx):
        self.updateStack[source_idx].add(
            (
                partial(self.sources[source_idx].getRenderGain, render_idx),
                (self.oscRenderPre[source_idx][render_idx],),
            )
        )
        self.sourceChanged(source_idx)

    def composeSourceUpdateMessage(
        self, values, sIdx: int = 0, *args
    ) -> list[tuple[bytes, Iterable]]:
        osc_pre = args[0]
        return [(osc_pre, [values])]


class SeamlessPlugin(SpatialRenderer):
    def myType(self) -> str:
        return "Seamless Plugin"

    def __init__(self, **kwargs):
        if not "dataformat" in kwargs.keys():
            kwargs["dataformat"] = skc.xyz
        super(SeamlessPlugin, self).__init__(**kwargs)

        self.sourceAttributes = (
            skc.SourceAttributes.doppler,
            skc.SourceAttributes.planewave,
        )

        self.oscAddrs: dict = {}

        for key in skc.fullformat[self.posFormat]:
            self.oscAddrs[key] = "/source/pos/{}".format(key).encode()

        for vv in self.sourceAttributes:
            self.oscAddrs[vv.value] = "/{}".format(vv.value).encode()

        self.oscAddrs["renderGain"] = "/send/gain".encode()

        self.debugPrefix = "/dSeamlessPlugin"

    def composeSourceUpdateMessage(
        self, values, sIdx: int = 0, *args
    ) -> list[tuple[bytes, Iterable]]:
        osc_pre = args[0]
        if osc_pre == self.oscAddrs["renderGain"]:
            return [(osc_pre, [sIdx + 1, args[1], values])]
        else:
            return [(osc_pre, [sIdx + 1, values])]

    def sourceAttributeChanged(self, source_idx, attribute):
        pass

    def sourceRenderGainChanged(self, source_idx, render_idx):
        self.updateStack[source_idx].add(
            (
                partial(self.sources[source_idx].getRenderGain, render_idx),
                (self.oscAddrs["renderGain"], render_idx),
            )
        )
        self.sourceChanged(source_idx)

    def sourcePositionChanged(self, source_idx):
        for key in skc.fullformat[self.posFormat]:
            self.updateStack[source_idx].add(
                (
                    partial(self.sources[source_idx].getPosition, key),
                    (self.oscAddrs[key],),
                )
            )

        self.sourceChanged(source_idx)


class DataClient(Audiorouter, SpatialRenderer):
    pass


renderer_name_dict = {
    "wonder": Wonder,
    "panoramix": Panoramix,
    "iemmultiencoder": IemMultiencoder,
    "viewclient": ViewClient,
    "oscar": Oscar,
    "scengine": SuperColliderEngine,
    "audiorouter": Audiorouter,
    "seamlessplugin": SeamlessPlugin,
    "audiorouterwfs": AudiorouterWFS,
    "audiomatrix": AudioMatrix,
}


def createRendererClient(config: dict) -> Renderer:

    # XXX some weird shit is happening here
    if "dataformat" in config:
        tmp_dataFormat = config["dataformat"]
        if not tmp_dataFormat in skc.posformat.keys():
            if len(tmp_dataFormat.split("_")) == 2:
                preStr = ""
                if tmp_dataFormat.split("_")[0] == "normcartesian":
                    preStr = "n"

                dFo = preStr + tmp_dataFormat.split("_")[1]
                config["dataformat"] = dFo
            else:
                log.warn("unknown position format")
                del config["dataformat"]

    if "type" not in config:
        raise RendererException("Type of receiver unspecified")

    renderer_type = config["type"].lower()
    del config["type"]

    if renderer_type not in renderer_name_dict:
        raise RendererException(f"Invalid receiver type: {renderer_type}")

    return renderer_name_dict[renderer_type](**config)

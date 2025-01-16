from collections.abc import Iterable
from functools import partial
import logging
from threading import Event, Timer
from time import time
from typing import Any

from numpy import iterable
from oscpy.client import OSCClient

from osc_kreuz.config import read_config_option
from osc_kreuz.soundobject import SoundObject
import osc_kreuz.str_keys_conventions as skc

log = logging.getLogger("renderer")
verbosity = 0


class RendererException(Exception):
    pass


class Message:
    def __init__(self, path: bytes, values: Any) -> None:
        self.path = path
        if isinstance(values, str) or not iterable(values):
            values = [values]
        self.values: Iterable[Any] = values


class Update:
    """Base Class for an Update sent via OSC. Updates with specific requirements should inherit from this one"""

    def __init__(
        self,
        path: bytes,
        soundobject: SoundObject,
        source_index: int | None = None,
        pre_arg: Any = None,
        post_arg: Any = None,
    ):
        """Construct a new Update.
        The values of the Message created out of this Update will look like this, values in <brackets> are optional:
        [<source_index>, <pre_arg>, value, <**values>,..., <post_arg>]


        Args:
            path (bytes): OSC Path this update should be sent to
            soundobject (SoundObject): the Soundobject this Update belongs to, usually the get_value() function needs this
            source_index (int | None, optional): source index of this Soundobject. Needed when the source index . Defaults to None.
            pre_arg (Any, optional): argument that should be added to OSC Message before the actual values. Defaults to None.
            post_arg (Any, optional): argument that should be added to OSC Message at the end. Defaults to None.
        """
        self.soundobject = soundobject
        self.pre_arg = pre_arg
        self.post_arg = post_arg
        self.path = path
        self.source_index = source_index

    def get_value(self):
        """Override this function!

        Raises:
            NotImplementedError: Seemds like you didn't override this function!
        """
        raise NotImplementedError

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return (
                isinstance(other, self.__class__)
                and self.source_index == other.source_index
                and self.path == other.path
            )
        return False

    def __hash__(self):
        """for use with sets"""
        return hash(tuple(sorted(self.__dict__.items())))

    def to_message(self) -> Message:
        values = []

        # add source index to list if it exists
        if self.source_index is not None:
            values.append(self.source_index)

        # sometimes needed as first argument
        if self.pre_arg is not None:
            values.append(self.pre_arg)

        # add value or values returned by the callback to the list
        ret_value = self.get_value()
        if isinstance(ret_value, str) or not iterable(ret_value):
            values.append(ret_value)
        else:
            values.extend(ret_value)

        # sometimes needed as a last argument
        if self.post_arg is not None:
            values.append(self.post_arg)

        return Message(self.path, values)


class PositionUpdate(Update):
    def __init__(
        self,
        path: bytes,
        soundobject: SoundObject,
        coord_fmt: str,
        source_index: int | None = None,
        pre_arg: Any = None,
        post_arg: Any = None,
    ):
        super().__init__(path, soundobject, source_index, pre_arg, post_arg)
        self.coord_fmt = coord_fmt

    def get_value(self):
        return self.soundobject.getPosition(self.coord_fmt)


class GainUpdate(Update):
    def __init__(
        self,
        path: bytes,
        soundobject: SoundObject,
        render_idx: int,
        source_index: int | None = None,
        pre_arg: Any = None,
        post_arg: Any = None,
        include_render_idx=False,
    ):
        super().__init__(path, soundobject, source_index, pre_arg, post_arg)
        self.render_idx = render_idx
        if include_render_idx:
            self.pre_arg = render_idx

    def get_value(self):
        return self.soundobject.getRenderGain(self.render_idx)


class DirectSendUpdate(Update):
    def __init__(
        self,
        path: bytes,
        soundobject: SoundObject,
        send_index: int,
        source_index: int | None = None,
        include_send_idx=False,
        pre_arg: Any = None,
        post_arg: Any = None,
    ):
        super().__init__(path, soundobject, source_index, pre_arg, post_arg)
        self.send_index = send_index
        if include_send_idx:
            self.pre_arg = send_index

    def get_value(self):
        return self.soundobject.getDirectSend(self.send_index)


class AttributeUpdate(Update):
    def __init__(
        self,
        path: bytes,
        attribute: skc.SourceAttributes,
        soundobject: SoundObject,
        source_index: int | None = None,
        include_attribute_name=False,
        pre_arg: Any = None,
        post_arg: Any = None,
    ):
        super().__init__(path, soundobject, source_index, pre_arg, post_arg)
        self.attribute = attribute
        if include_attribute_name:
            self.pre_arg = attribute.value

    def get_value(self):
        return self.soundobject.getAttribute(self.attribute)


class wonderPlanewaveAttributeUpdate(AttributeUpdate):
    def get_value(self):
        # for the planewave attribute, the value has to be inverted
        return int(not super().get_value())


class Renderer(object):

    numberOfSources = 64
    sources: list[SoundObject] = []
    globalConfig: dict = {}
    debugCopy: bool = False
    oscDebugClient: OSCClient

    printOutput = verbosity >= 1

    @classmethod
    def createDebugClient(cls, ip: str, port: int) -> None:
        cls.oscDebugClient = OSCClient(ip, port)

    @classmethod
    def setVerbosity(cls, v: int):
        global verbosity
        verbosity = v
        cls.printOutput = verbosity >= 1

    def __init__(
        self,
        dataformat: str = "xyz",
        updateintervall=10,
        hostname: str | None = None,
        hosts: list[dict] | None = None,
        port: int | None = None,
        sourceattributes=(),
        indexAsValue=0,  # XXX unused
    ):
        self.setVerbosity(verbosity)

        self.posFormat = dataformat
        self.sourceAttributes = sourceattributes

        self.hosts: list[tuple[str, int]] = []
        self.receivers: list[OSCClient] = []

        # check if hosts are defined as an array
        if hostname is not None and port is not None:
            self.add_receiver(hostname, int(port))
        if hosts is not None:
            for host in hosts:
                try:
                    self.add_receiver(host["hostname"], host["port"])
                except KeyError:
                    raise RendererException("Invalid Host")

        if len(self.hosts) == 0:
            log.warning(f"Renderer of type {self.my_type()} has no receivers")

        # convert update interval from ms to s
        self.update_interval = int(updateintervall) / 1000

        # init update semaphore for all sources
        self.source_getting_update: list[Event] = [
            Event() for _ in range(self.numberOfSources)
        ]

        # sets are used in update stack, so each source is updated only once during the update process
        self.update_stack: list[set[Update]] = [
            set() for _ in range(self.numberOfSources)
        ]
        # second update Stack that is swapped in during updates
        self.update_stack_swap: list[set[Update]] = [
            set() for _ in range(self.numberOfSources)
        ]

        self.debugPrefix = "/genericRenderer"
        self.oscPre = ("/source/" + self.posFormat).encode()

        self.isDataClient = False

        self.print_self_information()

    def print_self_information(self, print_pos_format=True):
        log.info(f"Initialized renderer {self.my_type()}")
        hosts_str = ", ".join([f"{hostname}:{port}" for hostname, port in self.hosts])
        log.info(f"\thosts: {hosts_str}")
        if print_pos_format:
            log.info(f"\tlistening to format {self.posFormat}")

    def my_type(self) -> str:
        return "basic Rendererclass: abstract class, doesnt listen"

    def add_receiver(self, hostname: str, port: int):
        self.hosts.append((hostname, port))
        self.receivers.append(OSCClient(hostname, port, encoding="utf8"))

    def add_update(self, source_idx: int, update: Update) -> None:
        self.update_stack[source_idx].add(update)
        self.update_source(source_idx)

    def update_source(self, source_idx) -> None:
        """Builds and sends source update messages

        Args:
            source_idx (int): index of source to be updated
        """
        # if an update is already in progress simply return
        if self.source_getting_update[source_idx].is_set():
            return
        time_start = time()
        self.source_getting_update[source_idx].set()

        # swap stacks so the stack we are working on isn't written to
        self.update_stack[source_idx], self.update_stack_swap[source_idx] = (
            self.update_stack_swap[source_idx],
            self.update_stack[source_idx],
        )

        # get messages from updates
        msgs = []
        while self.update_stack_swap[source_idx]:
            update: Update = self.update_stack_swap[source_idx].pop()
            msg = update.to_message()
            msgs.append(msg)

        self.send_updates(msgs)

        # schedule releasing of update lock
        Timer(
            self.update_interval - (time() - time_start),
            self.release_source_update_lock,
            args=(source_idx,),
        ).start()

    def send_updates(self, msgs, hostname: str | None = None, port: int | None = None):
        """This function sends all messages to the osc clients

        Args:
            msgs (list(list)): list of messages
        """
        for msg in msgs:
            for receiver in self.receivers:

                # if explicit hostname and port are specified skip all receivers that don't match
                if hostname is not None and port is not None:
                    if receiver.address != hostname and receiver.port != port:
                        continue

                try:
                    start_time = time()
                    receiver.send_message(msg.path, msg.values, safer=True)
                    send_time = (time() - start_time) * 1000
                    if send_time > 10:
                        log.warning(
                            f"sending osc update {msg.path} to {receiver.address} took way too long: {send_time}"
                        )
                except Exception as e:
                    log.exception(
                        f"Exception while sending to {receiver.address}:{receiver.port}",
                        exc_info=e,
                    )

                if self.debugCopy:
                    debugOsc = (
                        f"{self.debugPrefix}/{receiver.address}:{receiver.port}{msg.path.decode()}"
                    ).encode()
                    try:
                        self.oscDebugClient.send_message(debugOsc, msg.values)
                    except Exception:
                        pass

            if self.printOutput:
                self.printOscOutput(msg.path, msg.values)

    def release_source_update_lock(self, source_idx):
        self.source_getting_update[source_idx].clear()
        if len(self.update_stack[source_idx]) > 0:
            self.update_source(source_idx)

    # implement these functions in subclasses for registering for specific updates
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
    def my_type(self) -> str:
        return "Generic Spatial Renderer"

    def sourcePositionChanged(self, source_idx):
        self.add_update(
            source_idx,
            PositionUpdate(
                path=self.oscPre,
                soundobject=self.sources[source_idx],
                coord_fmt=self.posFormat,
                source_index=source_idx,
            ),
        )


class Wonder(SpatialRenderer):
    def __init__(self, **kwargs):
        if "dataformat" not in kwargs:
            kwargs["dataformat"] = "xy"
        if "sourceattributes" not in kwargs:
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

        self.interpolTime = self.update_interval * 0.9
        self.linkPositionAndAngle = True

        self.debugPrefix = "/dWonder"

    def my_type(self) -> str:
        return "Wonder"

    def sourcePositionChanged(self, source_idx):
        # Add position Update to update stack
        self.add_update(
            source_idx,
            PositionUpdate(
                path=self.oscPre,
                soundobject=self.sources[source_idx],
                coord_fmt=self.posFormat,
                source_index=source_idx,
                post_arg=self.interpolTime,
            ),
        )

        # optionally update angle if the wave is planar
        if self.linkPositionAndAngle and self.sources[source_idx].getAttribute(
            skc.SourceAttributes.planewave
        ):
            self.sourceAttributeChanged(source_idx, skc.SourceAttributes.angle)

    def sourceAttributeChanged(self, source_idx, attribute: skc.SourceAttributes):
        if attribute == skc.SourceAttributes.planewave:
            # planewave has special update type
            self.add_update(
                source_idx,
                wonderPlanewaveAttributeUpdate(
                    path=self.attributeOsc[attribute],
                    soundobject=self.sources[source_idx],
                    source_index=source_idx,
                    attribute=attribute,
                ),
            )

            if self.sources[source_idx].getAttribute(attribute):
                self.update_auto_angle(source_idx)
        elif attribute == skc.SourceAttributes.angle:
            # angle needs interpolation time as additional param
            self.add_update(
                source_idx,
                AttributeUpdate(
                    path=self.attributeOsc[attribute],
                    soundobject=self.sources[source_idx],
                    source_index=source_idx,
                    attribute=attribute,
                    post_arg=self.interpolTime,
                ),
            )
        else:
            self.add_update(
                source_idx,
                AttributeUpdate(
                    path=self.attributeOsc[attribute],
                    soundobject=self.sources[source_idx],
                    source_index=source_idx,
                    attribute=attribute,
                ),
            )

    def update_auto_angle(self, source_idx: int):
        # TODO take into account the user specified angle
        self.add_update(
            source_idx,
            PositionUpdate(
                path=self.attributeOsc[skc.SourceAttributes.angle],
                soundobject=self.sources[source_idx],
                source_index=source_idx,
                coord_fmt="azim",
                post_arg=self.interpolTime,
            ),
        )


class TWonder(Wonder):
    oscpath_n_sources = b"/WONDER/global/maxNoSources"
    oscpath_room_polygon = b"/WONDER/global/renderpolygon"
    oscpath_activate_source = b"/WONDER/source/activate"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.interpolTime = self.update_interval
        self.linkPositionAndAngle = True

        self.debugPrefix = "/dTWonder"

    def my_type(self) -> str:
        return "TWonder"

    def add_receiver(self, hostname: str, port: int):
        if (hostname, port) not in self.hosts:
            super().add_receiver(hostname, port)

        msgs = []
        msgs.append(Message(self.oscpath_n_sources, self.numberOfSources))

        # TODO do this somewhere better
        if "room_polygon" in self.globalConfig:
            room_name = read_config_option(
                self.globalConfig, "room_name", str, "default_room"
            )
            room_polygon = read_config_option(
                self.globalConfig, "room_polygon", list, []
            )
            args = [room_name, len(room_polygon)]
            for point in room_polygon:
                if len(point) != 3:
                    raise RendererException(f"Invalid polygon point: {point}")
                for p in point:
                    if not isinstance(p, float):
                        raise RendererException(
                            f"Invalid type for coordinate {p} of polygon"
                        )

                args.extend(point)
            msgs.append(Message(self.oscpath_room_polygon, args))

        for i in range(self.numberOfSources):
            msgs.append(Message(self.oscpath_activate_source, i))
        self.send_updates(msgs)


class Audiorouter(Renderer):
    #
    def __init__(self, **kwargs):
        super(Audiorouter, self).__init__(**kwargs)

        self.debugPrefix = "/dAudiorouter"
        self.oscpre_renderGain = b"/source/send/spatial"
        self.oscpre_reverbGain = b"/source/reverb/gain"
        self.oscpre_directSend = b"/source/send/direct"

    def print_self_information(self, print_pos_format=False):
        super().print_self_information(print_pos_format=print_pos_format)

    def my_type(self) -> str:
        return "Audiorouter"

    def sourceDirectSendChanged(self, source_idx, send_idx):
        self.add_update(
            source_idx,
            DirectSendUpdate(
                self.oscpre_directSend,
                soundobject=self.sources[source_idx],
                send_index=send_idx,
                source_index=source_idx,
                include_send_idx=True,
            ),
        )

    def sourceRenderGainChanged(self, source_idx, render_idx):
        if render_idx == 1:
            return

        if render_idx == 2:
            path = self.oscpre_reverbGain
            include_render_idx = False
        else:
            path = self.oscpre_renderGain
            include_render_idx = True

        self.add_update(
            source_idx,
            GainUpdate(
                path=path,
                soundobject=self.sources[source_idx],
                render_idx=render_idx,
                source_index=source_idx,
                include_render_idx=include_render_idx,
            ),
        )


class AudiorouterWFS(Audiorouter):
    def __init__(self, **kwargs):
        super(AudiorouterWFS, self).__init__(**kwargs)
        self.debugPrefix = "/dAudiorouterWFS"

    def sourceRenderGainChanged(self, source_idx, render_idx):
        if render_idx != 1:
            return

        self.add_update(
            source_idx,
            GainUpdate(
                path=self.oscpre_renderGain,
                soundobject=self.sources[source_idx],
                render_idx=render_idx,
                source_index=source_idx,
                include_render_idx=True,
            ),
        )

    def my_type(self) -> str:
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

        # add all configured paths from the yaml file to either the correct gain path index,
        # or to the position_path list
        for path in paths:
            osc_path: str = path["path"]
            path_type = path["type"]

            if path_type == "gain":
                renderer = path["renderer"]
                renderer_index = self.render_unit_indices[renderer]
                self.gain_paths[renderer_index].append(osc_path.encode())
            elif path_type in ["position", "pos"]:
                try:
                    coord_fmt = path["format"]
                except KeyError:
                    coord_fmt = "xyz"
                self.pos_paths.append((osc_path.encode(), coord_fmt))

        log.debug("Audio Matrix initialized")

    def my_type(self) -> str:
        return "AudioMatrix"

    def sourceRenderGainChanged(self, source_idx, render_idx):
        if render_idx in self.gain_paths:
            for path in self.gain_paths[render_idx]:
                self.add_update(
                    source_idx,
                    GainUpdate(
                        path=path,
                        soundobject=self.sources[source_idx],
                        render_idx=render_idx,
                        source_index=source_idx,
                    ),
                )

    def sourcePositionChanged(self, source_idx):
        for path, coord_fmt in self.pos_paths:
            self.add_update(
                source_idx,
                PositionUpdate(
                    path=path,
                    soundobject=self.sources[source_idx],
                    coord_fmt=coord_fmt,
                    source_index=source_idx,
                ),
            )


# class Panoramix(SpatialRenderer):
#     def __init__(self, **kwargs):
#         if not "dataformat" in kwargs.keys():
#             kwargs["dataformat"] = skc.xyz
#         super(Panoramix, self).__init__(**kwargs)

#         self.posAddrs = []
#         for i in range(self.numberOfSources):
#             self.posAddrs.append(("/track/" + str(i + 1) + "/xyz").encode())

#         self.debugPrefix = "/dPanoramix"

#     def my_type(self) -> str:
#         return "Panoramix CAREFUL NOT REALLY IMPLEMENTED"

#     def composeSourceUpdateMessage(
#         self, values, sIdx: int = 0, *args
#     ) -> list[tuple[bytes, Iterable]]:
#         # msgs = []
#         sobject = self.sources[sIdx]
#         position = sobject.getPosition(self.posFormat)
#         # sourceID = source_idx + 1
#         addr = self.posAddrs[sIdx]

#         return [(addr, position)]


class SuperColliderEngine(SpatialRenderer):
    def __init__(self, **kwargs):
        if "dataformat" not in kwargs.keys():
            kwargs["dataformat"] = "aed"
        super(SuperColliderEngine, self).__init__(**kwargs)

        self.oscPre = b"/source/pos/aed"

        self.debugPrefix = "/dSuperCollider"

    def my_type(self) -> str:
        return "Supercolliderengine"


class ViewClient(SpatialRenderer):
    def my_type(self) -> str:
        return "viewClient: {}".format(self.alias)

    def __init__(self, aliasname, **kwargs):
        self.alias = aliasname

        super(ViewClient, self).__init__(**kwargs)

        self.pingCounter = 0

        self.debugPrefix = "/d{}".format(aliasname.decode())

        self.indexAsValue = False
        if "indexAsValue" in kwargs.keys():
            self.indexAsValue = kwargs["indexAsValue"]

        # TODO initialize variables only once, and with a consistent type pl0x
        self.idxSourceOscPrePos = [b""] * self.numberOfSources
        self.idxSourceOscPreAttri = [{}] * self.numberOfSources
        self.idxSourceOscPreRender = [
            [b"" for j in range(self.globalConfig["n_renderengines"])]
            for i in range(self.numberOfSources)
        ]

        self.createOscPrefixes()

        # self.idxSourceOscPreAttri

        self.pingTimer: Timer | None = None

        # send current state to viewclient
        for i in range(self.globalConfig["number_sources"]):
            self.sourcePositionChanged(i)
            for j in range(self.globalConfig["n_renderengines"]):
                self.sourceRenderGainChanged(i, j)

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
                for j in range(self.globalConfig["n_renderengines"]):
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
                    b"/oscrouter/ping", [self.globalConfig[skc.inputport_settings]]
                )  # , self.alias
            except Exception as e:
                log.warning(e)
                log.warning(f"error while pinging client { self.alias }, removing")
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
            path = self.idxSourceOscPrePos[source_idx]
            source_index_for_update = None
        else:
            path = self.oscPre
            source_index_for_update = source_idx
        self.add_update(
            source_idx,
            PositionUpdate(
                path=path,
                soundobject=self.sources[source_idx],
                coord_fmt=self.posFormat,
                source_index=source_index_for_update,
            ),
        )

    def sourceRenderGainChanged(self, source_idx, render_idx):
        # TODO option to send named paths instead
        if self.indexAsValue:
            path = self.idxSourceOscPreRender[source_idx][render_idx]
            source_index_for_update = None
        else:
            path = b"/source/send"
            source_index_for_update = source_idx
        self.add_update(
            source_idx,
            GainUpdate(
                path,
                soundobject=self.sources[source_idx],
                render_idx=render_idx,
                source_index=source_index_for_update,
                include_render_idx=True,
            ),
        )

    def sourceDirectSendChanged(self, source_idx, send_idx):
        path = b"/source/direct"
        self.add_update(
            source_idx,
            DirectSendUpdate(
                path,
                soundobject=self.sources[source_idx],
                send_index=send_idx,
                source_index=source_idx,
                include_send_idx=True,
            ),
        )

    def sourceAttributeChanged(self, source_idx, attribute):
        path = b"/source/attribute"
        self.add_update(
            source_idx,
            AttributeUpdate(
                path,
                attribute,
                soundobject=self.sources[source_idx],
                source_index=source_idx,
                include_attribute_name=True,
            ),
        )


# class Oscar(SpatialRenderer):
#     def __init__(self, **kwargs):
#         if not "dataformat" in kwargs.keys():
#             kwargs["dataformat"] = "aed"
#         super(Oscar, self).__init__(**kwargs)

#         self.sourceAttributes = (
#             skc.SourceAttributes.doppler,
#             skc.SourceAttributes.planewave,
#         )

#         # self.posAddrs = []

#         self.oscPosPre = []
#         self.oscAttrPre = []
#         self.oscRenderPre = []
#         self.oscDirectPre = []

#         for i in range(self.numberOfSources):
#             sourceAddrs = {}
#             for kk in skc.fullformat[self.posFormat]:
#                 addrStr = "/source/" + str(i + 1) + "/" + kk
#                 sourceAddrs[kk] = addrStr.encode()
#             self.oscPosPre.append(sourceAddrs)

#             attrDic = {}
#             for key in self.sourceAttributes:
#                 oscStr = "/source" + str(i + 1) + "/" + key.value
#                 attrDic[key] = oscStr.encode()
#             self.oscAttrPre.append(attrDic)

#             renderGainOscs = []
#             for rId in range(self.globalConfig["n_renderengines"]):
#                 riOsc = "/source/" + str(i + 1) + "/render/" + str(rId)
#                 renderGainOscs.append(riOsc.encode())
#             self.oscRenderPre.append(renderGainOscs)

#             channelSend = []
#             for cId in range(self.globalConfig["number_direct_sends"]):
#                 csOsc = "/source/" + str(i + 1) + "/direct/" + str(cId)
#                 channelSend.append(csOsc.encode())
#             self.oscDirectPre.append(channelSend)

#             # self.posAddrs.append(sourceAddrs)

#         self.validPosKeys = {skc.dist}

#         self.isDataClient = True

#         self.debugPrefix = "/dOscar"

#     def my_type(self) -> str:
#         return "Oscar"

#     def sourcePositionChanged(self, source_idx):
#         for key in skc.fullformat[self.posFormat.value]:
#             self.add_update(
#                 source_idx,
#                 PositionUpdate(
#                     self.oscPosPre[source_idx][key],
#                     soundobject=self.sources[source_idx],
#                     coord_fmt=skc.CoordFormats(key),
#                 ),
#             )

#     def sourceAttributeChanged(self, source_idx, attribute):
#         self.add_update(
#             source_idx,
#             AttributeUpdate(
#                 path=self.oscAttrPre[source_idx][attribute],
#                 soundobject=self.sources[source_idx],
#                 attribute=attribute,
#             ),
#         )

#     def sourceDirectSendChanged(self, source_idx, send_idx):
#         self.add_update(
#             source_idx,
#             DirectSendUpdate(
#                 path=self.oscDirectPre[source_idx][send_idx],
#                 soundobject=self.sources[source_idx],
#                 send_index=send_idx,
#             ),
#         )

#     def sourceRenderGainChanged(self, source_idx, render_idx):
#         self.add_update(
#             source_idx,
#             GainUpdate(
#                 path=self.oscRenderPre[source_idx][render_idx],
#                 soundobject=self.sources[source_idx],
#                 render_idx=render_idx,
#             ),
#         )


class SeamlessPlugin(SpatialRenderer):
    def my_type(self) -> str:
        return "Seamless Plugin"

    def __init__(self, **kwargs):
        if "dataformat" not in kwargs.keys():
            kwargs["dataformat"] = "xyz"
        super(SeamlessPlugin, self).__init__(**kwargs)

        self.sourceAttributes = (
            skc.SourceAttributes.doppler,
            skc.SourceAttributes.planewave,
        )

        self.oscAddrs: dict = {}

        self.oscAddrs[self.posFormat] = f"/source/pos/{self.posFormat}".encode()

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
        self.add_update(
            source_idx,
            GainUpdate(
                self.oscAddrs["renderGain"],
                soundobject=self.sources[source_idx],
                render_idx=render_idx,
                source_index=source_idx + 1,
                include_render_idx=True,
            ),
        )

    def sourcePositionChanged(self, source_idx):
        self.add_update(
            source_idx,
            PositionUpdate(
                path=self.oscAddrs[self.posFormat],
                soundobject=self.sources[source_idx],
                coord_fmt=self.posFormat,
                source_index=source_idx + 1,
            ),
        )


class DataClient(Audiorouter, SpatialRenderer):
    pass


renderer_name_dict = {
    "wonder": Wonder,
    # "panoramix": Panoramix,
    "viewclient": ViewClient,
    # "oscar": Oscar,
    "scengine": SuperColliderEngine,
    "audiorouter": Audiorouter,
    "seamlessplugin": SeamlessPlugin,
    "audiorouterwfs": AudiorouterWFS,
    "audiomatrix": AudioMatrix,
}


def createRendererClient(config: dict) -> Renderer:

    # (probably) a workaround for OSCAR, removed for now
    # if "dataformat" in config:
    #     tmp_dataFormat = config["dataformat"]
    #     if not tmp_dataFormat in skc.posformat.keys():
    #         if len(tmp_dataFormat.split("_")) == 2:
    #             preStr = ""
    #             if tmp_dataFormat.split("_")[0] == "normcartesian":
    #                 preStr = "n"

    #             dFo = preStr + tmp_dataFormat.split("_")[1]
    #             config["dataformat"] = dFo
    #         else:
    #             log.warn("unknown position format")
    #             del config["dataformat"]

    if "type" not in config:
        raise RendererException("Type of receiver unspecified")

    renderer_type = config["type"].lower()
    del config["type"]

    if renderer_type not in renderer_name_dict:
        raise RendererException(f"Invalid receiver type: {renderer_type}")

    return renderer_name_dict[renderer_type](**config)

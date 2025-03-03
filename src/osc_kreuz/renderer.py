from collections.abc import Iterable
import logging
import socket
from threading import Semaphore, Timer
from time import sleep, thread_time, time
from typing import Any

from numpy import iterable
from pythonosc.udp_client import SimpleUDPClient

from osc_kreuz.config import add_renderer_to_state_file, read_config_option
from osc_kreuz.soundobject import SoundObject
import osc_kreuz.str_keys_conventions as skc

log = logging.getLogger("renderer")
verbosity = 0


class RendererException(Exception):
    pass


class Message:
    def __init__(self, path: str, values: Any) -> None:
        self.path: str = path
        if isinstance(values, str) or not iterable(values):
            values = [values]
        self.values: Iterable[Any] = values


class Update:
    """Base Class for an Update sent via OSC. Updates with specific requirements should inherit from this one"""

    def __init__(
        self,
        path: str,
        soundobject: SoundObject,
        source_index: int | None = None,
        pre_arg: Any = None,
        post_arg: Any = None,
    ):
        """Construct a new Update.
        The values of the Message created out of this Update will look like this, values in <brackets> are optional:
        [<source_index>, <pre_arg>, value, <**values>,..., <post_arg>]


        Args:
            path (str): OSC Path this update should be sent to
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
        path: str,
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
        path: str,
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
        path: str,
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
        path: str,
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


class BaseRenderer(object):

    numberOfSources = 64
    sources: list[SoundObject] = []
    globalConfig: dict = {}
    debugCopy: bool = False
    oscDebugClient: SimpleUDPClient

    printOutput = verbosity >= 1
    oscpath_position = ""

    @classmethod
    def createDebugClient(cls, ip: str, port: int) -> None:
        cls.oscDebugClient = SimpleUDPClient(ip, port)

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

        # convert update interval from ms to s
        self.update_interval = int(updateintervall) / 1000

        # sets are used in update stack, so each source is updated only once during the update process
        self.update_stack: list[set[Update]] = [
            set() for _ in range(self.numberOfSources)
        ]
        # second update Stack that is swapped in during updates
        self.update_stack_swap: list[set[Update]] = [
            set() for _ in range(self.numberOfSources)
        ]

        self.update_semaphore: list[Semaphore] = [
            Semaphore() for _ in range(self.numberOfSources)
        ]

        if self.oscpath_position == "":
            self.oscpath_position = "/source/" + self.posFormat

        self.hosts: list[tuple[str, int]] = []
        self.receivers: list[tuple[str, SimpleUDPClient]] = []

        # check if hosts are defined as an array
        if hostname is not None and port is not None:
            self.add_receiver(hostname, int(port))
        if hosts is not None:
            for host in hosts:
                try:
                    self.add_receiver(host["hostname"], host["port"])
                except KeyError:
                    raise RendererException("Invalid Host")

        if len(self.receivers) == 0:
            log.warning(f"Renderer of type {self.my_type()} has no receivers")

        self.print_self_information()

    def print_self_information(self, print_pos_format=True):
        log.info(f"Initialized renderer {self.my_type()}")
        hosts_str = ", ".join(
            [f"{hostname}:{receiver._port}" for hostname, receiver in self.receivers]
        )
        log.info(f"\thosts: {hosts_str}")
        if print_pos_format:
            log.info(f"\tlistening to format {self.posFormat}")

    def my_type(self) -> str:
        return self.__class__.__name__

    def add_receiver(self, hostname: str, port: int):

        # get ip from hostname to prevent repeated dns lookups
        ip = None
        n_retries = 120
        while ip is None:
            try:
                ip = socket.gethostbyname(hostname)
            except socket.gaierror as e:
                if n_retries <= 0:
                    log.warning(
                        f"failed to add receiver {hostname}:{port}, using hostname instead"
                    )
                    ip = hostname

                else:
                    log.warning(
                        f"getting ip for receiver {hostname}:{port} failed: {e}, retrying..."
                    )
                    n_retries -= 1
                    sleep(1)

        # TODO implement retrying here
        try:
            self.receivers.append((hostname, SimpleUDPClient(ip, port)))
        except socket.gaierror as e:
            log.error(
                f"failed to connect to receiver {hostname}:{port} for renderer {self.my_type()}: {e}"
            )

    def add_update(self, source_idx: int, update: Update) -> None:
        self.update_stack[source_idx].add(update)
        self.update_source(source_idx)

    def update_source(self, source_idx) -> None:
        """Builds and sends source update messages

        Args:
            source_idx (int): index of source to be updated
        """
        # if an update is already in progress simply return
        if not self.update_semaphore[source_idx].acquire(blocking=False):
            return

        if len(self.update_stack[source_idx]) == 0:
            self.update_semaphore[source_idx].release()
            log.info("didn't need to do anything")
            return

        time_start = time()

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
        t = Timer(
            self.update_interval - (time() - time_start),
            self.release_source_update_lock,
            args=(source_idx,),
        )
        t.name = f"rel_{source_idx:02}_{self.my_type()}"
        t.start()

    def send_updates(self, msgs, hostname: str | None = None, port: int | None = None):
        """This function sends all messages to the osc clients

        Args:
            msgs (list(list)): list of messages
        """
        for msg in msgs:
            for i, (r_hostname, receiver) in enumerate(self.receivers):

                # if explicit hostname and port are specified skip all receivers that don't match
                if hostname is not None and port is not None:
                    if r_hostname != hostname or receiver._port != port:
                        continue

                try:
                    # time sending performance
                    t1_thread = thread_time()
                    t1 = time()

                    # actually send
                    receiver.send_message(msg.path, msg.values)

                    t2_thread = thread_time()
                    t2 = time()
                    send_time = (t2 - t1) * 1000
                    if send_time > 10:
                        log.warning(
                            f"sending osc update {msg.path} to {receiver._address} took way too long: {round(send_time,2)}ms, (thread time: {round((t2_thread - t1_thread)*1000, 2)})"
                        )
                except Exception as e:
                    log.error(
                        f"Exception while sending to {receiver._address}:{receiver._port}: {e}",
                    )

                if self.debugCopy:
                    debugOsc = f"/d{self.my_type()}/{receiver._address}:{receiver._port}{msg.path}"
                    try:
                        self.oscDebugClient.send_message(debugOsc, msg.values)
                    except Exception:
                        pass

            if self.printOutput:
                self.printOscOutput(msg.path, msg.values)

    def release_source_update_lock(self, source_idx):
        self.update_semaphore[source_idx].release()
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

    def dump_source_positions(self):
        # TODO make receiver specifyable by hostname/port so it doesn't have to get sent out for all receivers multi-receiver renderers like twonder
        for i in range(
            read_config_option(self.globalConfig, "number_sources", int, 64)
        ):
            self.sourcePositionChanged(i)

    def dump_source_gains(self):
        # TODO make receiver specifyable by hostname/port so it doesn't have to get sent out for all receivers multi-receiver renderers like twonder
        for i in range(
            read_config_option(self.globalConfig, "number_sources", int, 64)
        ):
            for j in range(
                read_config_option(self.globalConfig, "n_renderengines", int, 3)
            ):
                self.sourceRenderGainChanged(i, j)

    def printOscOutput(self, oscpath: str, data: list):
        log.debug("OSC to %s %s with values %s", self.__class__.__name__, oscpath, data)


class SpatialRenderer(BaseRenderer):
    def sourcePositionChanged(self, source_idx):
        self.add_update(
            source_idx,
            PositionUpdate(
                path=self.oscpath_position,
                soundobject=self.sources[source_idx],
                coord_fmt=self.posFormat,
                source_index=source_idx,
            ),
        )


class Wonder(SpatialRenderer):
    oscpath_position = "/WONDER/source/position"
    attributeOsc = {
        skc.SourceAttributes.doppler: "/WONDER/source/dopplerEffect",
        skc.SourceAttributes.planewave: "/WONDER/source/type",
        skc.SourceAttributes.angle: "/WONDER/source/angle",
    }

    def __init__(self, **kwargs):
        if "dataformat" not in kwargs:
            kwargs["dataformat"] = "xy"
        if "sourceattributes" not in kwargs:
            kwargs["sourceattributes"] = (
                skc.SourceAttributes.doppler,
                skc.SourceAttributes.planewave,
            )
        if "updateintervall" not in kwargs:
            kwargs["updateintervall"] = 50
        self.interpolTime = int(kwargs["updateintervall"]) / 1000
        self.linkPositionAndAngle = True

        super(Wonder, self).__init__(**kwargs)

    def sourcePositionChanged(self, source_idx):
        # Add position Update to update stack
        self.add_update(
            source_idx,
            PositionUpdate(
                path=self.oscpath_position,
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
    oscpath_n_sources = "/WONDER/global/maxNoSources"
    oscpath_room_polygon = "/WONDER/global/renderpolygon"
    oscpath_activate_source = "/WONDER/source/activate"

    def add_receiver(self, hostname: str, port: int):

        # check that osc-kreuz is ready to function as cwonder replacement
        if "room_polygon" not in self.globalConfig:
            raise RendererException(
                "Can't connect twonder because no room_polygon was specified in config"
            )

        # make sure every twonder is only added once
        if (hostname, port) not in (
            (hostname, receiver._port) for hostname, receiver in self.receivers
        ):
            super().add_receiver(hostname, port)
            add_renderer_to_state_file("twonder", hostname, port)

        # send current state to twonder
        # BUGFIX don't do this here until the twonder bug causing it to work inconsistently when getting initialized twice is fixed
        # self.send_room_information(hostname, port)
        self.dump_source_positions()

    def send_room_information(self, hostname: str, port: int):
        """send status information for renderer to twonder

        Args:
            hostname (str): hostname of the receiving twonder
            port (int): port of the receiving twonder
        """
        msgs = []

        # send number of sources
        msgs.append(Message(self.oscpath_n_sources, self.numberOfSources))

        # send information about room
        room_name = read_config_option(
            self.globalConfig, "room_name", str, "default_room"
        )

        # read room polygon
        room_polygon = read_config_option(self.globalConfig, "room_polygon", list, [])
        if len(room_polygon) == 0:
            raise RendererException("room_polygon has length of 0")

        # args for this osc-path are [room_name, n_points_polygon, point_0_x, point_0_y, point_0_z, point_1_x...]
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

        # send activation information
        for i in range(self.numberOfSources):
            msgs.append(Message(self.oscpath_activate_source, i))
        self.send_updates(msgs, hostname, port)


class Audiorouter(BaseRenderer):
    oscpath_gain_renderer = "/source/send/spatial"
    oscpath_gain_reverb = "/source/reverb/gain"
    oscpath_gain_direct = "/source/send/direct"

    def print_self_information(self, print_pos_format=False):
        super().print_self_information(print_pos_format=print_pos_format)

    def sourceDirectSendChanged(self, source_idx, send_idx):
        self.add_update(
            source_idx,
            DirectSendUpdate(
                self.oscpath_gain_direct,
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
            path = self.oscpath_gain_reverb
            include_render_idx = False
        else:
            path = self.oscpath_gain_renderer
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
    def sourceRenderGainChanged(self, source_idx, render_idx):
        if render_idx != 1:
            return

        self.add_update(
            source_idx,
            GainUpdate(
                path=self.oscpath_gain_renderer,
                soundobject=self.sources[source_idx],
                render_idx=render_idx,
                source_index=source_idx,
                include_render_idx=True,
            ),
        )


class AudioMatrix(BaseRenderer):
    def __init__(self, paths: Iterable[dict["str", Any]], **kwargs):
        super().__init__(**kwargs)
        self.gain_paths: dict[int, list[str]] = {}
        self.pos_paths: list[tuple[str, str]] = []

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
                self.gain_paths[renderer_index].append(osc_path)
            elif path_type in ["position", "pos"]:
                try:
                    coord_fmt = path["format"]
                except KeyError:
                    coord_fmt = "xyz"
                self.pos_paths.append((osc_path, coord_fmt))

        log.debug("Audio Matrix initialized")

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


class SuperColliderEngine(SpatialRenderer):
    oscpath_position = "/source/pos/aed"

    def __init__(self, **kwargs):
        if "dataformat" not in kwargs.keys():
            kwargs["dataformat"] = "aed"
        super(SuperColliderEngine, self).__init__(**kwargs)


class ViewClient(SpatialRenderer):
    def my_type(self) -> str:
        return f"{super().my_type()}_{self.alias}"

    def __init__(self, aliasname: str, **kwargs):
        self.alias = aliasname
        log.info(type(self.alias))

        super(ViewClient, self).__init__(**kwargs)

        self.pingCounter = 0

        self.indexAsValue = False
        if "indexAsValue" in kwargs.keys():
            self.indexAsValue = kwargs["indexAsValue"]

        # TODO initialize variables only once, and with a consistent type pl0x
        self.idxSourceOscPrePos = [""] * self.numberOfSources
        self.idxSourceOscPreAttri = [{}] * self.numberOfSources
        self.idxSourceOscPreRender = [
            ["" for j in range(self.globalConfig["n_renderengines"])]
            for i in range(self.numberOfSources)
        ]

        self.createOscPrefixes()

        self.pingTimer: Timer | None = None

        # send current state to viewclient
        self.dump_source_positions()
        self.dump_source_gains()

    def createOscPrefixes(self):
        for i in range(self.numberOfSources):
            self.idxSourceOscPrePos[i] = "/source/{}/{}".format(i + 1, self.posFormat)
            _aDic = {}
            for attr in skc.knownAttributes:
                _aDic[attr] = "/source/{}/{}".format(i + 1, attr)

            self.idxSourceOscPreAttri[i] = _aDic

            try:
                render_units = self.globalConfig["render_units"]
            except KeyError:
                render_units = []

            renderList = [""] * self.globalConfig["n_renderengines"]
            if (
                "ambi" in render_units
                and "wfs" in render_units
                and "reverb" in render_units
            ):
                renderList[render_units.index("ambi")] = "/source/{}/ambi".format(i + 1)
                renderList[render_units.index("wfs")] = "/source/{}/wfs".format(i + 1)
                renderList[render_units.index("reverb")] = "/source/{}/reverb".format(
                    i + 1
                )
            else:
                for j in range(self.globalConfig["n_renderengines"]):
                    self.idxSourceOscPreRender[i][j] = "/source/{}/send/{}".format(
                        i + 1, j
                    )
            self.idxSourceOscPreRender[i] = renderList

    def checkAlive(self, deleteClient):
        self.pingTimer = Timer(2.0, self.checkAlive, args=(deleteClient,))
        self.pingTimer.name = f"pingtimer {self.alias}"

        if self.pingCounter < 6:
            try:
                # get first receiver tuple, get actual receiver
                self.receivers[0][1].send_message(
                    # TODO change ping path to constant defined somewhere else
                    "/oscrouter/ping",
                    [self.globalConfig[skc.inputport_settings]],
                )
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
            path = self.oscpath_position
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
            path = "/source/send"
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
        path = "/source/direct"
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
        path = "/source/attribute"
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

    def __init__(self, **kwargs):
        if "dataformat" not in kwargs.keys():
            kwargs["dataformat"] = "xyz"
        super(SeamlessPlugin, self).__init__(**kwargs)

        self.sourceAttributes = (
            skc.SourceAttributes.doppler,
            skc.SourceAttributes.planewave,
        )

        self.oscAddrs: dict = {}

        self.oscAddrs[self.posFormat] = f"/source/pos/{self.posFormat}"

        for vv in self.sourceAttributes:
            self.oscAddrs[vv.value] = "/{}".format(vv.value)

        self.oscAddrs["renderGain"] = "/send/gain"

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


renderer_name_dict = {
    "wonder": Wonder,
    "twonder": TWonder,
    # "panoramix": Panoramix,
    "viewclient": ViewClient,
    # "oscar": Oscar,
    "scengine": SuperColliderEngine,
    "audiorouter": Audiorouter,
    "seamlessplugin": SeamlessPlugin,
    "audiorouterwfs": AudiorouterWFS,
    "audiomatrix": AudioMatrix,
}


def createRendererClient(config: dict) -> BaseRenderer:

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

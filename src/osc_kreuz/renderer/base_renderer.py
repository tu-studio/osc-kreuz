import logging
import socket
from threading import Semaphore, Timer
from time import sleep, thread_time, time

from pythonosc.udp_client import SimpleUDPClient

from osc_kreuz.config import read_config_option
from osc_kreuz.soundobject import SoundObject

from .updates import Update, OSCMessage

log = logging.getLogger("renderer")
verbosity = 0


class RendererException(Exception):
    pass


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

    def send_updates(
        self,
        msgs: list[OSCMessage],
        hostname: str | None = None,
        port: int | None = None,
    ):
        """This function sends all messages to the osc clients

        Args:
            msgs (list[OSCMessage]): list of messages
        """
        # if explicit hostname and port are specified,
        # create a list with just one udp client for the specified host
        receivers_to_update = (
            [(hostname, SimpleUDPClient(hostname, port))]
            if hostname is not None and port is not None
            else self.receivers
        )
        for msg in msgs:
            for r_hostname, receiver in receivers_to_update:

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

    def dump_room_polygon(
        self,
        oscpath: str = "/room/polygon",
        hostname: str | None = None,
        port: int | None = None,
    ):
        # send information about room
        room_name = read_config_option(
            self.globalConfig, "room_name", str, "default_room"
        )

        # read room polygon
        room_polygon: list[list[float]] = read_config_option(
            self.globalConfig, "room_polygon", list, []
        )

        # args for this osc-path are [room_name, n_points_polygon, point_0_x, point_0_y, point_0_z, point_1_x...]
        args = [room_name, len(room_polygon)]

        for point in room_polygon:
            if len(point) != 3:
                log.error(f"Invalid polygon point: {point}")
                continue

            try:
                args.extend([float(p) for p in point])
            except ValueError:
                log.error(f"Invalid type for point {point}")

        if len(args) == 2:
            log.warning("Room Polygon has no points")

        self.send_updates([OSCMessage(oscpath, args)], hostname, port)

    def printOscOutput(self, oscpath: str, data: list):
        log.debug("OSC to %s %s with values %s", self.__class__.__name__, oscpath, data)

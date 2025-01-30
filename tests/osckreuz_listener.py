from dataclasses import dataclass, field
import logging
from threading import Event, Thread, Timer
from time import sleep
from types import NoneType
from typing import Callable, List

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

log = logging.getLogger()


n_renderers = 3
n_direct_sends = 64
attributes = ["doppler", "planewave", "angle"]


@dataclass
class Source:
    idx: int
    x: float = 0
    y: float = 0
    z: float = 0
    gain: List[float] = field(default_factory=lambda: [0.0 for i in range(n_renderers)])
    direct_sends: List[float] = field(
        default_factory=lambda: [0.0 for i in range(n_direct_sends)]
    )
    attributes: dict[str, float] = field(
        default_factory=lambda: dict([(attr, 0.0) for attr in attributes])
    )


class Watchdog(Exception):
    def __init__(self, timeout, userHandler=None):  # timeout in seconds
        self.timeout = timeout
        self.handler = userHandler if userHandler is not None else self.defaultHandler

    def start(self):
        self.timer = Timer(self.timeout, self.handler)
        self.timer.start()

    def reset(self, new_timeout: float | None = None):
        self.timer.cancel()
        if new_timeout:
            self.timeout = new_timeout
        self.timer = Timer(self.timeout, self.handler)
        self.timer.start()

    def stop(self):
        self.timer.cancel()

    def defaultHandler(self):
        raise self


class SeamlessListener:
    def __init__(
        self,
        n_sources: int,
        listen_ip,
        listen_port,
        osc_kreuz_hostname,
        osc_kreuz_port,
        name="seamless_status",
        reconnect_timeout: float = 5,
    ) -> None:
        self.name = name
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.osc_kreuz_hostname = osc_kreuz_hostname
        self.osc_kreuz_port = osc_kreuz_port
        self.is_connected = Event()
        self.sources = [Source(idx=i) for i in range(n_sources)]

        self.osc_dispatcher = Dispatcher()
        self.osc = BlockingOSCUDPServer((listen_ip, listen_port), self.osc_dispatcher)
        self.osc_client = SimpleUDPClient(osc_kreuz_hostname, osc_kreuz_port)

        self.reconnect_timer = Watchdog(reconnect_timeout, self.subscribe_to_osc_kreuz)

        self.osc_thread: None | Thread = None

        self.position_callback: (
            NoneType | Callable[[int, float, float, float], None]
        ) = None
        self.gain_callback: NoneType | Callable[[int, int, float], None] = None
        self.attribute_callback: NoneType | Callable[[int, str, float], None] = None
        self.direct_send_callback: NoneType | Callable[[int, int, float], None] = None

        # needed for default callback to notify of changes
        self.something_changed = Event()

    # TODO reinitialize if no ping for x Seconds

    def setup_default_osc_callback(self):
        self.register_gain_callback(self.default_osc_callback)
        self.register_position_callback(self.default_osc_callback)
        self.register_attribute_callback(self.default_osc_callback)
        self.register_direct_send_callback(self.default_osc_callback)

    def default_osc_callback(self, *args):
        self.something_changed.set()

    def start_listening(self):
        self.osc_thread = Thread(
            target=self.osc.serve_forever, args=(0.1,), name="osckreuz_listener"
        )
        self.osc_thread.start()
        self.osc_dispatcher.map("/oscrouter/ping", self.pong)
        self.osc_dispatcher.map("/source/xyz", self.receive_xyz)
        self.osc_dispatcher.map("/source/send", self.receive_gain)
        self.osc_dispatcher.map("/source/direct", self.receive_direct_send_gain)
        self.osc_dispatcher.map("/source/attribute", self.receive_attribute)
        self.osc_dispatcher.set_default_handler(self.default_handler)

        self.subscribe_to_osc_kreuz()

    def send_full_positions(self):
        # TODO use seperate callback maybe?
        for source in self.sources:
            if self.position_callback is not None:
                _ = self.position_callback(source.idx, source.x, source.y, source.z)

    def default_handler(self, address, *args):
        log.warning(f"received on default handler {address}: {args}")

    def register_position_callback(
        self, callback: Callable[[int, float, float, float], None]
    ):
        self.position_callback = callback

    def register_gain_callback(self, callback: Callable[[int, int, float], None]):
        self.gain_callback = callback

    def register_direct_send_callback(
        self, callback: Callable[[int, int, float], None]
    ):
        self.direct_send_callback = callback

    def register_attribute_callback(self, callback: Callable[[int, str, float], None]):
        self.attribute_callback = callback

    def pong(self, *values):
        print("listener received ping")
        self.is_connected.set()
        self.reconnect_timer.reset(3)
        self.osc_client.send_message("/oscrouter/pong", self.name)

    def receive_xyz(self, address: str, *values):
        if len(values) != 4:
            return

        source_id = int(values[0])
        x, y, z = map(float, values[1:])

        self.sources[source_id].x = x
        self.sources[source_id].y = y
        self.sources[source_id].z = z
        if self.position_callback is not None:
            self.position_callback(source_id, x, y, z)

    def receive_gain(self, address: str, *values):
        if len(values) != 3:
            log.warning(f"received gain update with invalid values: {values}")
            return
        source_id = int(values[0])
        renderer_id = int(values[1])
        gain = float(values[2])
        self.sources[source_id].gain[renderer_id] = gain

        if self.gain_callback is not None:
            self.gain_callback(source_id, renderer_id, gain)

    def receive_direct_send_gain(self, address: str, *values):
        if len(values) != 3:
            return
        source_id = int(values[0])
        direct_send_id = int(values[1])
        gain = float(values[2])

        self.sources[source_id].direct_sends[direct_send_id] = gain
        log.info(self.sources[source_id].direct_sends)
        if self.direct_send_callback is not None:
            self.direct_send_callback(source_id, direct_send_id, gain)

    def receive_attribute(self, address: str, *values):
        if len(values) != 3:
            return

        source_id = int(values[0])
        attr = str(values[1])
        val = float(values[2])
        self.sources[source_id].attributes[attr] = val

        if self.attribute_callback is not None:
            self.attribute_callback(source_id, attr, val)

    def subscribe_to_osc_kreuz(self):
        print(
            f"sending subscribe message to {self.osc_kreuz_hostname}:{self.osc_kreuz_port}"
        )
        self.osc_client.send_message(
            "/oscrouter/subscribe",
            [self.name, self.listen_port, "xyz", 0, 0],
        )
        self.reconnect_timer.start()

    def unsubscribe_from_osc_kreuz(self):

        try:
            self.osc_client.send_message(
                "/oscrouter/unsubscribe",
                self.name,
            )

            self.reconnect_timer.stop()

        except (RuntimeError, AttributeError):
            # handle shutdowns in dev mode of fastapi
            log.exception("exception while unsubscribing")
            pass

    def shutdown(self):
        if self.osc_thread is not None and self.osc_thread.is_alive():
            self.osc.shutdown()
        self.unsubscribe_from_osc_kreuz()

    def __del__(self):
        self.shutdown()


if __name__ == "__main__":
    # register with osc_kreuz
    osc_kreuz_ip = "127.0.0.1"
    osc_kreuz_port = 4999
    name = "seamless_status"

    n_sources = 64

    ip = "0.0.0.0"
    port = 51213

    s = SeamlessListener(n_sources, ip, port, osc_kreuz_ip, osc_kreuz_port, name)
    s.start_listening()
    sleep(2.5)
    s.shutdown()

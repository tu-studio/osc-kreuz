from dataclasses import dataclass, field
import logging
import signal
from threading import Timer
from types import NoneType
from typing import Callable, List

from oscpy.server import OSCThreadServer, ServerClass

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

    def reset(self):
        self.timer.cancel()
        self.timer = Timer(self.timeout, self.handler)
        self.timer.start()

    def stop(self):
        self.timer.cancel()

    def defaultHandler(self):
        raise self


@ServerClass
class SeamlessListener:
    def __init__(
        self,
        n_sources: int,
        listen_ip,
        listen_port,
        osc_kreuz_hostname,
        osc_kreuz_port,
        name="seamless_status",
        reconnect_timeout=5,
    ) -> None:
        self.name = name
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.osc_kreuz_hostname = osc_kreuz_hostname
        self.osc_kreuz_port = osc_kreuz_port

        self.sources = [Source(idx=i) for i in range(n_sources)]
        self.osc = OSCThreadServer()
        self.reconnect_timer = Watchdog(reconnect_timeout, self.subscribe_to_osc_kreuz)

        self.position_callback: (
            NoneType | Callable[[int, float, float, float], None]
        ) = None
        self.gain_callback: NoneType | Callable[[int, int, float], None] = None
        self.attribute_callback: NoneType | Callable[[int, str, float], None] = None
        self.direct_send_callback: NoneType | Callable[[int, int, float], None] = None

    # TODO reinitialize if no ping for x Seconds

    def start_listening(self):
        self.osc.listen(self.listen_ip, self.listen_port, True)
        self.osc.bind(b"/oscrouter/ping", self.pong)
        self.osc.bind(b"/source/xyz", self.receive_xyz)
        self.osc.bind(b"/source/send", self.receive_gain)
        self.osc.bind(b"/source/direct", self.receive_direct_send_gain)
        self.osc.bind(b"/source/attribute", self.receive_attribute)

        self.subscribe_to_osc_kreuz()

    def send_full_positions(self):
        # TODO use seperate callback maybe?
        for source in self.sources:
            if self.position_callback is not None:
                _ = self.position_callback(source.idx, source.x, source.y, source.z)

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
        log.info("listener received ping")
        self.reconnect_timer.reset()
        self.osc.send_message(
            b"/oscrouter/pong",
            (self.name.encode(),),
            self.osc_kreuz_hostname,
            self.osc_kreuz_port,
        )

    def receive_xyz(self, *values):
        if len(values) != 4:
            return

        source_id = int(values[0])
        x, y, z = map(float, values[1:])

        self.sources[source_id].x = x
        self.sources[source_id].y = y
        self.sources[source_id].z = z
        if self.position_callback is not None:
            self.position_callback(source_id, x, y, z)

    def receive_gain(self, *values):
        if len(values) != 3:
            return
        source_id = int(values[0])
        renderer_id = int(values[1])
        gain = float(values[2])
        self.sources[source_id].gain[renderer_id] = gain

        if self.gain_callback is not None:
            self.gain_callback(source_id, renderer_id, gain)

    def receive_direct_send_gain(self, *values):
        if len(values) != 3:
            return
        source_id = int(values[0])
        direct_send_id = int(values[1])
        gain = float(values[2])
        self.sources[source_id].direct_sends[direct_send_id] = gain
        print(self.sources[source_id].direct_sends)
        if self.direct_send_callback is not None:
            self.direct_send_callback(source_id, direct_send_id, gain)

    def receive_attribute(self, *values):
        if len(values) != 3:
            return

        source_id = int(values[0])
        attr = bytes(values[1]).decode()
        val = float(values[2])
        self.sources[source_id].attributes[attr] = val

        if self.attribute_callback is not None:
            self.attribute_callback(source_id, attr, val)

    def subscribe_to_osc_kreuz(self):
        logging.info(
            f"sending subscribe message to {self.osc_kreuz_hostname}:{self.osc_kreuz_port}"
        )
        print(
            f"sending subscribe message to {self.osc_kreuz_hostname}:{self.osc_kreuz_port}"
        )
        self.osc.send_message(
            "/oscrouter/subscribe".encode(),
            [self.name.encode(), self.listen_port, b"xyz", 0, 1],
            self.osc_kreuz_hostname,
            self.osc_kreuz_port,
        )
        self.reconnect_timer.start()

    def unsubscribe_from_osc_kreuz(self):
        try:
            self.osc.send_message(
                b"/oscrouter/unsubscribe",
                [self.name.encode()],
                self.osc_kreuz_hostname,
                self.osc_kreuz_port,
            )

            self.reconnect_timer.stop()
            self.osc.close()

        except (RuntimeError, AttributeError):
            # handle shutdowns in dev mode of fastapi
            pass

    def __del__(self):
        self.unsubscribe_from_osc_kreuz()


if __name__ == "__main__":
    # register with osc_kreuz
    osc_kreuz_ip = "130.149.23.211"
    osc_kreuz_port = 4999
    name = "seamless_status"

    n_sources = 64

    ip = "0.0.0.0"
    port = 51213

    SeamlessListener(n_sources, ip, port, osc_kreuz_ip, osc_kreuz_port, name)
    signal.pause()

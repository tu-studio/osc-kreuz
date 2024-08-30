import logging
import math
import os
from pathlib import Path
import random
import signal
from threading import Event, Thread
from time import sleep, time

from click.testing import CliRunner
from oscpy.client import OSCClient

from osc_kreuz.osc_kreuz import main, read_config, read_config_option, signal_handler
from osckreuz_listener import SeamlessListener
import osc_kreuz.str_keys_conventions as skc
import osc_kreuz.coordinates

test_config = Path(__file__).parent / "assets" / "config_test.yml"
config = read_config(test_config)

n_sources = config["global"]["number_sources"]
renderers = config["global"]["render_units"]
n_renderers = len(renderers)


def build_gain_test_path(path, renderer_in_path, source_index_in_path):
    source_index = random.randint(0, n_sources - 1)
    val = random.random() * 2
    renderer_index = random.randint(0, n_renderers - 1)
    renderer = renderers[renderer_index]
    if renderer in skc.osc_aliases:
        renderer = random.choice(skc.osc_aliases[renderer])
    args = []

    path = path.format(idx=source_index + 1, val=renderer)

    if not source_index_in_path:
        args.append(source_index + 1)

    if not renderer_in_path:
        args.append(renderer_index)

    args.append(val)

    return (path, args, source_index, renderer_index, val)


# def build_coordinate_test_path(path, source_index_in_path):
#     source_index = random.randint(0, n_sources - 1)
#     args = []
#     if not source_index_in_path:
#         args.append(source_index + 1)
#     for coordinate_format_str in osc_kreuz.coordinates.get_all_coordinate_formats():
#         coordinate_system, coordinate_keys = osc_kreuz.coordinates.parse_coordinate_format(coordinate_format_str)
#         if coordinate_system
#         # TODO continue here
#         # TODO how to handle incomplete paths here?

#     return (path, args, source_index, (x_expected, y_expected, z_expected))


def build_all_gain_paths():
    paths = []

    for _ in range(30):
        for path in ["/source/send/spatial", "/send/gain", "/source/send"]:
            paths.append(build_gain_test_path(path, False, False))

        for path in skc.osc_paths[skc.OscPathType.Gain]["base"]:
            paths.append(
                build_gain_test_path(
                    path, renderer_in_path=True, source_index_in_path=False
                )
            )

        for path in skc.osc_paths[skc.OscPathType.Gain]["extended"]:
            paths.append(
                build_gain_test_path(
                    path, renderer_in_path=True, source_index_in_path=True
                )
            )
    return paths


def test_gains():
    runner = CliRunner()
    osc_kreuz_thread = Thread(
        target=runner.invoke,
        args=(main, ["-c", str(test_config.absolute().resolve())]),
    )
    osc_kreuz_thread.start()
    sleep(0.5)
    listener = SeamlessListener(
        n_sources, "127.0.0.1", 9876, "127.0.0.1", 4999, "osckreuz_test"
    )
    sender = OSCClient("127.0.0.1", 4455)

    something_changed = Event()

    def osc_callback(*args):
        something_changed.set()

    listener.register_gain_callback(osc_callback)
    listener.register_position_callback(osc_callback)
    listener.start_listening()

    sleep(1)
    for path, args, source_index, renderer, expected_val in build_all_gain_paths():
        something_changed.clear()

        sender.send_message(path.encode(), args)
        val = something_changed.wait(5)

        assert val == True
        # logging.info(listener.sources)
        assert math.isclose(
            listener.sources[source_index].gain[renderer], expected_val, rel_tol=1e-06
        )
        print(f"success for gain path {path}")
    logging.info("unsubscribing")
    listener.unsubscribe_from_osc_kreuz()
    signal_handler()
    logging.info("killed osc-kreuz")


if __name__ == "__main__":
    test_gains()

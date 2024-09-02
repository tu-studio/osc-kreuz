from itertools import product
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

from osc_kreuz.config import read_config
from osc_kreuz.osc_kreuz import main, signal_handler
from osckreuz_listener import SeamlessListener, Source
import osc_kreuz.str_keys_conventions as skc
import osc_kreuz.coordinates
from osc_kreuz.coordinates import (
    CoordinateKey,
    CoordinatePolar,
    CoordinatePolarRadians,
    CoordinateSystemType,
)
import numpy as np

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
    # cli runner to run the actual osckreuz
    runner = CliRunner()
    osc_kreuz_thread = Thread(
        target=runner.invoke,
        args=(main, ["-c", str(test_config.absolute().resolve())]),
    )
    osc_kreuz_thread.start()

    sleep(0.5)

    # listener to receive osc from osc kreuz
    listener = SeamlessListener(
        n_sources, "127.0.0.1", 9876, "127.0.0.1", 4999, "osckreuz_test"
    )

    # sender to send updates to osc-kreuz
    sender = OSCClient("127.0.0.1", 4455)

    # something changed to check if the update sent to the osc-kreuz also came back
    something_changed = Event()

    def osc_callback(*args):
        something_changed.set()

    # setup listener
    listener.register_gain_callback(osc_callback)
    listener.register_position_callback(osc_callback)
    listener.start_listening()

    # sleep to wait for initial barrage of updates
    sleep(0.5)

    # test a lot of different paths
    for path, args, source_index, renderer, expected_val in build_all_gain_paths():
        something_changed.clear()

        sender.send_message(path.encode(), args)
        val = something_changed.wait(5)

        assert val == True
        # standard epsilon is to fine grained
        assert math.isclose(
            listener.sources[source_index].gain[renderer], expected_val, rel_tol=1e-06
        )
        print(f"success for gain path {path}")
    logging.info("unsubscribing")
    listener.unsubscribe_from_osc_kreuz()
    signal_handler()
    logging.info("killed osc-kreuz")


def random_coords_for_coordinate_type(
    coordinate_system: CoordinateSystemType, coordinate_key: CoordinateKey
):
    if coordinate_system == CoordinateSystemType.Cartesian:
        return (random.random() - 0.5) * 10
    elif coordinate_key == CoordinateKey.d:
        return random.random() * 5
    if coordinate_system == CoordinateSystemType.Polar:
        return (random.random() - 0.5) * 360
    else:
        return (random.random() - 0.5) * 2 * np.pi


def build_coordinate_test_path(
    path,
    coordinate_format_str,
    source_index,
    source_index_in_path,
    initial_position: Source,
):
    args = []
    if not source_index_in_path:
        args.append(source_index + 1)
    x = (random.random() - 0.5) * 10

    path = path.format(val=coordinate_format_str, idx=source_index + 1)

    initial_coordinate = osc_kreuz.coordinates.CoordinateCartesian(
        initial_position.x, initial_position.y, initial_position.z
    )
    # for coordinate_format_str in osc_kreuz.coordinates.get_all_coordinate_formats():
    coordinate_system, coordinate_keys = osc_kreuz.coordinates.parse_coordinate_format(
        coordinate_format_str
    )
    vals = [
        random_coords_for_coordinate_type(coordinate_system, key)
        for key in coordinate_keys
    ]

    args.extend(vals)

    if coordinate_system == osc_kreuz.coordinates.CoordinateSystemType.Cartesian:
        initial_coordinate.set_coordinates(coordinate_keys, vals)
    else:
        conv_coordinates = initial_coordinate.convert_to(coordinate_system)
        if coordinate_system == osc_kreuz.coordinates.CoordinateSystemType.Polar:
            coords = osc_kreuz.coordinates.CoordinatePolar(*conv_coordinates)
        else:
            coords = osc_kreuz.coordinates.CoordinatePolarRadians(*conv_coordinates)

        coords.set_coordinates(coordinate_keys, vals)

        cart_coordinates = coords.convert_to(
            osc_kreuz.coordinates.CoordinateSystemType.Cartesian
        )
        initial_coordinate.set_all(*cart_coordinates)

    return (path, args, initial_coordinate.get_all())


def test_full_positions():
    # cli runner to run the actual osckreuz
    runner = CliRunner()
    osc_kreuz_thread = Thread(
        target=runner.invoke,
        args=(main, ["-c", str(test_config.absolute().resolve())]),
    )
    osc_kreuz_thread.start()

    sleep(0.5)

    # listener to receive osc from osc kreuz
    listener = SeamlessListener(
        n_sources, "127.0.0.1", 9876, "127.0.0.1", 4999, "osckreuz_test"
    )

    # sender to send updates to osc-kreuz
    sender = OSCClient("127.0.0.1", 4455)

    # something changed to check if the update sent to the osc-kreuz also came back
    something_changed = Event()

    def osc_callback(*args):
        something_changed.set()

    # setup listener
    listener.register_gain_callback(osc_callback)
    listener.register_position_callback(osc_callback)
    listener.start_listening()

    # sleep to wait for initial barrage of updates
    sleep(0.5)

    # test a lot of different paths
    paths = [
        (path, False) for path in skc.osc_paths[skc.OscPathType.Position]["base"]
    ] + [(path, True) for path in skc.osc_paths[skc.OscPathType.Position]["extended"]]
    for (path, source_index_in_path), pos_format in product(
        paths, ["xyz", "aed", "aedrad"] * 500
    ):
        something_changed.clear()
        source_index = random.randint(0, n_sources - 1)

        path, args, expected_xyz = build_coordinate_test_path(
            path,
            pos_format,
            source_index,
            source_index_in_path,
            listener.sources[source_index],
        )
        before_xyz = (
            listener.sources[source_index].x,
            listener.sources[source_index].y,
            listener.sources[source_index].z,
        )
        sender.send_message(path.encode(), args)
        val = something_changed.wait(5)

        assert val == True
        # standard epsilon is to fine grained

        assert np.allclose(
            (
                listener.sources[source_index].x,
                listener.sources[source_index].y,
                listener.sources[source_index].z,
            ),
            expected_xyz,
            rtol=1e-3,
        )

    logging.info("unsubscribing")
    listener.unsubscribe_from_osc_kreuz()
    signal_handler()
    logging.info("killed osc-kreuz")


def test_positions():
    # cli runner to run the actual osckreuz
    runner = CliRunner()
    osc_kreuz_thread = Thread(
        target=runner.invoke,
        args=(main, ["-c", str(test_config.absolute().resolve())]),
    )
    osc_kreuz_thread.start()

    sleep(0.5)

    # listener to receive osc from osc kreuz
    listener = SeamlessListener(
        n_sources, "127.0.0.1", 9876, "127.0.0.1", 4999, "osckreuz_test"
    )

    # sender to send updates to osc-kreuz
    sender = OSCClient("127.0.0.1", 4455)

    # something changed to check if the update sent to the osc-kreuz also came back
    something_changed = Event()

    def osc_callback(*args):
        something_changed.set()

    # setup listener
    listener.register_gain_callback(osc_callback)
    listener.register_position_callback(osc_callback)
    listener.start_listening()

    # sleep to wait for initial barrage of updates
    sleep(0.5)

    # test a lot of different paths
    paths = [
        (path, False) for path in skc.osc_paths[skc.OscPathType.Position]["base"]
    ] + [(path, True) for path in skc.osc_paths[skc.OscPathType.Position]["extended"]]
    for (path, source_index_in_path), pos_format in product(
        paths, osc_kreuz.coordinates.get_all_coordinate_formats()
    ):
        something_changed.clear()
        source_index = random.randint(0, n_sources - 1)

        path, args, expected_xyz = build_coordinate_test_path(
            path,
            pos_format,
            source_index,
            source_index_in_path,
            listener.sources[source_index],
        )
        before_xyz = (
            listener.sources[source_index].x,
            listener.sources[source_index].y,
            listener.sources[source_index].z,
        )
        sender.send_message(path.encode(), args)
        val = something_changed.wait(5)

        assert val == True
        # standard epsilon is to fine grained

        try:
            assert np.allclose(
                (
                    listener.sources[source_index].x,
                    listener.sources[source_index].y,
                    listener.sources[source_index].z,
                ),
                expected_xyz,
                rtol=1e-4,
            )
        except AssertionError:
            print(f"checking pos path {path}, {pos_format}")

            print("before:   ", *before_xyz)
            print(
                "after:    ",
                listener.sources[source_index].x,
                listener.sources[source_index].y,
                listener.sources[source_index].z,
            )
            print("expected: ", *expected_xyz)
            print("args: ", *args)

            import matplotlib.pyplot as plt

            fig = plt.figure()
            ax = fig.add_subplot(1, 1, 1, projection="3d")
            ax.plot(*zip(before_xyz, (0, 0, 0)), label="before")
            ax.plot(
                *zip(
                    (
                        listener.sources[source_index].x,
                        listener.sources[source_index].y,
                        listener.sources[source_index].z,
                    ),
                    (0, 0, 0),
                ),
                label="after",
            )
            ax.plot(*zip(expected_xyz, (0, 0, 0)), label="expected")

            csystem, ckeys = coordinates.parse_coordinate_format(pos_format)
            if csystem == CoordinateSystemType.PolarRadians:
                c = CoordinatePolarRadians(0, 0, 1)
            else:
                c = CoordinatePolar(0, 0, 1)
            c.set_coordinates(ckeys, args[-len(ckeys) :])
            ax.plot(
                *zip(c.convert_to(CoordinateSystemType.Cartesian), (0, 0, 0)),
                label="change",
            )

            plt.legend()
            plt.title(f"{pos_format}: {c.get_all()}")
            plt.show()

            raise

    logging.info("unsubscribing")
    listener.unsubscribe_from_osc_kreuz()
    signal_handler()
    logging.info("killed osc-kreuz")


if __name__ == "__main__":
    # test_gains()
    test_full_positions()

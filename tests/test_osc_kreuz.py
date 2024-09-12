from itertools import product
import itertools
import logging
import math
from pathlib import Path
import random
from threading import Event, Thread
from time import sleep

from click.testing import CliRunner
import numpy as np
from oscpy.client import OSCClient

from osc_kreuz.config import read_config
import osc_kreuz.coordinates
from osc_kreuz.coordinates import (
    CoordinateCartesian,
    CoordinateKey,
    CoordinatePolar,
    CoordinatePolarRadians,
    CoordinateSystemType,
    parse_coordinate_format,
)
from osc_kreuz.osc_kreuz import main, signal_handler
import osc_kreuz.str_keys_conventions as skc
from osckreuz_listener import SeamlessListener, Source

test_config = Path(__file__).parent / "assets" / "config_test.yml"

config = read_config(test_config)

n_sources = config["global"]["number_sources"]
n_direct_sends = config["global"]["number_direct_sends"]
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
    port_ui = 4456
    port_data = 4008
    port_settings = 4998
    port_listen = 9876
    # cli runner to run the actual osckreuz
    runner = CliRunner()
    osc_kreuz_thread = Thread(
        target=runner.invoke,
        args=(
            main,
            [
                "-c",
                str(test_config.absolute().resolve()),
                "-u",
                port_ui,
                "-d",
                port_data,
                "-s",
                port_settings,
            ],
        ),
    )
    osc_kreuz_thread.start()

    sleep(0.5)

    # listener to receive osc from osc kreuz
    listener = SeamlessListener(
        n_sources,
        "127.0.0.1",
        port_listen,
        "127.0.0.1",
        port_settings,
        "osckreuz_test",
    )

    # sender to send updates to osc-kreuz
    sender = OSCClient("127.0.0.1", port_ui)

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
            listener.sources[source_index].gain[renderer],
            expected_val,
            rel_tol=1e-06,
        )
        print(f"success for gain path {path}")
    logging.info("unsubscribing")
    listener.unsubscribe_from_osc_kreuz()
    signal_handler()
    sleep(0.2)

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

    # create the correct osc path
    path = path.format(val=coordinate_format_str, idx=source_index + 1)

    # turn the initial coordinate into our coordinate class
    initial_coordinate = osc_kreuz.coordinates.CoordinateCartesian(
        initial_position.x, initial_position.y, initial_position.z
    )

    # parse the format string
    coordinate_system, coordinate_keys = osc_kreuz.coordinates.parse_coordinate_format(
        coordinate_format_str
    )

    # create random coordinates for this coordinate type and append to args
    vals = [
        random_coords_for_coordinate_type(coordinate_system, key)
        for key in coordinate_keys
    ]

    args.extend(vals)

    # set the changed coordinates
    if coordinate_system == osc_kreuz.coordinates.CoordinateSystemType.Cartesian:
        # if coordinates were cartesian originally, the new keys can just be replaced
        initial_coordinate.set_coordinates(coordinate_keys, vals)
    else:
        # the coordinates have to be converted first
        conv_coordinates = initial_coordinate.convert_to(coordinate_system)
        if coordinate_system == osc_kreuz.coordinates.CoordinateSystemType.Polar:
            coords = osc_kreuz.coordinates.CoordinatePolar(*conv_coordinates)
        else:
            coords = osc_kreuz.coordinates.CoordinatePolarRadians(*conv_coordinates)

        # set the changed coordinates
        coords.set_coordinates(coordinate_keys, vals)

        # convert back to cartesian
        cart_coordinates = coords.convert_to(
            osc_kreuz.coordinates.CoordinateSystemType.Cartesian
        )

        # replace initial coordinates
        initial_coordinate.set_all(*cart_coordinates)

    return (path, args, initial_coordinate.get_all())


def test_full_positions():
    port_ui = 4457
    port_data = 4009
    port_settings = 4997
    port_listen = 9875
    # cli runner to run the actual osckreuz
    runner = CliRunner()
    osc_kreuz_thread = Thread(
        target=runner.invoke,
        args=(
            main,
            [
                "-c",
                str(test_config.absolute().resolve()),
                "-u",
                port_ui,
                "-d",
                port_data,
                "-s",
                port_settings,
            ],
        ),
    )
    osc_kreuz_thread.start()

    sleep(0.5)

    # listener to receive osc from osc kreuz
    listener = SeamlessListener(
        n_sources,
        "127.0.0.1",
        port_listen,
        "127.0.0.1",
        port_settings,
        "osckreuz_test",
    )

    # sender to send updates to osc-kreuz
    sender = OSCClient("127.0.0.1", port_ui)

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
            rtol=1e-6,
            atol=1e-4,
        )

    logging.info("unsubscribing")
    listener.unsubscribe_from_osc_kreuz()
    signal_handler()
    sleep(0.2)
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

    source_indexes = {
        CoordinateSystemType.Cartesian: 1,
        CoordinateSystemType.Polar: 2,
        CoordinateSystemType.PolarRadians: 3,
    }
    test_coordinate = {
        CoordinateSystemType.Cartesian: CoordinateCartesian(1, 0, 0),
        CoordinateSystemType.Polar: CoordinatePolar(0, 0, 1),
        CoordinateSystemType.PolarRadians: CoordinatePolarRadians(0, 0, 1),
    }

    # test a lot of different paths
    paths = [
        (path, False) for path in skc.osc_paths[skc.OscPathType.Position]["base"]
    ] + [(path, True) for path in skc.osc_paths[skc.OscPathType.Position]["extended"]]

    for (path, source_index_in_path), pos_format in product(
        paths, osc_kreuz.coordinates.get_all_coordinate_formats() * 20
    ):
        something_changed.clear()
        coordinate_system, coordinate_keys = parse_coordinate_format(pos_format)

        source_index = source_indexes[coordinate_system]
        coordinate = test_coordinate[coordinate_system]

        osc_args = []

        if not source_index_in_path:
            osc_args.append(source_index + 1)

        # create the correct osc path
        path = path.format(val=pos_format, idx=source_index + 1)
        new_coordinates = [
            random_coords_for_coordinate_type(coordinate_system, key)
            for key in coordinate_keys
        ]

        coordinate.set_coordinates(coordinate_keys, new_coordinates)
        osc_args.extend(new_coordinates)

        expected_xyz = coordinate.convert_to(CoordinateSystemType.Cartesian)

        sender.send_message(path.encode(), osc_args)
        val = something_changed.wait(5)

        assert val == True

        received_xyz = (
            listener.sources[source_index].x,
            listener.sources[source_index].y,
            listener.sources[source_index].z,
        )
        # standard epsilon is too fine grained
        print(
            f"{pos_format} ({coordinate_system}), expected: {expected_xyz}, received: {received_xyz}"
        )
        assert np.allclose(
            received_xyz,
            expected_xyz,
            rtol=1e-6,
            atol=1e-4,
        )

    logging.info("unsubscribing")
    listener.unsubscribe_from_osc_kreuz()
    signal_handler()
    sleep(0.2)
    logging.info("killed osc-kreuz")


def test_direct_sends():
    port_ui = 4458
    port_data = 4010
    port_settings = 4995
    port_listen = 9873

    # cli runner to run the actual osckreuz
    runner = CliRunner()
    osc_kreuz_thread = Thread(
        target=runner.invoke,
        args=(
            main,
            [
                "-c",
                str(test_config.absolute().resolve()),
                "-u",
                port_ui,
                "-d",
                port_data,
                "-s",
                port_settings,
            ],
        ),
    )
    osc_kreuz_thread.start()

    sleep(0.5)

    # listener to receive osc from osc kreuz
    listener = SeamlessListener(
        n_sources,
        "127.0.0.1",
        port_listen,
        "127.0.0.1",
        port_settings,
        "osckreuz_test",
    )

    # sender to send updates to osc-kreuz
    sender = OSCClient("127.0.0.1", port_ui)

    # something changed to check if the update sent to the osc-kreuz also came back
    something_changed = Event()

    def osc_callback(*args):
        print(args)
        something_changed.set()

    # setup listener
    listener.register_direct_send_callback(osc_callback)
    listener.start_listening()

    sleep(0.5)
    for _ in range(50):
        something_changed.clear()

        source_index = random.randint(0, n_sources - 1)
        gain = random.random() * 2
        direct_send_index = random.randint(0, n_direct_sends - 1)
        path = b"/source/send/direct"

        sender.send_message(path, (source_index + 1, direct_send_index, gain))

        changed = something_changed.wait()

        assert changed == True
        assert math.isclose(
            listener.sources[source_index].direct_sends[direct_send_index],
            gain,
            rel_tol=1e-06,
        )

    logging.info("unsubscribing")
    listener.unsubscribe_from_osc_kreuz()
    signal_handler()
    sleep(0.2)

    logging.info("killed osc-kreuz")


def test_attributes():
    port_ui = 4459
    port_data = 4011
    port_settings = 4993
    port_listen = 9872

    # cli runner to run the actual osckreuz
    runner = CliRunner()
    osc_kreuz_thread = Thread(
        target=runner.invoke,
        args=(
            main,
            [
                "-c",
                str(test_config.absolute().resolve()),
                "-u",
                port_ui,
                "-d",
                port_data,
                "-s",
                port_settings,
            ],
        ),
    )
    osc_kreuz_thread.start()

    sleep(0.5)

    # listener to receive osc from osc kreuz
    listener = SeamlessListener(
        n_sources,
        "127.0.0.1",
        port_listen,
        "127.0.0.1",
        port_settings,
        "osckreuz_test",
    )

    # sender to send updates to osc-kreuz
    sender = OSCClient("127.0.0.1", port_ui)

    # something changed to check if the update sent to the osc-kreuz also came back
    something_changed = Event()

    def osc_callback(*args):
        print(args)
        something_changed.set()

    # setup listener
    listener.register_attribute_callback(osc_callback)
    listener.start_listening()

    sleep(0.5)
    base_path = "/source/{attribute}"
    indexed_path = "/source/{index}/{attribute}"
    for attribute, use_base_path in itertools.product(
        ["planewave", "doppler", "angle"], [True, False] * 20
    ):

        something_changed.clear()

        source_index = random.randint(0, n_sources - 1)
        val = random.random() * 2
        if use_base_path:
            path = base_path.format(attribute=attribute).encode()
            args = (source_index + 1, val)
        else:
            path = indexed_path.format(
                index=source_index + 1, attribute=attribute
            ).encode()
            args = (val,)
        sender.send_message(path, args)

        changed = something_changed.wait()

        assert changed == True
        assert math.isclose(
            listener.sources[source_index].attributes[attribute],
            val,
            rel_tol=1e-06,
        )

    logging.info("unsubscribing")
    listener.unsubscribe_from_osc_kreuz()
    signal_handler()
    sleep(0.2)

    logging.info("killed osc-kreuz")


if __name__ == "__main__":
    # test_gains()
    test_positions()

from itertools import product
import itertools
import math
import os
from pathlib import Path
import random
import shutil
from threading import Thread
import threading
from time import sleep
import uuid

import numpy as np
import pytest
from pythonosc.udp_client import SimpleUDPClient

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
import osc_kreuz.osc_kreuz
import osc_kreuz.str_keys_conventions as skc
from osckreuz_listener import SeamlessListener, Source


test_config = Path(__file__).parent / "assets" / "config_test.yml"

config = read_config(test_config)

n_sources = config["global"]["number_sources"]
n_direct_sends = config["global"]["number_direct_sends"]
renderers = config["global"]["render_units"]
n_renderers = len(renderers)


def build_gain_test_path(path: str, renderer_in_path: bool, source_index_in_path: bool):
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


@pytest.fixture
def listener(request):
    """Fixture to create an osc test listener. has to be initialized after the osc-kreuz fixture"""
    # get ports from markers
    port_listen = request.node.get_closest_marker("port_listen").args[0]
    port_settings = request.node.get_closest_marker("port_settings").args[0]

    # listener to receive osc from osc kreuz
    listener = SeamlessListener(
        n_sources,
        "127.0.0.1",
        port_listen,
        "127.0.0.1",
        port_settings,
        "osckreuz_test",
        reconnect_timeout=0.1,
    )

    # setup callback that just sets the value of listener.something_changed whenever an update is recieved
    listener.setup_default_osc_callback()
    listener.start_listening()
    listener.is_connected.wait()

    # sleep to wait for initial barrage of updates
    sleep(0.2)
    listener.something_changed.clear()
    yield listener
    # tear down
    print("unsubscribing")
    listener.shutdown()


@pytest.fixture(autouse=True)
def change_state_dir(monkeypatch):

    runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR") or Path("/tmp/"))
    runtime_dir = runtime_dir / "osc-kreuz-test" / str(uuid.uuid4())

    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    runtime_dir.mkdir(parents=True)

    monkeypatch.setenv("XDG_STATE_DIR", str(runtime_dir))


def osc_kreuz_runner(*args, **kwargs):
    osc_kreuz.osc_kreuz.main(args, standalone_mode=False)


@pytest.fixture
def osckreuz(request):
    port_ui = request.node.get_closest_marker("port_ui").args[0]
    port_data = request.node.get_closest_marker("port_data").args[0]
    port_settings = request.node.get_closest_marker("port_settings").args[0]

    osc_kreuz_thread = Thread(
        target=osc_kreuz_runner,
        args=(
            "-c",
            str(test_config.absolute().resolve()),
            "-u",
            port_ui,
            "-d",
            port_data,
            "-s",
            port_settings,
        ),
        name="osckreuz_runner",
    )
    osc_kreuz_thread.start()
    yield
    osc_kreuz.osc_kreuz.signal_handler()
    print("killed osc-kreuz")
    print("\nthreads still running:")
    for thread in threading.enumerate():
        print(thread.name)


@pytest.fixture
def oscsender(request):
    port_ui = request.node.get_closest_marker("port_ui").args[0]
    sender = SimpleUDPClient("127.0.0.1", port_ui)
    return sender


@pytest.mark.port_ui(4456)
@pytest.mark.port_data(4008)
@pytest.mark.port_settings(4998)
@pytest.mark.port_listen(9876)
def test_gains(osckreuz, listener, oscsender):

    # test a lot of different paths
    for path, args, source_index, renderer, expected_val in build_all_gain_paths():
        listener.something_changed.clear()
        oscsender.send_message(path, args)
        val = listener.something_changed.wait(5)

        assert val
        # standard epsilon is to fine grained
        assert math.isclose(
            listener.sources[source_index].gain[renderer],
            expected_val,
            rel_tol=1e-06,
        )
        print(f"success for gain path {path}")


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


@pytest.mark.port_ui(4457)
@pytest.mark.port_data(4009)
@pytest.mark.port_settings(4997)
@pytest.mark.port_listen(9875)
def test_full_positions(osckreuz, listener, oscsender):

    # test a lot of different paths
    paths = [
        (path, False) for path in skc.osc_paths[skc.OscPathType.Position]["base"]
    ] + [(path, True) for path in skc.osc_paths[skc.OscPathType.Position]["extended"]]
    for (path, source_index_in_path), pos_format in product(
        paths, ["xyz", "aed", "aedrad"] * 500
    ):
        listener.something_changed.clear()
        source_index = random.randint(0, n_sources - 1)

        path, args, expected_xyz = build_coordinate_test_path(
            path,
            pos_format,
            source_index,
            source_index_in_path,
            listener.sources[source_index],
        )

        oscsender.send_message(path, args)
        val = listener.something_changed.wait(5)

        assert val
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


@pytest.mark.port_ui(4460)
@pytest.mark.port_data(4015)
@pytest.mark.port_settings(4990)
@pytest.mark.port_listen(9870)
def test_positions(osckreuz, listener, oscsender):
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
        listener.something_changed.clear()
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

        oscsender.send_message(path, osc_args)
        val = listener.something_changed.wait(5)

        assert val

        received_xyz = (
            listener.sources[source_index].x,
            listener.sources[source_index].y,
            listener.sources[source_index].z,
        )
        # standard epsilon is too fine grained
        assert np.allclose(
            received_xyz,
            expected_xyz,
            rtol=1e-6,
            atol=1e-4,
        )


@pytest.mark.port_ui(4458)
@pytest.mark.port_data(4010)
@pytest.mark.port_settings(4995)
@pytest.mark.port_listen(9873)
def test_direct_sends(osckreuz, listener, oscsender):
    for _ in range(50):
        listener.something_changed.clear()

        source_index = random.randint(0, n_sources - 1)
        gain = random.random() * 2
        direct_send_index = random.randint(0, n_direct_sends - 1)
        path = "/source/send/direct"

        oscsender.send_message(path, [source_index + 1, direct_send_index, gain])

        changed = listener.something_changed.wait(5)

        assert changed
        assert math.isclose(
            listener.sources[source_index].direct_sends[direct_send_index],
            gain,
            rel_tol=1e-06,
        )


@pytest.mark.port_ui(4459)
@pytest.mark.port_data(4011)
@pytest.mark.port_settings(4993)
@pytest.mark.port_listen(9872)
def test_attributes(osckreuz, listener, oscsender):
    base_path = "/source/{attribute}"
    indexed_path = "/source/{index}/{attribute}"

    for attribute, use_base_path in itertools.product(
        ["planewave", "doppler", "angle"], [True, False] * 20
    ):

        listener.something_changed.clear()

        source_index = random.randint(0, n_sources - 1)
        val = random.random() * 2
        if use_base_path:
            path = base_path.format(attribute=attribute)
            args = [source_index + 1, val]
        else:
            path = indexed_path.format(index=source_index + 1, attribute=attribute)
            args = val
        oscsender.send_message(path, args)

        changed = listener.something_changed.wait(5)

        assert changed
        assert math.isclose(
            listener.sources[source_index].attributes[attribute],
            val,
            rel_tol=1e-06,
        )

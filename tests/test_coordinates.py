import random

import numpy as np
from pyfar import Coordinates

from osc_kreuz.coordinates import (
    CoordinateCartesian,
    CoordinateKey,
    CoordinatePolar,
    CoordinatePolarRadians,
    CoordinateSystemType,
    parse_coordinate_format,
)


def test_format_str_parsing():
    for format_str, format_tuple in [
        (
            "aed",
            (
                CoordinateSystemType.Polar,
                [CoordinateKey.a, CoordinateKey.e, CoordinateKey.d],
            ),
        ),
        (
            "aedrad",
            (
                CoordinateSystemType.PolarRadians,
                [CoordinateKey.a, CoordinateKey.e, CoordinateKey.d],
            ),
        ),
        (
            "xyz",
            (
                CoordinateSystemType.Cartesian,
                [CoordinateKey.x, CoordinateKey.y, CoordinateKey.z],
            ),
        ),
        ("x", (CoordinateSystemType.Cartesian, [CoordinateKey.x])),
        ("distance", (CoordinateSystemType.Polar, [CoordinateKey.d])),
        ("azim", (CoordinateSystemType.Polar, [CoordinateKey.a])),
        ("elevrad", (CoordinateSystemType.PolarRadians, [CoordinateKey.e])),
        ("arad", (CoordinateSystemType.PolarRadians, [CoordinateKey.a])),
    ]:
        format_parsed = parse_coordinate_format(format_str)
        print("parsing ", format_str)
        print(format_parsed[0], format_tuple[0])
        assert format_parsed[0] == format_tuple[0]

        print(format_parsed)
        print(len(format_parsed[1]), len(format_tuple[1]))

        assert len(format_parsed[1]) == len(format_tuple[1])
        for key_correct, key_parsed in zip(format_tuple[1], format_parsed[1]):
            assert key_correct == key_parsed
        print()


def test_spherical_coordinates():
    for _ in range(10000):

        c = CoordinatePolarRadians(
            (random.random() - 0.5) * 2 * np.pi,
            (random.random() - 0.5) * 2 * np.pi,
            (random.random()) * 5,
        )
        a, e, d = c.get_all()
        c_compare = Coordinates.from_spherical_elevation(a, e, d)
        print(c_compare.cartesian[0], c.convert_to(CoordinateSystemType.Cartesian))
        assert np.allclose(
            c.convert_to(CoordinateSystemType.Cartesian), c_compare.cartesian[0]
        )


def test_spherical_coordinates_setting_azim():
    for _ in range(10000):
        azim_new = (random.random() - 0.5) * 4 * np.pi

        c = CoordinatePolarRadians(
            (random.random() - 0.5) * 2 * np.pi,
            (random.random() - 0.5) * 2 * np.pi,
            (random.random()) * 5,
        )

        c.set_coordinates([CoordinateKey.a], [azim_new])
        a, e, d = c.get_all()
        c_compare = Coordinates.from_spherical_elevation(azim_new, e, d)
        print(c_compare.cartesian[0], c.convert_to(CoordinateSystemType.Cartesian))
        assert np.allclose(
            c.convert_to(CoordinateSystemType.Cartesian), c_compare.cartesian[0]
        )


def test_spherical_coordinates_degree():
    for _ in range(10000):

        c = CoordinatePolar(
            (random.random() - 0.5) * 720,
            (random.random() - 0.5) * 720,
            (random.random()) * 5,
        )
        a, e, d = c.get_all()
        c_compare = Coordinates.from_spherical_elevation(
            a / 180 * np.pi, e / 180 * np.pi, d
        )
        print(c_compare.cartesian[0], c.convert_to(CoordinateSystemType.Cartesian))

        assert np.allclose(
            c.convert_to(CoordinateSystemType.Cartesian), c_compare.cartesian[0]
        )


def test_specific_spherical_values():
    for a, e, d in [(-62, -124, 1), [-165.21469451262973, 172.50352478027344, 1]]:
        c = CoordinatePolar(a, e, d)
        c_compare = Coordinates.from_spherical_elevation(
            a / 180 * np.pi, e / 180 * np.pi, d
        )
        print(c_compare.cartesian[0], c.convert_to(CoordinateSystemType.Cartesian))

        assert np.allclose(
            c.convert_to(CoordinateSystemType.Cartesian), c_compare.cartesian[0]
        )


def test_replacing_single_values_azim():
    for _ in range(1000):
        xyz_coords = CoordinateCartesian(
            random.random() - 0.5 * 10,
            random.random() - 0.5 * 10,
            random.random() - 0.5 * 10,
        )

        new_azim = (random.random() - 0.5) * 8 * np.pi
        x, y, z = xyz_coords.get_all()
        # comparison with pyfar
        pyfar_initial = Coordinates.from_cartesian(x, y, z)

        pyfar_spherical = pyfar_initial.spherical_elevation[0]
        if pyfar_spherical[0] > np.pi:
            pyfar_spherical[0] -= 2 * np.pi
        a, e, d = xyz_coords.convert_to(CoordinateSystemType.PolarRadians)

        assert np.allclose([a, e, d], pyfar_spherical)

        pyfar_spherical[0] = new_azim

        aed_coords = CoordinatePolarRadians(a, e, d)
        aed_coords.set_coordinates([CoordinateKey.a], [new_azim])
        pyfar_changed = Coordinates.from_spherical_elevation(*pyfar_spherical)

        assert np.allclose(
            aed_coords.convert_to(CoordinateSystemType.Cartesian),
            pyfar_changed.cartesian[0],
        )

        xyz_coords.set_all(*aed_coords.convert_to(CoordinateSystemType.Cartesian))

        assert np.allclose(
            xyz_coords.get_all(),
            pyfar_changed.cartesian[0],
        )


def test_replacing_single_values_elev():
    for _ in range(1000):
        xyz_coords = CoordinateCartesian(
            random.random() - 0.5 * 10,
            random.random() - 0.5 * 10,
            random.random() - 0.5 * 10,
        )

        new_elev = (random.random() - 0.5) * 8 * np.pi
        x, y, z = xyz_coords.get_all()
        # comparison with pyfar
        pyfar_initial = Coordinates.from_cartesian(x, y, z)

        pyfar_spherical = pyfar_initial.spherical_elevation[0]
        if pyfar_spherical[0] > np.pi:
            pyfar_spherical[0] -= 2 * np.pi
        a, e, d = xyz_coords.convert_to(CoordinateSystemType.PolarRadians)

        assert np.allclose([a, e, d], pyfar_spherical)

        pyfar_spherical[1] = new_elev

        aed_coords = CoordinatePolarRadians(a, e, d)
        aed_coords.set_coordinates([CoordinateKey.e], [new_elev])
        pyfar_changed = Coordinates.from_spherical_elevation(*pyfar_spherical)

        assert np.allclose(
            aed_coords.convert_to(CoordinateSystemType.Cartesian),
            pyfar_changed.cartesian[0],
        )

        xyz_coords.set_all(*aed_coords.convert_to(CoordinateSystemType.Cartesian))

        assert np.allclose(
            xyz_coords.get_all(),
            pyfar_changed.cartesian[0],
        )


if __name__ == "__main__":
    test_specific_spherical_values()

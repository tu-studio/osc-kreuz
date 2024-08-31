import random
from osc_kreuz.coordinates import (
    CoordinatePolar,
    CoordinatePolarRadians,
    CoordinateSystemType,
    CoordinateKey,
    parse_coordinate_format,
)

from pyfar import Coordinates
import numpy as np


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


if __name__ == "__main__":
    test_spherical_coordinates_degree()

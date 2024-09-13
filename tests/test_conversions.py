import numpy as np

import osc_kreuz.conversionsTools as ct


def test_simple_conversions():
    for aed, xyz in [
        ((0, 0, 1), (1, 0, 0)),
        ((90, 0, 1), (0, 1, 0)),
        ((0, 90, 2), (0, 0, 2)),
    ]:
        xyz_calc = ct.aed2xyz(*aed)
        assert np.allclose(xyz, xyz_calc)
        aed_calc = ct.xyz2aed(*xyz_calc, coordinates_in_degree=True)
        assert np.allclose(aed, aed_calc)


def test_conversions_xyz_wraparound():
    for xyz, aed in [
        ((0, 1, 0), (90, 0, 1)),
        ((0, -1, 0), (-90, 0, 1)),
        ((0, 0, 1), (0, 90, 1)),
        ((0, 0, -1), (0, -90, 1)),
    ]:
        aed_calc = ct.xyz2aed(*xyz, coordinates_in_degree=True)
        assert np.allclose(aed, aed_calc)


def test_conversions_aed_wraparound():
    for aed, xyz in [
        ((270, 0, 1), (0, -1, 0)),
        ((360, 0, 1), (1, 0, 0)),
        ((450, 0, 1), (0, 1, 0)),
        ((-270, 0, 1), (0, 1, 0)),
        ((-360, 0, 1), (1, 0, 0)),
        ((-450, 0, 1), (0, -1, 0)),
    ]:
        xyz_calc = ct.aed2xyz(*aed)
        assert np.allclose(xyz, xyz_calc)


def test_conversions_aedrad_wraparound():
    for aed, xyz in [
        ((3 / 2 * np.pi, 0, 1), (0, -1, 0)),
        ((2 * np.pi, 0, 1), (1, 0, 0)),
        ((5 / 2 * np.pi, 0, 1), (0, 1, 0)),
        ((-3 / 2 * np.pi, 0, 1), (0, 1, 0)),
        ((-2 * np.pi, 0, 1), (1, 0, 0)),
        ((-5 / 2 * np.pi, 0, 1), (0, -1, 0)),
    ]:
        xyz_calc = ct.aed2xyz(*aed, coordinates_in_degree=False)
        assert np.allclose(xyz, xyz_calc)


# TODO test normalized coordinate systems, aedrad

import osc_kreuz.conversionsTools as ct
import numpy as np


def test_simple_conversions():
    for aed, xyz in [
        ((0, 0, 1), (1, 0, 0)),
        ((90, 0, 1), (0, 1, 0)),
        ((0, 90, 2), (0, 0, 2)),
    ]:
        xyz_calc = ct.conv_pol2cart(*aed)
        assert np.allclose(xyz, xyz_calc)
        aed_calc = ct.conv_cart2pol(*xyz_calc)
        assert np.allclose(aed, aed_calc)


def test_conversions_xyz_wraparound():
    for xyz, aed in [
        ((0, 1, 0), (90, 0, 1)),
        ((0, -1, 0), (-90, 0, 1)),
        ((0, 0, 1), (0, 90, 1)),
        ((0, 0, -1), (0, -90, 1)),
    ]:
        aed_calc = ct.conv_cart2pol(*xyz)
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
        xyz_calc = ct.conv_pol2cart(*aed)
        assert np.allclose(xyz, xyz_calc)


# TODO test normalized coordinate systems, aedrad

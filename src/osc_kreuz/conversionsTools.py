from typing import Any

import numpy as np


deg90_rad = np.deg2rad(90)


def mag_xyz(x, y, z) -> float:
    return np.sqrt(np.square(x) + np.square(y) + np.square(z))


def aed2xyz(a, e, d, coordinates_in_degree: bool = True) -> list[float]:
    if coordinates_in_degree == True:
        e = np.deg2rad(e)
        a = np.deg2rad(a)

    e = np.pi / 2 - e
    x = d * np.sin(e) * np.cos(a)
    y = d * np.sin(e) * np.sin(a)
    z = d * np.cos(e)

    return [x, y, z]


def xyz2aed(x, y, z, coordinates_in_degree: bool = True) -> list[float]:
    dist = mag_xyz(x, y, z)
    azim = np.arctan2(y, x)
    elev = np.arctan2(z, np.sqrt(np.square(x) + np.square(y)))

    if coordinates_in_degree == True:
        azim = np.rad2deg(azim)
        elev = np.rad2deg(elev)

    return [azim, elev, dist]


def conv_pol2cart(azim, elev, dist) -> list[float]:
    return aed2xyz(azim, elev, dist)


def conv_pol2ncart(azim, elev, dist) -> list[float]:
    x, y, z = aed2xyz(azim, elev, 1, coordinates_in_degree=True)
    return [x, y, z, dist]


def conv_cart2pol(x, y, z) -> list[float]:
    return xyz2aed(x, y, z, coordinates_in_degree=True)


def conv_cart2ncart(x, y, z) -> list[float]:
    nd = mag_xyz(x, y, z)
    inv_mag = 1 / nd
    nx = x * inv_mag
    ny = y * inv_mag
    nz = z * inv_mag
    return [nx, ny, nz, nd]


def conv_ncart2pol(nx, ny, nz, nd):
    a, e, d = xyz2aed(nx, ny, nz, coordinates_in_degree=True)
    # a = wrapAzimuth180(a)

    # e = wrapElevation90(e)

    return [a, e, nd]


def conv_ncart2cart(nx, ny, nz, nd) -> list[float]:
    x = nx * nd
    y = ny * nd
    z = nz * nd
    return [x, y, z]


def wrapAzimuth180(azim) -> float:
    if azim > 180.0:
        azim -= 360
        # return azim
    elif azim < -180.0:
        azim += 360.0

    while azim < -180.0 or azim > 180.0:
        azim = wrapAzimuth180(azim)

    return azim


def wrapElevation90(elev) -> float:
    if elev > 90.0:
        elev = 90.0 - elev
        return elev
    else:
        return elev


# TODO: implement this
def azi_to_wonderangle(azim) -> float:
    return azim


def dist_to_gain(dist) -> float:
    return dist


def convertedValue(x) -> Any:
    if isint(x):
        return int(x)
    elif isfloat(x):
        return float(x)
    else:
        return x


def isfloat(x):
    try:
        a = float(x)
    except (TypeError, ValueError):
        return False
    else:
        return True


def isint(x):
    try:
        a = float(x)
        b = int(a)
    except (TypeError, ValueError):
        return False
    else:
        return a == b

import numpy as np


deg90_rad = np.deg2rad(90)


def mag_xyz(x: float, y: float, z: float) -> float:
    return np.sqrt(np.square(x) + np.square(y) + np.square(z))


def aed2xyz(
    a: float, e: float, d: float, coordinates_in_degree: bool = True
) -> list[float]:
    if coordinates_in_degree:
        e = np.deg2rad(e)
        a = np.deg2rad(a)

    e = np.pi / 2 - e
    x = d * np.sin(e) * np.cos(a)
    y = d * np.sin(e) * np.sin(a)
    z = d * np.cos(e)

    return [x, y, z]


def xyz2aed(
    x: float, y: float, z: float, coordinates_in_degree: bool = True
) -> list[float]:
    dist = mag_xyz(x, y, z)
    azim = np.arctan2(y, x)
    elev = np.arctan2(z, np.sqrt(np.square(x) + np.square(y)))

    if coordinates_in_degree:
        azim = np.rad2deg(azim)
        elev = np.rad2deg(elev)

    return [azim, elev, dist]


# TODO: implement this
def azi_to_wonderangle(azim: float) -> float:
    return azim

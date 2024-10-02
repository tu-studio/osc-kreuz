from collections.abc import Iterable
from enum import Enum
from functools import lru_cache
from itertools import chain, combinations

import numpy as np

import osc_kreuz.conversionsTools as conversions


class CoordinateFormatException(Exception):
    pass


class CoordinateSystemType(Enum):
    Cartesian = 0
    Polar = 1
    PolarRadians = 2


class CoordinateKey(Enum):
    a = "a"
    e = "e"
    d = "d"
    x = "x"
    y = "y"
    z = "z"


radians_suffix = "rad"

# coordinate keys for the different coordinate systems
allowed_coordinate_keys = {
    CoordinateSystemType.Cartesian: [CoordinateKey.x, CoordinateKey.y, CoordinateKey.z],
    CoordinateSystemType.Polar: [CoordinateKey.a, CoordinateKey.e, CoordinateKey.d],
    CoordinateSystemType.PolarRadians: [
        CoordinateKey.a,
        CoordinateKey.e,
        CoordinateKey.d,
    ],
}

# coordinates that should be scaled when a scaling factor exists
scalable_coordinates = [
    CoordinateKey.x,
    CoordinateKey.y,
    CoordinateKey.z,
    CoordinateKey.d,
]

# aliases for the single keys of polar coordinates
polar_coordinate_aliases = {
    "azimuth": CoordinateKey.a,
    "azim": CoordinateKey.a,
    "elevation": CoordinateKey.e,
    "elev": CoordinateKey.e,
    "distance": CoordinateKey.d,
    "dist": CoordinateKey.d,
}

# type to make typing easier to read
CoordinateFormatTuple = tuple[CoordinateSystemType, list[CoordinateKey]]


class Coordinate:
    """Baseclass for all coordinates, only __init__() and convert_to() need to be overwritten."""

    def __init__(
        self, position_keys: list[CoordinateKey], initial_values: list[float]
    ) -> None:
        self.position_keys = position_keys
        self.position: dict[CoordinateKey, float] = {}

        # initialize position dict
        self.set_all(*initial_values)

    def convert_to(
        self, coordinate_format: CoordinateSystemType
    ) -> list[float] | tuple[float, float, float]:
        raise NotImplementedError

    def set_all(self, *values: float) -> None:
        """Sets all coordinates in the order they were declared in the constructor.

        Raises:
            CoordinateFormatException: raised when the number of values is not correct
        """
        if len(values) != len(self.position_keys):
            raise CoordinateFormatException(
                f"Invalid Number of values for coordinate: {len(values)}"
            )

        for key, val in zip(self.position_keys, values):
            self.position[key] = val

        self.validate_coordinates()

    def get_all(self) -> list[float]:
        """gets all coordinates in the order they were declared in the constructor

        Returns:
            list[float]: list of coordinates
        """
        return self.get_coordinates(self.position_keys)

    def validate_coordinates(self) -> None:
        """overwrite this function if for some coordinates special processing is required"""
        pass

    def constrain_centered_coordinate(
        self, val: float, constrain_range: float
    ) -> float:
        half_range = constrain_range / 2
        return ((val + half_range) % constrain_range) - half_range

    def set_coordinates(
        self,
        coordinates: CoordinateKey | list[CoordinateKey],
        values: float | Iterable[float],
        scaling_factor: float = 1.0,
    ) -> bool:
        """Sets values for all specified coordinates. values and coordinates need to be lists of the same length

        Args:
            coordinates (CoordinateKey | list[CoordinateKey]): single coordinate or list of coordinates to set
            values (float | list[float]): single value or list of values to set
            scaling_factor (float, optional): used to scale the coordinate system . Defaults to 1.0.

        Raises:
            CoordinateFormatException: raised when the Coordinate Format is invalid

        Returns:
            bool: True if the coordinate changed, False if the same value as before was set
        """
        # make sure input is iterable
        if not isinstance(coordinates, Iterable):
            coordinates = [coordinates]
        if not isinstance(values, Iterable):
            values = [values]

        coordinate_changed = False

        for c_key, val in zip(coordinates, values):
            # scale coordinate if necessary
            if c_key in scalable_coordinates:
                val = val * scaling_factor

            # set the coordinate if it exists
            try:
                if self.position[c_key] != val:
                    self.position[c_key] = val
                    coordinate_changed = True
            except KeyError:
                raise CoordinateFormatException(f"Invalid Coordinate Key: {c_key}")
        if coordinate_changed:
            self.validate_coordinates()
        return coordinate_changed

    def get_coordinates(
        self, coordinates: CoordinateKey | list[CoordinateKey]
    ) -> list[float]:
        """Get all specified coordinates

        Args:
            coordinates (CoordinateKey | list[CoordinateKey]): single coordinate or list of desired coordinates

        Returns:
            list[float]: list of coordinates
        """
        if not isinstance(coordinates, Iterable):
            coordinates = [coordinates]
        return [self.position[key] for key in coordinates]


class CoordinateCartesian(Coordinate):
    def __init__(self, x, y, z) -> None:
        super().__init__([CoordinateKey.x, CoordinateKey.y, CoordinateKey.z], [x, y, z])

    def convert_to(
        self, coordinate_format: CoordinateSystemType
    ) -> list[float] | tuple[float, float, float]:
        if coordinate_format == CoordinateSystemType.Polar:
            return conversions.xyz2aed(*self.get_all(), coordinates_in_degree=True)
        elif coordinate_format == CoordinateSystemType.PolarRadians:
            return conversions.xyz2aed(*self.get_all(), coordinates_in_degree=False)
        elif coordinate_format == CoordinateSystemType.Cartesian:
            return self.get_all()
        else:
            raise CoordinateFormatException(
                f"Invalid Conversion format for Cartesion Coordinates: {coordinate_format}"
            )


class CoordinatePolar(Coordinate):
    def __init__(self, a, e, d) -> None:
        super().__init__([CoordinateKey.a, CoordinateKey.e, CoordinateKey.d], [a, e, d])

    def validate_coordinates(self):

        # constrain elevation between -180 and 180
        if not (-180 <= self.position[CoordinateKey.e] <= 180):
            self.position[CoordinateKey.e] = (
                (self.position[CoordinateKey.e] + 180) % 360
            ) - 180

        # constrain azim between -180 and 180
        if not (-180 <= self.position[CoordinateKey.a] <= 180):
            self.position[CoordinateKey.a] = (
                (self.position[CoordinateKey.a] + 180) % 360
            ) - 180

    def convert_to(
        self, coordinate_format: CoordinateSystemType
    ) -> list[float] | tuple[float, float, float]:
        if coordinate_format == CoordinateSystemType.Cartesian:
            return conversions.aed2xyz(*self.get_all(), coordinates_in_degree=True)
        elif coordinate_format == CoordinateSystemType.PolarRadians:
            a, e, d = self.get_all()
            return a / 180 * np.pi, e / 180 * np.pi, d
        elif coordinate_format == CoordinateSystemType.Polar:
            return self.get_all()
        else:
            raise CoordinateFormatException(
                f"Invalid Conversion format for Polar Coordinates: {coordinate_format}"
            )


class CoordinatePolarRadians(Coordinate):
    def __init__(self, a, e, d) -> None:
        super().__init__([CoordinateKey.a, CoordinateKey.e, CoordinateKey.d], [a, e, d])

    def validate_coordinates(self):

        # constrain elev between -pi and pi
        if not (-np.pi <= self.position[CoordinateKey.e] <= np.pi):
            self.position[CoordinateKey.e] = (
                (self.position[CoordinateKey.e] + np.pi) % (2 * np.pi)
            ) - np.pi

        # constrain azim between -pi and pi
        if not (-np.pi <= self.position[CoordinateKey.a] <= np.pi):
            self.position[CoordinateKey.a] = (
                (self.position[CoordinateKey.a] + np.pi) % (2 * np.pi)
            ) - np.pi

    def convert_to(
        self, coordinate_format: CoordinateSystemType
    ) -> list[float] | tuple[float, float, float]:
        if coordinate_format == CoordinateSystemType.Cartesian:
            return conversions.aed2xyz(*self.get_all(), coordinates_in_degree=False)
        elif coordinate_format == CoordinateSystemType.Polar:
            a, e, d = self.get_all()
            return a / np.pi * 180, e / np.pi * 180, d
        elif coordinate_format == CoordinateSystemType.PolarRadians:
            return self.get_all()
        else:
            raise CoordinateFormatException(
                f"Invalid Conversion format for PolarRadians Coordinates: {coordinate_format}"
            )


@lru_cache(maxsize=100)
def parse_coordinate_format(format_str: str) -> CoordinateFormatTuple:
    """Parse an incoming coordinate format string to the format required by Coordinate

    Args:
        format_str (str): coordinate format string, for example "aed", "xy", "azimrad"

    Raises:
        CoordinateFormatException: _description_

    Returns:
        CoordinateFormatTuple: Tuple containing the type of the coordinate system and a list of the individual coordinate keys
    """

    # find the coordinate system type
    coordinate_format = CoordinateSystemType.Cartesian

    if format_str.endswith(radians_suffix):
        format_str = format_str[: -len(radians_suffix)]
        coordinate_format = CoordinateSystemType.PolarRadians

    elif (
        CoordinateKey[format_str[0]]
        in allowed_coordinate_keys[CoordinateSystemType.Polar]
    ):
        coordinate_format = CoordinateSystemType.Polar

    coordinate_keys = []

    # parse special aliases
    if (
        coordinate_format == CoordinateSystemType.Polar
        or coordinate_format == CoordinateSystemType.PolarRadians
    ):
        try:
            coordinate_keys.append(polar_coordinate_aliases[format_str])
            format_str = ""
        except KeyError:
            pass

    # parse remaining letters individually
    for key in format_str:
        try:
            coordinate_keys.append(CoordinateKey[key])
        except ValueError:
            raise CoordinateFormatException(f"Invalid coordinate key {key}")

    # TODO check that only coordinate keys legal to the current system are used
    return (coordinate_format, coordinate_keys)


def powerset(iterable):
    "powerset([1,2,3]) --> () (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)"
    s = list(iterable)
    return chain.from_iterable(combinations(s, r) for r in range(1, len(s) + 1))


def get_all_coordinate_formats() -> list[str]:
    format_strings: list[str] = []
    for key in allowed_coordinate_keys:
        suffix = radians_suffix if key == CoordinateSystemType.PolarRadians else ""
        all_combinations = [
            "".join([k.value for k in combinations]) + suffix
            for combinations in powerset(allowed_coordinate_keys[key])
        ]
        format_strings.extend(all_combinations)

    for key in polar_coordinate_aliases:
        format_strings.append(key)
        format_strings.append(key + radians_suffix)

    return format_strings

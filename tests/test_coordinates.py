from osc_kreuz.coordinates import (
    CoordinateSystemType,
    CoordinateKey,
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


if __name__ == "__main__":
    test_format_str_parsing()

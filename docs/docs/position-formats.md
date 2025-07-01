
# Supported position formats

Currently, 2 different coordinate systems are supported: **cartesian** and **spherical** coordinates.

For cartesian coordinates, the format string can contain any of the letters `x`, `y` and `z`. For spherical coordinates, the letters `a`, `e`, `d` are allowed. A suffix of `rad` tells the osc-kreuz that azimuth or elevation should be in radians, otherwise they are in degrees. If only one of the spherical coordinates is required, `azim`, `azimuth`, `elev`, `elevation`, `dist`, `distance` are also valid position formats.

Some examples of valid position format strings are listed in the following table:

| Position Format String | Datatypes of Data | Comment |
| ---------------------- | ----------------- | ------- |
| `xyz`                  | `fff`             |         |
| `xz`                   | `ff`              |         |
| `y`                    | `f`               |         |
| `aed`                  | `fff`             |         |
| `aedrad`               | `fff`             |         |
| `distance`             | `f`               |         |
| `elevrad`              | `f`               |         |
| `azimuth`              | `f`               |         |
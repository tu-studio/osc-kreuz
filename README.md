# OSC-kreuz
The osc-kreuz serves as a central interface for OSC messages in a multiclient spatial rendering environment. It automatically translates incoming OSC messages to match the expected formats of the rendering engines and distributes it to all connected clients including UI Clients and Data clients for automation data.


# Installation
Install with pip:
```bash
pip install osc-kreuz
```

On our machines osc-kreuz is installed systemwide using:
``` bash
meson setup -Dversioned_install=true --wipe build
meson install -C build
```

when using the `versioned_install` flag the installation of multiple different versions of the osc-kreuz is possible, see [here](versioned_install.md)

# Configuration
The configuration is done using a YAML-Config file, an example config file can be found in `example_configs`.

## global config
the "globalconfig"-Section of the Config contains general settings:

| Setting               | Description                                                                                                        | Default                   |
| --------------------- | ------------------------------------------------------------------------------------------------------------------ | ------------------------- |
| `oscr_ip`             | ip address the osc-kreuz listens on                                                                                | 0.0.0.0                   |
| `inputport_ui`        | Highest Priority listen-port intended for GUI applications                                                         | 4455                      |
| `inputport_data`      | lower priority port for listening to automated clients. pauses listening when data is received on `inputport_ui`   | 4007                      |
| `inputport_settings`  | global configs can be changed on this port                                                                         | 4999                      |
| `number_sources`      | number of source audio channels                                                                                    | 64                        |
| `max_gain`            | max gain for the audiorouter                                                                                       | 2                         |
| `min_dist`            |                                                                                                                    | 0.001                     |
| `number_direct_sends` | number of direct send channels                                                                                     | 46                        |
| `send_changes_only`   | only send when source data has changed,                                                                            | true                      |
| `data_port_timeout`   | when data is received on the ui port, the data port is paused for this timeout, in seconds, set to 0 to deactivate | 2                         |
| `render_units`        | available render units in this system                                                                              | ["ambi", "wfs", "reverb"] |

## Receivers
This Section of the config contains a list of clients that receive updates from osc-kreuz.
common settings are:
| Setting           | Description                                                                                              | Default |
| ----------------- | -------------------------------------------------------------------------------------------------------- | ------- |
| `type`            | Type of the receiver, you should probably use `audiomatrix`                                              |         |
| `hostname`        | target host, can be a hostname or an ip address, ignored when `hosts` is set                             |         |
| `port`            | Port the target listens on, ignored when `hosts` is set                                                  |         |
| `hosts`           | can contain a list of hostnames and ports, allows sending updates to multiple receivers of the same type |         |
| `updateintervall` | time (in ms) to wait between subsequent update bundles                                                   |         |
| `dataformat`      | format the positional data is sent in. supports a lot of different formats                               | xyz     |

### Audiomatrix
This Receiver type is intended for use with the [Audio Matrix](https://github.com/tu-studio/audio-matrix), but can be configured in a flexible way in order to be used for many different receivers.
what makes it powerful is an additional option, `paths`, for configuring the osc paths the target listens on.
`paths` contains a list of osc paths with the following configuration options:
| Setting    | Description                                                                                     |
| ---------- | ----------------------------------------------------------------------------------------------- |
| `path`     | OSC-Path                                                                                        |
| `type`     | type of data that is sent to this path, options are `gain` and `position`                       |
| `renderer` | only used when `type`=`gain`, choose renderer whose gain is sent to this path                   |
| `format`   | only used when `type`=`position`, chooses the datatype of the positional data sent to this path |

# Supported data formats
Data is sent to clients with the index of the source as the first parameter, followed by the positional or gain data.

| Type                                         | Supported formats                                                                                   |
| -------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Cartesion Coordinates                        | `x`, `y`, `z`, `xyz`, `xy`, `xz`, `yz`                                                              |
| Spherical Coordinates (degrees)              | `azim`, `elev`, `dist`, `aed`, `ad`, `ae`, `ed`                                                     |
| Spherical Coordinates (radians)              | `aedrad`                                                                                            |
| Normalized Cartesian Coordinates (for Oscar) | `nx`, `nxd`, `ny`, `nyd`, `nz`, `nzd`, `nxyz`, `nxyzd`, `nxy`, `nxyd`, `nxz`, `nxzd`, `nyz`, `nyzd` |

# Development
For Development it is recommended to install the python package in a virtual environment.
``` bash
python -m venv venv
source venv/bin/activate
pip install -e .
```
then it can be run using 
```bash
osc-kreuz
# To Check Command line options use
osc-kreuz --help
``` 

# Releasing

Releases are published automatically when a tag is pushed to GitHub.

``` bash

# Set next version number
export RELEASE=x.x.x

git tag -a $RELEASE -m "Version $RELEASE"

# Push
git push --tags
```
# About
The osc-kreuz was originally developed as part of the SeamLess Suite, then named OSC-Router.